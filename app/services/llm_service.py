import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.config.llm_settings import llm_settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.ollama_url = llm_settings.ollama_base_url
        self.model = llm_settings.ollama_model
        self.temperature = llm_settings.temperature
        self.max_tokens = llm_settings.max_tokens
        self.timeout = llm_settings.timeout
        self.session = None
        self.memories = {}
        self.is_initialized = False
        
    async def initialize(self):
        """Inicializa conexão LLM com tratamento de erro melhorado"""
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            logger.info(f"🔧 Inicializando LLM Service...")
            logger.info(f"📍 Ollama URL: {self.ollama_url}")
            logger.info(f"🤖 Modelo: {self.model}")
            
            # Testa conexão com Ollama
            await self._test_ollama_connection()
            
            self.is_initialized = True
            logger.info(f"✅ LLM Service inicializado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar LLM Service: {e}")
            self.is_initialized = False
            # Não levanta exceção para permitir que o serviço inicie
            # mas marca como não inicializado
    
    async def _test_ollama_connection(self):
        """Testa conexão com Ollama com melhor tratamento de erro"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Tentativa {attempt + 1} de conectar ao Ollama...")
                
                # Teste 1: Verifica se Ollama está acessível
                async with self.session.get(f"{self.ollama_url}/api/tags") as response:
                    if response.status != 200:
                        raise Exception(f"Ollama tags endpoint retornou status {response.status}")
                    
                    tags_data = await response.json()
                    models = tags_data.get('models', [])
                    model_names = [m.get('name', '') for m in models]
                    
                    logger.info(f"Modelos disponíveis: {model_names}")
                    
                    if self.model not in model_names:
                        logger.warning(f"⚠️ Modelo {self.model} não encontrado. Usando primeiro disponível.")
                        if model_names:
                            self.model = model_names[0]
                            logger.info(f"Usando modelo: {self.model}")
                        else:
                            raise Exception("Nenhum modelo disponível no Ollama")
                
                # Sucesso
                return
                
            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} falhou: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise
    
    async def generate_response(
        self, 
        prompt: str, 
        system_message: str = None,
        session_id: str = None,
        context: Dict[str, Any] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Gera resposta com fallback em caso de erro"""
        
        if not self.is_initialized:
            logger.warning("LLM Service não inicializado, usando resposta padrão")
            return self._get_fallback_response(prompt)
        
        try:
            start_time = datetime.now()
            
            # Constrói mensagens
            messages = []
            
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # Adiciona contexto da sessão
            if session_id and session_id in self.memories:
                memory = self.memories[session_id]
                for msg in memory[-6:]:
                    messages.append(msg)
            
            # Adiciona contexto adicional
            if context:
                context_parts = []
                if "agent_info" in context:
                    context_parts.append(f"Agente atual: {context['agent_info'].get('name', 'Desconhecido')}")
                if "user_info" in context:
                    context_parts.append(f"Usuário: {context['user_info'].get('phone_number', 'Desconhecido')}")
                
                if context_parts:
                    context_str = "Contexto: " + ", ".join(context_parts)
                    messages.append({"role": "system", "content": context_str})
            
            # Adiciona prompt atual
            messages.append({"role": "user", "content": prompt})
            
            # Prepara payload
            url = f"{self.ollama_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature or self.temperature,
                    "num_predict": max_tokens or self.max_tokens,
                    "top_k": 40,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }
            
            # Faz requisição
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Erro Ollama (status {response.status}): {text}")
                    return self._get_fallback_response(prompt)
                
                result = await response.json()
                
                if "error" in result:
                    logger.error(f"Ollama error: {result['error']}")
                    return self._get_fallback_response(prompt)
                
                content = result.get("message", {}).get("content", "")
                if not content:
                    return self._get_fallback_response(prompt)
                
                # Salva na memória
                if session_id:
                    if session_id not in self.memories:
                        self.memories[session_id] = []
                    self.memories[session_id].append({"role": "user", "content": prompt})
                    self.memories[session_id].append({"role": "assistant", "content": content})
                    self._trim_memory(session_id)
                
                return content.strip()
                
        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {e}", exc_info=True)
            return self._get_fallback_response(prompt)
    
    def _get_fallback_response(self, prompt: str) -> str:
        """Resposta fallback quando LLM não está disponível"""
        prompt_lower = prompt.lower()
        
        # Respostas padrão baseadas em palavras-chave
        if any(word in prompt_lower for word in ["oi", "olá", "bom dia", "boa tarde", "boa noite"]):
            return """Olá! 👋 Bem-vindo ao Jarvis Assistant!

Sou seu assistente virtual e posso ajudar com:
- 📊 Dados e Relatórios
- 🔧 Suporte Técnico
- 📅 Agendamentos
- 💬 Informações Gerais

Como posso ajudar você hoje?"""
        
        elif any(word in prompt_lower for word in ["menu", "opções", "ajuda"]):
            return """📋 MENU PRINCIPAL

Escolha uma opção:
- 📊 Dados e Relatórios - Digite "dados"
- 🔧 Suporte Técnico - Digite "suporte"
- 📅 Agendamentos - Digite "agendar"
- 💬 Falar com Atendente - Digite "atendente"

O que você precisa?"""
        
        elif any(word in prompt_lower for word in ["dados", "relatório", "dashboard"]):
            return """📊 Para acessar dados e relatórios, estou conectando você com nosso analista de dados.

Você pode solicitar:
- Relatórios de vendas
- Dashboard executivo
- Análises de clientes
- Métricas de performance

O que você gostaria de ver?"""
        
        elif any(word in prompt_lower for word in ["erro", "problema", "bug", "suporte"]):
            return """🔧 Entendi que você está com um problema técnico.

Para ajudar melhor, por favor descreva:
- Qual erro está ocorrendo?
- Quando começou?
- O que você estava tentando fazer?

Vou criar um ticket de suporte para você."""
        
        else:
            return """Desculpe, estou com algumas limitações no momento, mas posso ajudar com:

- 📊 Dados e Relatórios
- 🔧 Suporte Técnico
- 📅 Agendamentos
- 💬 Informações Gerais

Digite "menu" para ver todas as opções ou me diga como posso ajudar!"""
    
    async def classify_intent(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Classifica intenção com fallback"""
        
        if self.is_initialized:
            system_prompt = """Classifique a mensagem em uma destas categorias:
- "reception": saudações, cumprimentos
- "data_query": dados, relatórios, métricas
- "technical_support": problemas, erros, bugs
- "scheduling": agendamentos, reuniões
- "general_chat": outros

Responda APENAS em JSON: {"intent": "categoria", "confidence": 0.0-1.0, "reasoning": "explicação"}"""

            try:
                response = await self.generate_response(
                    f"Classifique: '{message}'",
                    system_prompt,
                    session_id,
                    temperature=0.3,
                    max_tokens=150
                )
                
                # Tenta extrair JSON
                response = response.replace("```json", "").replace("```", "").strip()
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = response[start:end]
                    result = json.loads(json_str)
                    
                    if all(key in result for key in ["intent", "confidence"]):
                        result["confidence"] = float(result["confidence"])
                        return result
                        
            except Exception as e:
                logger.error(f"Erro na classificação LLM: {e}")
        
        # Fallback com classificação por palavras-chave
        return self._classify_by_keywords(message)
    
    def _classify_by_keywords(self, message: str) -> Dict[str, Any]:
        """Classificação fallback por palavras-chave"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["oi", "olá", "bom dia", "boa tarde", "boa noite"]):
            return {"intent": "reception", "confidence": 0.9, "reasoning": "Saudação detectada"}
        elif any(word in message_lower for word in ["relatório", "dados", "dashboard", "vendas"]):
            return {"intent": "data_query", "confidence": 0.8, "reasoning": "Consulta de dados"}
        elif any(word in message_lower for word in ["erro", "problema", "bug", "não funciona"]):
            return {"intent": "technical_support", "confidence": 0.8, "reasoning": "Problema técnico"}
        elif any(word in message_lower for word in ["agendar", "reunião", "marcar"]):
            return {"intent": "scheduling", "confidence": 0.8, "reasoning": "Agendamento"}
        else:
            return {"intent": "general_chat", "confidence": 0.5, "reasoning": "Conversa geral"}
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Retorna status do serviço"""
        status = {
            "service": "LLM Service",
            "ollama_url": self.ollama_url,
            "model": self.model,
            "status": "offline",
            "initialized": self.is_initialized,
            "active_sessions": len(self.memories),
            "fallback_mode": not self.is_initialized,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.is_initialized and self.session:
            try:
                async with self.session.get(
                    f"{self.ollama_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        status["status"] = "online"
                        data = await response.json()
                        status["available_models"] = [m.get('name', '') for m in data.get('models', [])]
                        status["model_available"] = self.model in status["available_models"]
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)
        
        return status
    
    def _trim_memory(self, session_id: str, max_messages: int = 10):
        """Mantém apenas as últimas N mensagens"""
        if session_id in self.memories and len(self.memories[session_id]) > max_messages:
            self.memories[session_id] = self.memories[session_id][-max_messages:]
    
    async def cleanup(self):
        """Limpa recursos"""
        if self.session:
            await self.session.close()
        self.memories.clear()
        self.is_initialized = False
        logger.info("LLM Service cleaned up")