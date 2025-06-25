import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import traceback
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
        self.connection_error = None
        self.last_test_time = None
        self.last_test_result = None
        
    async def initialize(self):
        """Inicializa conexão LLM com tratamento de erro melhorado"""
        try:
            logger.info("="*60)
            logger.info("🔧 Inicializando LLM Service...")
            logger.info(f"📍 Ollama URL: {self.ollama_url}")
            logger.info(f"🤖 Modelo Configurado: {self.model}")
            logger.info(f"🌡️ Temperature: {self.temperature}")
            logger.info(f"📏 Max Tokens: {self.max_tokens}")
            logger.info(f"⏱️ Timeout: {self.timeout}s")
            logger.info("="*60)
            
            # Cria sessão HTTP
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout_config)
            
            # Testa conexão com Ollama
            connection_ok = await self._test_ollama_connection()
            
            if connection_ok:
                self.is_initialized = True
                logger.info("✅ LLM Service inicializado com sucesso!")
                logger.info(f"✅ Modelo {self.model} está disponível e funcionando")
            else:
                self.is_initialized = False
                logger.warning("⚠️ LLM Service inicializado em modo fallback (Ollama não disponível)")
                
        except Exception as e:
            logger.error(f"❌ Erro crítico ao inicializar LLM Service: {e}")
            logger.error(traceback.format_exc())
            self.is_initialized = False
            self.connection_error = str(e)
    
    async def _test_ollama_connection(self):
        """Testa conexão com Ollama com debug detalhado"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔍 Tentativa {attempt + 1}/{max_retries} de conectar ao Ollama...")
                
                # Teste 1: Verifica se endpoint está acessível
                test_url = f"{self.ollama_url}/api/tags"
                logger.debug(f"Testing URL: {test_url}")
                
                async with self.session.get(test_url) as response:
                    logger.debug(f"Response status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"❌ Ollama retornou status {response.status}: {error_text}")
                        raise Exception(f"Ollama endpoint returned status {response.status}")
                    
                    tags_data = await response.json()
                    models = tags_data.get('models', [])
                    model_names = [m.get('name', '') for m in models]
                    
                    logger.info(f"📋 Modelos disponíveis no Ollama: {model_names}")
                    
                    # Verifica se o modelo configurado existe
                    if self.model not in model_names:
                        logger.warning(f"⚠️ Modelo {self.model} não encontrado!")
                        if model_names:
                            # Tenta usar um modelo alternativo
                            for preferred in ['llama3.1:8b', 'llama3:latest', 'llama2:latest']:
                                if preferred in model_names:
                                    self.model = preferred
                                    logger.info(f"✅ Usando modelo alternativo: {self.model}")
                                    break
                            else:
                                # Usa o primeiro disponível
                                self.model = model_names[0]
                                logger.info(f"✅ Usando primeiro modelo disponível: {self.model}")
                        else:
                            raise Exception("Nenhum modelo disponível no Ollama")
                
                # Teste 2: Tenta fazer uma chamada simples
                logger.info("🧪 Testando geração com o modelo...")
                test_payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 10
                    }
                }
                
                test_url = f"{self.ollama_url}/api/chat"
                async with self.session.post(test_url, json=test_payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Teste de geração bem-sucedido!")
                        self.last_test_time = datetime.now()
                        self.last_test_result = "success"
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Falha no teste de geração: {error_text}")
                        self.last_test_result = f"generation_failed: {response.status}"
                
            except aiohttp.ClientError as e:
                logger.error(f"❌ Erro de conexão (tentativa {attempt + 1}): {type(e).__name__}: {str(e)}")
                self.connection_error = f"Connection error: {str(e)}"
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout ao conectar com Ollama (tentativa {attempt + 1})")
                self.connection_error = "Timeout connecting to Ollama"
                
            except Exception as e:
                logger.error(f"❌ Erro inesperado (tentativa {attempt + 1}): {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                self.connection_error = str(e)
            
            if attempt < max_retries - 1:
                logger.info(f"⏳ Aguardando {retry_delay}s antes da próxima tentativa...")
                await asyncio.sleep(retry_delay)
        
        logger.error("❌ Todas as tentativas de conexão com Ollama falharam!")
        return False
    
    async def generate_response(
        self, 
        prompt: str, 
        system_message: str = None,
        session_id: str = None,
        context: Dict[str, Any] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Gera resposta com fallback robusto"""
        
        logger.debug(f"📝 Generating response for prompt: {prompt[:50]}...")
        
        # Se não está inicializado ou Ollama não está disponível, usa fallback
        if not self.is_initialized or not self.session:
            logger.warning("⚠️ LLM não inicializado, usando fallback")
            return self._get_fallback_response(prompt)
        
        try:
            start_time = datetime.now()
            
            # Constrói mensagens
            messages = []
            
            if system_message:
                messages.append({"role": "system", "content": system_message})
                logger.debug(f"System message: {system_message[:100]}...")
            
            # Adiciona contexto da sessão
            if session_id and session_id in self.memories:
                memory = self.memories[session_id]
                # Pega apenas as últimas 6 mensagens para não exceder o contexto
                for msg in memory[-6:]:
                    messages.append(msg)
                logger.debug(f"Added {len(memory[-6:])} messages from memory")
            
            # Adiciona contexto adicional
            if context:
                context_parts = []
                if "agent_info" in context:
                    agent_name = context['agent_info'].get('name', 'Desconhecido')
                    context_parts.append(f"Você está atuando como: {agent_name}")
                if "user_info" in context:
                    phone = context['user_info'].get('phone_number', 'Desconhecido')
                    context_parts.append(f"Conversando com: {phone}")
                
                if context_parts:
                    context_str = "\n".join(context_parts)
                    messages.append({"role": "system", "content": context_str})
                    logger.debug(f"Added context: {context_str}")
            
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
            
            logger.debug(f"🚀 Sending request to Ollama...")
            logger.debug(f"URL: {url}")
            logger.debug(f"Model: {self.model}")
            
            # Faz requisição
            async with self.session.post(url, json=payload) as response:
                response_text = await response.text()
                logger.debug(f"Response status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"❌ Erro Ollama (status {response.status}): {response_text}")
                    return self._get_fallback_response(prompt)
                
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"❌ Invalid JSON response: {response_text[:200]}...")
                    return self._get_fallback_response(prompt)
                
                if "error" in result:
                    logger.error(f"❌ Ollama error: {result['error']}")
                    return self._get_fallback_response(prompt)
                
                content = result.get("message", {}).get("content", "")
                if not content:
                    logger.error("❌ Empty response from Ollama")
                    return self._get_fallback_response(prompt)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ LLM response generated in {elapsed:.2f}s")
                logger.debug(f"Response preview: {content[:100]}...")
                
                # Salva na memória da sessão
                if session_id:
                    if session_id not in self.memories:
                        self.memories[session_id] = []
                    self.memories[session_id].append({"role": "user", "content": prompt})
                    self.memories[session_id].append({"role": "assistant", "content": content})
                    self._trim_memory(session_id)
                
                return content.strip()
                
        except aiohttp.ClientError as e:
            logger.error(f"❌ Network error: {type(e).__name__}: {str(e)}")
            return self._get_fallback_response(prompt)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout após {self.timeout}s")
            return self._get_fallback_response(prompt)
            
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao gerar resposta: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return self._get_fallback_response(prompt)
    
    def _get_fallback_response(self, prompt: str) -> str:
        """Resposta fallback melhorada quando LLM não está disponível"""
        logger.info(f"🔄 Using fallback response for: {prompt[:50]}...")
        prompt_lower = prompt.lower()
        # Respostas mais naturais e variadas
        greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "opa", "eae", "e ai"]
        if any(word in prompt_lower for word in greetings):
            responses = [
                "Oi! Tudo bem? 😊 Como posso te ajudar hoje?",
                "Opa! Que bom te ver por aqui! O que você precisa?",
                "Oi oi! Como você tá? Precisa de alguma coisa?",
                "Hey! Tudo certo? Me conta como posso ajudar!",
                "Olá! Seja bem-vindo(a)! Em que posso ser útil?"
            ]
            import random
            return random.choice(responses)
        elif any(word in prompt_lower for word in ["menu", "opções", "opcoes", "ajuda", "o que você faz", "comandos"]):
            return """Claro! Eu posso te ajudar com várias coisas:

📊 *Dados e Relatórios* - Vendas, métricas, dashboards
🛠️ *Suporte Técnico* - Problemas, erros, dúvidas
📅 *Agendamentos* - Reuniões, compromissos
💬 *Bate-papo* - Qualquer outra coisa!

O que você precisa? 😊"""
        elif any(word in prompt_lower for word in ["dados", "relatório", "relatorio", "vendas", "dashboard", "métrica", "metrica", "kpi", "analise", "análise"]):
            return """Legal! Vou puxar essas informações pra você! 📊

Você quer ver:
- Vendas do mês?
- Comparativo com mês anterior?
- Performance geral?
- Ou algum dado específico?

Me conta o que precisa!"""
        elif any(word in prompt_lower for word in ["erro", "problema", "bug", "não funciona", "nao funciona", "travou", "lento", "falha"]):
            return """Poxa, que chato! Vamos resolver isso juntos 🛠️

Me conta:
- O que aconteceu exatamente?
- Quando começou o problema?
- Já tentou reiniciar?

Com essas infos consigo te ajudar melhor!"""
        elif any(word in prompt_lower for word in ["agendar", "marcar", "reunião", "reuniao", "horário", "horario", "agenda"]):
            return """📅 Vamos agendar!

Me diz:
- Que tipo de compromisso?
- Qual dia seria melhor?
- Tem horário preferido?

Vou verificar a disponibilidade pra você!"""
        elif any(word in prompt_lower for word in ["obrigado", "obrigada", "valeu", "thanks", "brigado", "agradeço"]):
            responses = [
                "Por nada! Sempre que precisar, tô aqui! 😊",
                "Imagina! Foi um prazer ajudar! 🤗",
                "Que isso! Conta comigo sempre! ✨",
                "De nada! Volte sempre que precisar!"
            ]
            import random
            return random.choice(responses)
        elif any(word in prompt_lower for word in ["tchau", "até", "ate", "adeus", "bye", "xau", "flw", "falou"]):
            responses = [
                "Tchau! Foi ótimo falar com você! Até mais! 👋",
                "Até logo! Se cuida! 😊",
                "Valeu pela conversa! Até a próxima! ✨",
                "Tchau tchau! Volte sempre! 🤗"
            ]
            import random
            return random.choice(responses)
        elif any(word in prompt_lower for word in ["teste", "testando", "test"]):
            return "🧪 Teste recebido! Estou funcionando perfeitamente! Como posso ajudar?"
        else:
            # Resposta genérica mais natural
            responses = [
                "Hmm, não entendi muito bem... Pode me explicar de outro jeito? 😊",
                "Opa, acho que não captei. Pode dar mais detalhes?",
                "Desculpa, não entendi direito. Você quer dados, suporte ou marcar algo?",
                "Poxa, não peguei bem o que você precisa. Me conta mais?",
                "Interessante! Mas não entendi completamente. Pode elaborar um pouco mais?"
            ]
            import random
            return random.choice(responses)
    
    async def classify_intent(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Classifica intenção com fallback robusto"""
        logger.debug(f"🎯 Classifying intent for: {message[:50]}...")
        
        if self.is_initialized and self.session:
            system_prompt = """Você é um classificador de intenções. Analise a mensagem e classifique em uma destas categorias:
- "reception": saudações, cumprimentos, despedidas
- "data_query": dados, relatórios, métricas, análises
- "technical_support": problemas, erros, bugs, suporte
- "scheduling": agendamentos, reuniões, calendário
- "general_chat": outros assuntos

Responda APENAS em JSON: {"intent": "categoria", "confidence": 0.0-1.0, "reasoning": "breve explicação"}"""

            try:
                response = await self.generate_response(
                    f"Classifique esta mensagem: '{message}'",
                    system_prompt,
                    session_id,
                    temperature=0.3,
                    max_tokens=150
                )
                
                logger.debug(f"Classification response: {response}")
                
                # Tenta extrair JSON da resposta
                response = response.strip()
                
                # Remove formatação markdown se houver
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0].strip()
                
                # Encontra o JSON na resposta
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = response[start:end]
                    result = json.loads(json_str)
                    
                    # Valida estrutura
                    if all(key in result for key in ["intent", "confidence"]):
                        result["confidence"] = float(result["confidence"])
                        logger.info(f"✅ Intent classified: {result['intent']} (confidence: {result['confidence']})")
                        return result
                
                logger.warning("Failed to parse LLM classification response, using fallback")
                        
            except Exception as e:
                logger.error(f"❌ Erro na classificação LLM: {type(e).__name__}: {str(e)}")
        
        # Fallback com classificação por palavras-chave
        logger.info("🔄 Using keyword-based classification")
        return self._classify_by_keywords(message)
    
    def _classify_by_keywords(self, message: str) -> Dict[str, Any]:
        """Classificação fallback por palavras-chave melhorada"""
        message_lower = message.lower()
        
        # Padrões mais abrangentes
        patterns = {
            "reception": {
                "keywords": ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "opa", 
                           "e ai", "eai", "fala", "alô", "alo", "prezado", "caro", "tchau", "até",
                           "obrigado", "valeu", "flw", "falou"],
                "confidence": 0.95
            },
            "data_query": {
                "keywords": ["relatório", "relatorio", "dados", "dashboard", "vendas", "faturamento", 
                           "métrica", "metrica", "kpi", "números", "numeros", "estatística", 
                           "estatistica", "análise", "analise", "gráfico", "grafico", "planilha",
                           "excel", "csv", "exportar", "resultado", "performance", "indicador"],
                "confidence": 0.85
            },
            "technical_support": {
                "keywords": ["erro", "problema", "bug", "não funciona", "nao funciona", "travou", 
                           "lento", "parou", "ajuda técnica", "suporte", "falha", "crash", "down",
                           "offline", "timeout", "conexão", "conexao", "acesso negado", "senha",
                           "login", "autenticação", "autenticacao", "permissão", "permissao"],
                "confidence": 0.85
            },
            "scheduling": {
                "keywords": ["agendar", "marcar", "reunião", "reuniao", "horário", "horario", 
                           "calendário", "calendario", "compromisso", "disponibilidade", "agenda",
                           "remarcar", "cancelar", "adiar", "confirmar", "meeting", "call",
                           "videoconferência", "videoconferencia"],
                "confidence": 0.85
            }
        }
        
        # Verifica cada padrão
        for intent, pattern in patterns.items():
            if any(keyword in message_lower for keyword in pattern["keywords"]):
                reasoning = f"Detectada palavra-chave relacionada a {intent}"
                logger.info(f"✅ Keyword match for intent: {intent}")
                return {
                    "intent": intent,
                    "confidence": pattern["confidence"],
                    "reasoning": reasoning
                }
        
        # Se não encontrar padrão claro, classifica como general_chat
        logger.info("ℹ️ No clear pattern found, classifying as general_chat")
        return {
            "intent": "general_chat",
            "confidence": 0.5,
            "reasoning": "Nenhum padrão específico detectado"
        }
    
    def _trim_memory(self, session_id: str, max_messages: int = 10):
        """Mantém apenas as últimas N mensagens na memória"""
        if session_id in self.memories and len(self.memories[session_id]) > max_messages:
            self.memories[session_id] = self.memories[session_id][-max_messages:]
            logger.debug(f"Trimmed memory for session {session_id} to {max_messages} messages")
    
    async def cleanup(self):
        """Limpa recursos"""
        logger.info("🧹 Cleaning up LLM Service...")
        
        if self.session:
            await self.session.close()
            
        self.memories.clear()
        self.is_initialized = False
        
        logger.info("✅ LLM Service cleaned up")

    async def get_service_status(self) -> Dict[str, Any]:
        """Retorna status detalhado do serviço LLM"""
        try:
            status = {
                "status": "online" if self.is_initialized else "offline",
                "initialized": self.is_initialized,
                "ollama_url": self.ollama_url,
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "timeout": self.timeout,
                "timestamp": datetime.now().isoformat(),
                "memory_sessions": len(self.memories),
                "connection_error": self.connection_error,
                "last_test": {
                    "time": self.last_test_time.isoformat() if self.last_test_time else None,
                    "result": self.last_test_result
                }
            }
            
            # Testa conexão atual se inicializado
            if self.is_initialized and self.session:
                try:
                    # Teste rápido de conectividade
                    test_start = datetime.now()
                    async with self.session.get(
                        f"{self.ollama_url}/api/tags", 
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            models = [m.get('name', '') for m in data.get('models', [])]
                            status["available_models"] = models
                            status["model_available"] = self.model in models
                            status["connectivity"] = "connected"
                            status["ping_ms"] = int((datetime.now() - test_start).total_seconds() * 1000)
                        else:
                            status["connectivity"] = "error"
                            status["connectivity_error"] = f"HTTP {response.status}"
                except asyncio.TimeoutError:
                    status["connectivity"] = "timeout"
                except Exception as e:
                    status["connectivity"] = "error"
                    status["connectivity_error"] = str(e)
            else:
                status["connectivity"] = "not_initialized"
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }