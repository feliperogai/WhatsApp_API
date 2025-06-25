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
        """Resposta fallback natural e variada quando LLM não está disponível"""
        logger.info(f"🔄 Using fallback response for: {prompt[:50]}...")
        prompt_lower = prompt.lower()
        import random
        
        # Respostas mais naturais e variadas por categoria
        
        # Saudações
        greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "opa", "eae", "e ai", "fala", "salve"]
        if any(word in prompt_lower for word in greetings):
            responses = [
                "Opa! E aí, tudo bem? 😊",
                "Oi oi! Como você tá?",
                "Fala! Tudo certo aí?",
                "Hey! Que bom te ver por aqui!",
                "Oi! Tava esperando você aparecer! Como tá?",
                "E aí! Beleza? Como posso ajudar?",
                "Salve! Tudo tranquilo?",
                "Olá! Como tá seu dia hoje?",
                "Opa, tudo bem? Que legal você por aqui!"
            ]
            # Para horários específicos
            from datetime import datetime
            hour = datetime.now().hour
            if 5 <= hour < 12 and "bom dia" in prompt_lower:
                responses.extend([
                    "Bom dia! Acordou cedo hein! Como tá?",
                    "Bom dia! ☀️ Já tomou café?",
                    "Bom dia! Que seu dia seja incrível!"
                ])
            elif 12 <= hour < 18 and "boa tarde" in prompt_lower:
                responses.extend([
                    "Boa tarde! Como foi sua manhã?",
                    "Boa tarde! Tá calor aí?",
                    "Boa tarde! Já almoçou?"
                ])
            elif "boa noite" in prompt_lower:
                responses.extend([
                    "Boa noite! Como foi seu dia?",
                    "Boa noite! 🌙 Tudo bem?",
                    "Boa noite! Ainda trabalhando?"
                ])
            return random.choice(responses)
        
        # Pedidos de ajuda/serviços
        elif any(word in prompt_lower for word in ["ajuda", "ajudar", "serviço", "serviços", "o que você faz", "pode fazer", "consegue"]):
            responses = [
                "Claro! Eu ajudo com várias coisas: relatórios, dados da empresa, problemas técnicos, agendamentos... O que você precisa?",
                "Opa, tô aqui pra isso! Posso puxar relatórios, resolver problemas técnicos, marcar reuniões... Me conta o que precisa!",
                "Ah, eu faço um monte de coisa! Dados, suporte, agenda... Mas me diz, o que tá precisando agora?",
                "Consigo te ajudar com relatórios e dados, resolver problemas técnicos, organizar agenda... O que seria bom pra você?"
            ]
            return random.choice(responses)
        
        # Menu (pessoa insiste em formato menu)
        elif "menu" in prompt_lower:
            responses = [
                "Então, não tenho bem um 'menu' haha, mas posso te ajudar com dados e relatórios, problemas técnicos, agendamentos... O que você precisa?",
                "Menu? 😄 Bom, eu ajudo com relatórios da empresa, suporte técnico, marco reuniões... Qual dessas coisas você tá precisando?",
                "Hmm menu... Deixa eu pensar! Faço relatórios, resolvo bugs, organizo agenda... Te interessa alguma coisa específica?"
            ]
            return random.choice(responses)
        
        # Dados/Relatórios
        elif any(word in prompt_lower for word in ["dados", "relatório", "relatorio", "vendas", "dashboard", "métrica", "kpi"]):
            responses = [
                "Ah, você quer ver dados! Legal! Me conta mais: vendas, clientes, performance... O que seria útil pra você?",
                "Show! Adoro mostrar números! 📊 Quer ver vendas? Clientes? Ou alguma métrica específica?",
                "Opa, vamos aos dados! O que você quer saber? Vendas do mês? Comparativo? Performance?",
                "Relatórios! Boa! Temos várias opções... Vendas, clientes, KPIs... Por onde quer começar?"
            ]
            return random.choice(responses)
        
        # Problemas técnicos
        elif any(word in prompt_lower for word in ["erro", "problema", "bug", "não funciona", "travou", "lento"]):
            responses = [
                "Eita, que chato! Me conta direitinho o que tá acontecendo que eu te ajudo!",
                "Poxa, problema técnico é fogo! O que tá dando erro aí?",
                "Xiii, vamos resolver isso! Me explica o que aconteceu?",
                "Problema? Calma que a gente resolve! O que tá pegando?"
            ]
            return random.choice(responses)
        
        # Agendamentos
        elif any(word in prompt_lower for word in ["agendar", "marcar", "reunião", "horário", "agenda"]):
            responses = [
                "Beleza! Vamos marcar! Que tipo de compromisso você quer agendar?",
                "Show! Me conta: é reunião? Call? Presencial? Quando seria bom?",
                "Opa, vamos organizar sua agenda! O que precisa marcar?",
                "Legal! Agendamento! É reunião de trabalho? Me dá mais detalhes!"
            ]
            return random.choice(responses)
        
        # Agradecimentos
        elif any(word in prompt_lower for word in ["obrigado", "obrigada", "valeu", "thanks", "agradeço"]):
            responses = [
                "Imagina! Sempre que precisar! 😊",
                "Por nada! Foi um prazer!",
                "Que isso! Tamo junto! 🤝",
                "De nada! Conta comigo!",
                "Valeu você! Fico feliz em ajudar!",
                "Nada! Precisando, só chamar!"
            ]
            return random.choice(responses)
        
        # Despedidas
        elif any(word in prompt_lower for word in ["tchau", "até", "adeus", "bye", "xau", "flw", "falou"]):
            responses = [
                "Tchau! Foi ótimo falar com você! 👋",
                "Até mais! Se cuida!",
                "Falou! Boa sorte aí! ✨",
                "Tchau tchau! Aparece mais!",
                "Até! Qualquer coisa me chama!",
                "Valeu pela conversa! Até a próxima!"
            ]
            return random.choice(responses)
        
        # Teste
        elif any(word in prompt_lower for word in ["teste", "testando", "test"]):
            responses = [
                "Recebi seu teste! Tá tudo funcionando! 🧪",
                "Teste recebido! Tô aqui, pode falar!",
                "Testando 1, 2, 3... Tá me ouvindo bem? 😄"
            ]
            return random.choice(responses)
        
        # Respostas genéricas (não entendeu)
        else:
            responses = [
                "Hmm, não entendi bem... Pode me explicar melhor?",
                "Opa, acho que não captei. Pode falar de outro jeito?",
                "Desculpa, não peguei essa. Me conta mais?",
                "Putz, não entendi direito. Você quer dados, suporte ou marcar algo?",
                "Eita, me perdi aqui! 😅 Pode repetir?",
                "Não entendi muito bem, mas tô aqui pra ajudar! Me explica melhor?",
                f"Interessante você falar sobre '{prompt[:30]}{'...' if len(prompt) > 30 else ''}'. Mas não entendi o que precisa. Pode elaborar?"
            ]
            return random.choice(responses)
    
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

    def classify_intent(self, message: str) -> Dict[str, Any]:
        """Classifica a intenção da mensagem usando palavras-chave (público para orquestrador)"""
        return self._classify_by_keywords(message)