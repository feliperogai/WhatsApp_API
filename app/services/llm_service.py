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
        # Usa configurações do llm_settings
        self.ollama_url = llm_settings.ollama_base_url
        self.model = llm_settings.ollama_model
        self.temperature = llm_settings.temperature
        self.max_tokens = llm_settings.max_tokens
        self.timeout = llm_settings.timeout
        self.session = None
        self.memories = {}  # Store conversation memories per session
        self.is_initialized = False
        
    async def initialize(self):
        """Inicializa conexão LLM"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            # Log configuração
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
            raise
    
    async def _test_ollama_connection(self):
        """Testa conexão com Ollama usando configuração exata"""
        try:
            # Teste 1: Verifica se Ollama está acessível
            logger.debug(f"Testando conexão com {self.ollama_url}/api/tags")
            async with self.session.get(f"{self.ollama_url}/api/tags") as response:
                if response.status != 200:
                    raise Exception(f"Ollama tags endpoint retornou status {response.status}")
                
                tags_data = await response.json()
                logger.debug(f"Modelos disponíveis: {[m.get('name', '') for m in tags_data.get('models', [])]}")
            
            # Teste 2: Verifica se o modelo está disponível
            models = tags_data.get('models', [])
            model_names = [m.get('name', '') for m in models]
            if self.model not in model_names:
                logger.warning(f"⚠️ Modelo {self.model} não encontrado. Modelos disponíveis: {model_names}")
            
            # Teste 3: Testa chat endpoint
            logger.debug(f"Testando chat com modelo {self.model}")
            url = f"{self.ollama_url}/api/chat"
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Responda apenas: OK"}],
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": 10  # Limita resposta para teste
                }
            }
            
            async with self.session.post(url, json=test_payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Ollama chat falhou: {response.status} - {text}")
                
                result = await response.json()
                if "message" not in result or "content" not in result["message"]:
                    raise Exception(f"Formato de resposta inválido: {result}")
                
                test_response = result["message"]["content"]
                logger.debug(f"Teste OK - Resposta: {test_response}")
                    
        except Exception as e:
            logger.error(f"Falha no teste de conexão Ollama: {e}")
            raise
    
    def get_memory(self, session_id: str) -> List[Dict]:
        """Obtém ou cria memória para sessão"""
        if session_id not in self.memories:
            self.memories[session_id] = []
        return self.memories[session_id]
    
    def _trim_memory(self, session_id: str, max_messages: int = 10):
        """Mantém apenas as últimas N mensagens na memória"""
        if session_id in self.memories and len(self.memories[session_id]) > max_messages:
            self.memories[session_id] = self.memories[session_id][-max_messages:]
    
    async def generate_response(
        self, 
        prompt: str, 
        system_message: str = None,
        session_id: str = None,
        context: Dict[str, Any] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Gera resposta usando Ollama com configuração otimizada"""
        
        if not self.is_initialized:
            logger.error("LLM Service não inicializado!")
            return "Desculpe, o serviço de IA está iniciando. Tente novamente em alguns instantes."
        
        try:
            start_time = datetime.now()
            
            # Constrói mensagens
            messages = []
            
            # Adiciona mensagem do sistema
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # Adiciona contexto da sessão (histórico de conversa)
            if session_id and session_id in self.memories:
                memory = self.memories[session_id]
                # Adiciona apenas as últimas mensagens para não exceder contexto
                for msg in memory[-6:]:  # Últimas 6 mensagens (3 turnos)
                    messages.append(msg)
            
            # Adiciona contexto adicional como mensagem do sistema
            if context:
                # Formata contexto de forma legível
                context_parts = []
                if "agent_info" in context:
                    context_parts.append(f"Agente atual: {context['agent_info'].get('name', 'Desconhecido')}")
                if "user_info" in context:
                    context_parts.append(f"Usuário: {context['user_info'].get('phone_number', 'Desconhecido')}")
                
                if context_parts:
                    context_str = "Contexto da conversa: " + ", ".join(context_parts)
                    messages.append({"role": "system", "content": context_str})
            
            # Adiciona prompt atual
            messages.append({"role": "user", "content": prompt})
            
            # Prepara payload para Ollama
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
            
            # Log para debug
            logger.debug(f"Enviando para Ollama: {len(messages)} mensagens")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            # Faz requisição para Ollama
            async with self.session.post(url, json=payload) as response:
                response_time = (datetime.now() - start_time).total_seconds()
                
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Erro Ollama (status {response.status}): {text}")
                    raise Exception(f"Ollama API error: {response.status}")
                
                result = await response.json()
                
                # Valida resposta
                if "error" in result:
                    raise Exception(f"Ollama error: {result['error']}")
                
                if "message" not in result or "content" not in result["message"]:
                    raise Exception(f"Formato de resposta inválido")
                
                content = result["message"]["content"]
                
                # Estatísticas
                total_duration = result.get("total_duration", 0) / 1e9  # Converte para segundos
                eval_count = result.get("eval_count", 0)
                
                logger.info(f"✅ Resposta gerada em {response_time:.2f}s - {eval_count} tokens")
                
                # Salva na memória da sessão
                if session_id:
                    memory = self.get_memory(session_id)
                    memory.append({"role": "user", "content": prompt})
                    memory.append({"role": "assistant", "content": content})
                    self._trim_memory(session_id)
                
                return content.strip()
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout ao gerar resposta (>{self.timeout}s)")
            return "Desculpe, a resposta está demorando muito. Por favor, tente novamente."
            
        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {e}", exc_info=True)
            return "Desculpe, estou com dificuldades técnicas no momento. Tente novamente em alguns instantes."
    
    async def classify_intent(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Classifica intenção da mensagem usando LLM"""
        
        system_prompt = """Você é um classificador de intenções especializado.

Analise a mensagem e classifique em EXATAMENTE uma destas categorias:

1. "reception" - Saudações, cumprimentos, apresentações, início de conversa (oi, olá, bom dia, etc)
2. "data_query" - Consultas sobre dados, relatórios, dashboards, KPIs, métricas, vendas, faturamento
3. "technical_support" - Problemas técnicos, erros, bugs, suporte, sistema não funciona, travou
4. "scheduling" - Agendamentos, reuniões, calendário, marcar horário, compromissos
5. "general_chat" - Qualquer outra coisa, conversa geral, agradecimentos, despedidas

IMPORTANTE: Responda APENAS em JSON puro, sem texto adicional:
{"intent": "categoria_escolhida", "confidence": 0.0-1.0, "reasoning": "breve explicação"}"""

        try:
            # Gera classificação
            response = await self.generate_response(
                f"Classifique esta mensagem: '{message}'",
                system_prompt,
                session_id,
                temperature=0.3,  # Baixa temperatura para classificação consistente
                max_tokens=150
            )
            
            # Tenta extrair JSON da resposta
            # Remove possível markdown
            response = response.replace("```json", "").replace("```", "").strip()
            
            # Encontra JSON na resposta
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)
                
                # Valida estrutura
                if all(key in result for key in ["intent", "confidence", "reasoning"]):
                    # Garante que confidence é float
                    result["confidence"] = float(result["confidence"])
                    return result
                    
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON de classificação: {e}")
            logger.debug(f"Resposta original: {response}")
        except Exception as e:
            logger.error(f"Erro na classificação de intenção: {e}")
        
        # Fallback com classificação básica por palavras-chave
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["oi", "olá", "bom dia", "boa tarde", "boa noite", "hello", "hi"]):
            intent = "reception"
            confidence = 0.8
        elif any(word in message_lower for word in ["relatório", "dados", "dashboard", "vendas", "faturamento", "kpi"]):
            intent = "data_query"
            confidence = 0.7
        elif any(word in message_lower for word in ["erro", "problema", "bug", "travou", "não funciona", "suporte"]):
            intent = "technical_support"
            confidence = 0.7
        elif any(word in message_lower for word in ["agendar", "reunião", "marcar", "horário", "calendário"]):
            intent = "scheduling"
            confidence = 0.7
        else:
            intent = "general_chat"
            confidence = 0.5
        
        return {
            "intent": intent,
            "confidence": confidence,
            "reasoning": "Classificação por palavras-chave (fallback)"
        }
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Retorna status detalhado do serviço LLM"""
        status = {
            "service": "LLM Service",
            "ollama_url": self.ollama_url,
            "model": self.model,
            "status": "offline",
            "initialized": self.is_initialized,
            "active_sessions": len(self.memories),
            "total_memories": sum(len(m) for m in self.memories.values()),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timestamp": datetime.now().isoformat()
        }
        
        # Testa conexão atual
        if self.is_initialized and self.session:
            try:
                # Teste rápido
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
    
    async def cleanup(self):
        """Limpa recursos e fecha conexões"""
        logger.info("🧹 Limpando recursos do LLM Service...")
        
        if self.session:
            await self.session.close()
        
        # Limpa memórias
        self.memories.clear()
        self.is_initialized = False
        
        logger.info("✅ LLM Service limpo com sucesso")
        
    def reset_session_memory(self, session_id: str):
        """Reseta memória de uma sessão específica"""
        if session_id in self.memories:
            del self.memories[session_id]
            logger.info(f"Memória resetada para sessão: {session_id}")
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """Retorna histórico de uma sessão"""
        return self.memories.get(session_id, [])