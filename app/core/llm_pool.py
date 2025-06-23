import asyncio
import aiohttp
import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    content: str
    model: str
    tokens: int
    latency: float
    cached: bool = False

class LLMConnection:
    def __init__(self, base_url: str, model: str, timeout: int = 30):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_healthy = True
        self.last_check = 0
        self.consecutive_failures = 0
    
    async def initialize(self):
        timeout_config = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout_config)
        await self.health_check()
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> bool:
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    self.is_healthy = self.model in models
                    self.consecutive_failures = 0
                    self.last_check = time.time()
                    return self.is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.consecutive_failures += 1
            if self.consecutive_failures > 3:
                self.is_healthy = False
        
        return False
    
    async def generate(self, prompt: str, system_message: str = "", temperature: float = 0.7, max_tokens: int = 500) -> Optional[Dict[str, Any]]:
        if not self.is_healthy:
            if time.time() - self.last_check > 60:
                await self.health_check()
            if not self.is_healthy:
                return None
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message} if system_message else None,
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        }
        
        payload["messages"] = [m for m in payload["messages"] if m]
        
        try:
            async with self.session.post(f"{self.base_url}/api/chat", json=payload) as response:
                if response.status == 200:
                    self.consecutive_failures = 0
                    return await response.json()
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures > 3:
                        self.is_healthy = False
                    return None
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            self.consecutive_failures += 1
            if self.consecutive_failures > 3:
                self.is_healthy = False
            return None

class LLMPool:
    def __init__(self, base_urls: List[str], models: List[str], pool_size: int = 2):
        self.connections: List[LLMConnection] = []
        self.pool_size = pool_size
        self.current_index = 0
        self._lock = asyncio.Lock()
        
        for i in range(pool_size):
            base_url = base_urls[i % len(base_urls)]
            model = models[i % len(models)]
            self.connections.append(LLMConnection(base_url, model))
    
    async def initialize(self):
        await asyncio.gather(*[conn.initialize() for conn in self.connections])
        logger.info(f"LLM pool initialized with {len(self.connections)} connections")
    
    async def close(self):
        await asyncio.gather(*[conn.close() for conn in self.connections])
    
    async def get_connection(self) -> Optional[LLMConnection]:
        async with self._lock:
            healthy_connections = [c for c in self.connections if c.is_healthy]
            if not healthy_connections:
                await self._try_recover_connections()
                healthy_connections = [c for c in self.connections if c.is_healthy]
            
            if not healthy_connections:
                return None
            
            self.current_index = (self.current_index + 1) % len(healthy_connections)
            return healthy_connections[self.current_index]
    
    async def _try_recover_connections(self):
        unhealthy = [c for c in self.connections if not c.is_healthy]
        if unhealthy:
            logger.info(f"Attempting to recover {len(unhealthy)} unhealthy connections")
            await asyncio.gather(*[c.health_check() for c in unhealthy], return_exceptions=True)

class LLMCache:
    def __init__(self, redis_client, ttl: int = 3600, max_size: int = 1000):
        self.redis = redis_client
        self.ttl = ttl
        self.max_size = max_size
        self.cache_prefix = "jarvis:llm_cache:"
        self.stats_key = "jarvis:llm_cache:stats"
    
    def _generate_key(self, prompt: str, system_message: str, model: str, temperature: float) -> str:
        content = f"{prompt}|{system_message}|{model}|{temperature}"
        return self.cache_prefix + hashlib.md5(content.encode()).hexdigest()
    
    async def get(self, prompt: str, system_message: str, model: str, temperature: float) -> Optional[str]:
        key = self._generate_key(prompt, system_message, model, temperature)
        
        cached = await self.redis.get(key)
        if cached:
            await self.redis.hincrby(self.stats_key, "hits", 1)
            await self.redis.expire(key, self.ttl)
            return cached.decode()
        
        await self.redis.hincrby(self.stats_key, "misses", 1)
        return None
    
    async def set(self, prompt: str, system_message: str, model: str, temperature: float, response: str):
        key = self._generate_key(prompt, system_message, model, temperature)
        
        await self.redis.setex(key, self.ttl, response)
        await self.redis.hincrby(self.stats_key, "sets", 1)
        
        await self._enforce_size_limit()
    
    async def _enforce_size_limit(self):
        cursor = 0
        keys = []
        
        while True:
            cursor, batch = await self.redis.scan(cursor, match=f"{self.cache_prefix}*", count=100)
            keys.extend(batch)
            if cursor == 0:
                break
        
        if len(keys) > self.max_size:
            ttls = await asyncio.gather(*[self.redis.ttl(k) for k in keys])
            keys_with_ttl = sorted(zip(keys, ttls), key=lambda x: x[1])
            
            to_delete = [k for k, _ in keys_with_ttl[:len(keys) - self.max_size]]
            if to_delete:
                await self.redis.delete(*to_delete)
    
    async def get_stats(self) -> Dict[str, int]:
        stats = await self.redis.hgetall(self.stats_key)
        return {k.decode(): int(v) for k, v in stats.items()}
    
    async def warm_up(self, common_prompts: List[Tuple[str, str]]):
        for prompt, response in common_prompts:
            key = self._generate_key(prompt, "", "llama3.1:8b", 0.7)
            await self.redis.setex(key, self.ttl * 2, response)
        
        logger.info(f"Warmed up cache with {len(common_prompts)} common prompts")

class OptimizedLLMService:
    def __init__(
        self,
        base_urls: List[str],
        models: List[str],
        redis_client,
        pool_size: int = 2,
        cache_ttl: int = 3600,
        max_cache_size: int = 1000
    ):
        self.pool = LLMPool(base_urls, models, pool_size)
        self.cache = LLMCache(redis_client, cache_ttl, max_cache_size)
        self.default_model = models[0] if models else "llama3.1:8b"
        self.context_memory: Dict[str, List[Dict[str, str]]] = {}
        self.max_context_size = 10
    
    async def initialize(self):
        await self.pool.initialize()
        
        common_prompts = [
            ("oi", "Olá! Como posso ajudá-lo hoje?"),
            ("olá", "Olá! Bem-vindo ao Jarvis. Em que posso ajudar?"),
            ("menu", "Aqui estão as opções disponíveis:\n• Consultar dados\n• Obter suporte\n• Agendar atendimento"),
            ("ajuda", "Posso ajudar com:\n• Consultas e relatórios\n• Problemas técnicos\n• Agendamentos"),
            ("obrigado", "Por nada! Sempre que precisar, estarei aqui."),
            ("tchau", "Até logo! Foi um prazer ajudá-lo.")
        ]
        await self.cache.warm_up(common_prompts)
    
    async def close(self):
        await self.pool.close()
    
    async def generate_response(
        self,
        prompt: str,
        system_message: str = "",
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        use_cache: bool = True
    ) -> LLMResponse:
        start_time = time.time()
        
        if use_cache:
            cached_response = await self.cache.get(prompt, system_message, self.default_model, temperature)
            if cached_response:
                return LLMResponse(
                    content=cached_response,
                    model=self.default_model,
                    tokens=0,
                    latency=time.time() - start_time,
                    cached=True
                )
        
        connection = await self.pool.get_connection()
        if not connection:
            raise Exception("No healthy LLM connections available")
        
        messages = []
        if session_id and session_id in self.context_memory:
            messages.extend(self.context_memory[session_id][-self.max_context_size:])
        
        result = await connection.generate(prompt, system_message, temperature, max_tokens)
        
        if not result:
            raise Exception("Failed to generate response")
        
        content = result.get("message", {}).get("content", "")
        tokens = result.get("eval_count", 0)
        
        if use_cache and content:
            await self.cache.set(prompt, system_message, connection.model, temperature, content)
        
        if session_id:
            if session_id not in self.context_memory:
                self.context_memory[session_id] = []
            self.context_memory[session_id].append({"role": "user", "content": prompt})
            self.context_memory[session_id].append({"role": "assistant", "content": content})
            if len(self.context_memory[session_id]) > self.max_context_size * 2:
                self.context_memory[session_id] = self.context_memory[session_id][-self.max_context_size:]
        
        return LLMResponse(
            content=content,
            model=connection.model,
            tokens=tokens,
            latency=time.time() - start_time,
            cached=False
        )
    
    async def classify_intent(self, message: str) -> Dict[str, Any]:
        system_prompt = """Classifique a mensagem em uma das categorias:
- greeting: saudações, cumprimentos
- data_query: consultas de dados, relatórios
- support: problemas técnicos, erros
- scheduling: agendamentos, reuniões
- general: outros assuntos

Responda APENAS com JSON: {"intent": "categoria", "confidence": 0.0-1.0}"""
        
        try:
            response = await self.generate_response(
                message,
                system_prompt,
                temperature=0.3,
                max_tokens=100,
                use_cache=True
            )
            
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            
            return json.loads(content)
        except:
            message_lower = message.lower()
            if any(word in message_lower for word in ["oi", "olá", "bom dia", "boa tarde"]):
                return {"intent": "greeting", "confidence": 0.8}
            elif any(word in message_lower for word in ["relatório", "dados", "dashboard", "vendas"]):
                return {"intent": "data_query", "confidence": 0.7}
            elif any(word in message_lower for word in ["erro", "problema", "bug", "não funciona"]):
                return {"intent": "support", "confidence": 0.7}
            elif any(word in message_lower for word in ["agendar", "reunião", "marcar"]):
                return {"intent": "scheduling", "confidence": 0.7}
            else:
                return {"intent": "general", "confidence": 0.5}
    
    async def get_status(self) -> Dict[str, Any]:
        healthy_connections = sum(1 for c in self.pool.connections if c.is_healthy)
        cache_stats = await self.cache.get_stats()
        
        return {
            "pool": {
                "total_connections": len(self.pool.connections),
                "healthy_connections": healthy_connections,
                "models": list(set(c.model for c in self.pool.connections))
            },
            "cache": cache_stats,
            "context_sessions": len(self.context_memory)
        }
    
    def clear_session_context(self, session_id: str):
        if session_id in self.context_memory:
            del self.context_memory[session_id]