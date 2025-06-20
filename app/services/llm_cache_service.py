import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
from dataclasses import dataclass, asdict
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Entrada no cache"""
    key: str
    prompt: str
    response: str
    model: str
    temperature: float
    created_at: datetime
    hits: int = 0
    last_accessed: datetime = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_accessed'] = self.last_accessed.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)

class LLMCacheService:
    """Serviço de cache para respostas do LLM"""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        cache_prefix: str = "llm_cache",
        ttl_seconds: int = 3600,  # 1 hora
        max_cache_size: int = 1000,
        similarity_threshold: float = 0.9
    ):
        self.redis = redis_client
        self.cache_prefix = cache_prefix
        self.ttl = ttl_seconds
        self.max_cache_size = max_cache_size
        self.similarity_threshold = similarity_threshold
        
        # Métricas
        self.metrics_key = f"{cache_prefix}:metrics"
        self.cache_keys_set = f"{cache_prefix}:keys"
        
        # Cache local para prompts frequentes
        self.local_cache: Dict[str, Tuple[str, datetime]] = {}
        self.local_cache_max_size = 100
        self.local_cache_ttl = 300  # 5 minutos
    
    def _generate_cache_key(
        self,
        prompt: str,
        system_message: str = "",
        model: str = "",
        temperature: float = 0.0
    ) -> str:
        """Gera chave única para o cache"""
        # Normaliza o prompt
        normalized_prompt = prompt.lower().strip()
        
        # Cria hash único
        content = f"{normalized_prompt}|{system_message}|{model}|{temperature}"
        hash_key = hashlib.md5(content.encode()).hexdigest()
        
        return f"{self.cache_prefix}:{hash_key}"
    
    async def get(
        self,
        prompt: str,
        system_message: str = "",
        model: str = "",
        temperature: float = 0.0
    ) -> Optional[str]:
        """Busca resposta no cache"""
        try:
            # Primeiro verifica cache local
            cache_key = self._generate_cache_key(prompt, system_message, model, temperature)
            
            # Verifica cache local
            if cache_key in self.local_cache:
                response, cached_at = self.local_cache[cache_key]
                if (datetime.now() - cached_at).seconds < self.local_cache_ttl:
                    await self._increment_metric("local_hits")
                    return response
                else:
                    # Remove do cache local se expirado
                    del self.local_cache[cache_key]
            
            # Busca no Redis
            cached_data = await self.redis.get(cache_key)
            
            if cached_data:
                entry = CacheEntry.from_dict(json.loads(cached_data))
                
                # Atualiza métricas
                entry.hits += 1
                entry.last_accessed = datetime.now()
                
                # Salva atualização
                await self.redis.setex(
                    cache_key,
                    self.ttl,
                    json.dumps(entry.to_dict())
                )
                
                # Adiciona ao cache local
                self._update_local_cache(cache_key, entry.response)
                
                # Métricas
                await self._increment_metric("cache_hits")
                logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                
                return entry.response
            
            # Se não encontrou exato, busca similar
            similar_response = await self._find_similar_cached(prompt, system_message, model, temperature)
            if similar_response:
                await self._increment_metric("similarity_hits")
                return similar_response
            
            await self._increment_metric("cache_misses")
            return None
            
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            await self._increment_metric("cache_errors")
            return None
    
    async def set(
        self,
        prompt: str,
        response: str,
        system_message: str = "",
        model: str = "",
        temperature: float = 0.0
    ) -> bool:
        """Armazena resposta no cache"""
        try:
            cache_key = self._generate_cache_key(prompt, system_message, model, temperature)
            
            # Cria entrada
            entry = CacheEntry(
                key=cache_key,
                prompt=prompt,
                response=response,
                model=model,
                temperature=temperature,
                created_at=datetime.now()
            )
            
            # Salva no Redis
            await self.redis.setex(
                cache_key,
                self.ttl,
                json.dumps(entry.to_dict())
            )
            
            # Adiciona à lista de chaves
            await self.redis.sadd(self.cache_keys_set, cache_key)
            
            # Atualiza cache local
            self._update_local_cache(cache_key, response)
            
            # Verifica tamanho do cache
            await self._enforce_cache_size_limit()
            
            # Métricas
            await self._increment_metric("cache_sets")
            logger.debug(f"Cached response for prompt: {prompt[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            await self._increment_metric("cache_errors")
            return False
    
    async def invalidate(self, pattern: str = "*") -> int:
        """Invalida entradas do cache baseado em padrão"""
        try:
            # Busca chaves que correspondem ao padrão
            full_pattern = f"{self.cache_prefix}:{pattern}"
            keys = []
            
            async for key in self.redis.scan_iter(match=full_pattern):
                keys.append(key)
            
            if keys:
                # Remove do Redis
                await self.redis.delete(*keys)
                
                # Remove do conjunto de chaves
                for key in keys:
                    await self.redis.srem(self.cache_keys_set, key)
                
                # Limpa cache local
                self.local_cache.clear()
                
                logger.info(f"Invalidated {len(keys)} cache entries")
            
            return len(keys)
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        try:
            # Métricas básicas
            metrics = await self.redis.hgetall(self.metrics_key)
            metrics_decoded = {k.decode(): int(v) for k, v in metrics.items()}
            
            # Tamanho do cache
            cache_size = await self.redis.scard(self.cache_keys_set)
            
            # Taxa de acerto
            hits = metrics_decoded.get("cache_hits", 0) + metrics_decoded.get("similarity_hits", 0)
            misses = metrics_decoded.get("cache_misses", 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            # Análise de entradas mais acessadas
            top_entries = await self._get_top_accessed_entries(5)
            
            return {
                "metrics": metrics_decoded,
                "cache_size": cache_size,
                "max_size": self.max_cache_size,
                "hit_rate": round(hit_rate, 2),
                "local_cache_size": len(self.local_cache),
                "ttl_seconds": self.ttl,
                "top_accessed": top_entries
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def _find_similar_cached(
        self,
        prompt: str,
        system_message: str,
        model: str,
        temperature: float
    ) -> Optional[str]:
        """Busca respostas similares no cache"""
        try:
            # Busca todas as chaves do cache
            cache_keys = await self.redis.smembers(self.cache_keys_set)
            
            for key in cache_keys:
                cached_data = await self.redis.get(key)
                if cached_data:
                    entry = CacheEntry.from_dict(json.loads(cached_data))
                    
                    # Verifica se modelo e temperatura são compatíveis
                    if entry.model == model and abs(entry.temperature - temperature) < 0.1:
                        # Calcula similaridade simples
                        similarity = self._calculate_similarity(prompt, entry.prompt)
                        
                        if similarity >= self.similarity_threshold:
                            logger.debug(f"Found similar cached response (similarity: {similarity:.2f})")
                            return entry.response
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding similar cached: {e}")
            return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcula similaridade entre dois textos (versão simplificada)"""
        # Normaliza textos
        t1 = text1.lower().strip().split()
        t2 = text2.lower().strip().split()
        
        # Calcula Jaccard similarity
        intersection = len(set(t1) & set(t2))
        union = len(set(t1) | set(t2))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _update_local_cache(self, key: str, response: str):
        """Atualiza cache local"""
        # Remove entrada mais antiga se necessário
        if len(self.local_cache) >= self.local_cache_max_size:
            oldest_key = min(self.local_cache.keys(), 
                           key=lambda k: self.local_cache[k][1])
            del self.local_cache[oldest_key]
        
        self.local_cache[key] = (response, datetime.now())
    
    async def _enforce_cache_size_limit(self):
        """Garante que o cache não exceda o tamanho máximo"""
        try:
            cache_size = await self.redis.scard(self.cache_keys_set)
            
            if cache_size > self.max_cache_size:
                # Remove entradas mais antigas
                to_remove = cache_size - self.max_cache_size
                
                # Busca todas as chaves e suas datas
                entries_with_dates = []
                
                cache_keys = await self.redis.smembers(self.cache_keys_set)
                for key in cache_keys:
                    cached_data = await self.redis.get(key)
                    if cached_data:
                        entry = CacheEntry.from_dict(json.loads(cached_data))
                        entries_with_dates.append((key, entry.last_accessed))
                
                # Ordena por data de acesso
                entries_with_dates.sort(key=lambda x: x[1])
                
                # Remove as mais antigas
                for key, _ in entries_with_dates[:to_remove]:
                    await self.redis.delete(key)
                    await self.redis.srem(self.cache_keys_set, key)
                
                logger.info(f"Removed {to_remove} old cache entries")
                
        except Exception as e:
            logger.error(f"Error enforcing cache size limit: {e}")
    
    async def _get_top_accessed_entries(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna entradas mais acessadas"""
        try:
            entries = []
            cache_keys = await self.redis.smembers(self.cache_keys_set)
            
            for key in cache_keys:
                cached_data = await self.redis.get(key)
                if cached_data:
                    entry = CacheEntry.from_dict(json.loads(cached_data))
                    entries.append({
                        "prompt": entry.prompt[:50] + "...",
                        "hits": entry.hits,
                        "created_at": entry.created_at.isoformat(),
                        "last_accessed": entry.last_accessed.isoformat()
                    })
            
            # Ordena por hits
            entries.sort(key=lambda x: x["hits"], reverse=True)
            
            return entries[:limit]
            
        except Exception as e:
            logger.error(f"Error getting top entries: {e}")
            return []
    
    async def _increment_metric(self, metric: str):
        """Incrementa métrica"""
        try:
            await self.redis.hincrby(self.metrics_key, metric, 1)
        except Exception as e:
            logger.error(f"Error incrementing metric {metric}: {e}")
    
    async def warm_cache(self, common_prompts: List[Dict[str, Any]]):
        """Pré-aquece o cache com prompts comuns"""
        logger.info(f"Warming cache with {len(common_prompts)} common prompts")
        
        for prompt_data in common_prompts:
            await self.set(
                prompt=prompt_data["prompt"],
                response=prompt_data["response"],
                system_message=prompt_data.get("system_message", ""),
                model=prompt_data.get("model", ""),
                temperature=prompt_data.get("temperature", 0.0)
            )
        
        logger.info("Cache warming completed")

# Prompts comuns para pré-aquecer o cache
COMMON_PROMPTS = [
    {
        "prompt": "oi",
        "response": "Olá! Bem-vindo ao Jarvis Assistant. Como posso ajudá-lo hoje?",
        "system_message": "Você é o Agente de Recepção do Jarvis Assistant"
    },
    {
        "prompt": "olá",
        "response": "Olá! Sou o Jarvis, seu assistente virtual. Em que posso ajudar?",
        "system_message": "Você é o Agente de Recepção do Jarvis Assistant"
    },
    {
        "prompt": "menu",
        "response": """📋 **MENU PRINCIPAL**
        
Escolha uma opção:
• 📊 Dados e Relatórios
• 🔧 Suporte Técnico
• 📅 Agendamentos
• 💬 Falar com Atendente

Digite o número ou nome da opção desejada.""",
        "system_message": "Você é o Agente de Recepção do Jarvis Assistant"
    },
    {
        "prompt": "ajuda",
        "response": """🆘 **CENTRAL DE AJUDA**

Posso ajudar com:
• Consultas de dados e relatórios
• Problemas técnicos e suporte
• Agendamentos e reuniões
• Informações gerais

O que você precisa?""",
        "system_message": "Você é o Agente de Recepção do Jarvis Assistant"
    }
]