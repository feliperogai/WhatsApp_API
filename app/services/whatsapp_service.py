import logging
from typing import Optional, Dict, Any
from app.services.twilio_service import TwilioService
from app.models.message import WhatsAppMessage, MessageType, MessageStatus
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.core.session_manager import SessionManager
from app.services.llm_service import LLMService
from datetime import datetime

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.session_manager = SessionManager()
        self.twilio_service = TwilioService()
        self.llm_service = LLMService()
        self.orchestrator = None
    
    async def initialize(self):
        """Inicializa todos os serviços"""
        await self.session_manager.initialize()
        await self.llm_service.initialize()
        
        # Inicializa orquestrador LangGraph
        self.orchestrator = LangGraphOrchestrator(self.session_manager, self.llm_service)
        
        logger.info("WhatsApp LLM service initialized successfully")
    
    async def process_incoming_webhook(self, webhook_data: Dict[str, Any]) -> str:
        """Processa webhook usando LangGraph"""
        try:
            # Valida webhook
            if not await self.twilio_service.validate_webhook(webhook_data):
                logger.warning("Invalid webhook received")
                return self.twilio_service.create_webhook_response("Erro de validação")
            
            # Extrai dados da mensagem
            from_number = self.twilio_service.extract_phone_number(webhook_data.get('From', ''))
            message_body = webhook_data.get('Body', '')
            message_sid = webhook_data.get('MessageSid', '')
            
            # Detecta tipo de mensagem
            message_type = self._detect_message_type(webhook_data)
            
            # Cria objeto de mensagem
            message = WhatsAppMessage(
                message_id=message_sid,
                from_number=from_number,
                to_number=self.twilio_service.phone_number,
                body=message_body,
                message_type=message_type,
                media_url=webhook_data.get('MediaUrl0'),
                status=MessageStatus.RECEIVED
            )
            
            logger.info(f"Processing message from {from_number}: {message_body[:50]}...")
            
            # Processa através do LangGraph Orchestrator
            response = await self.orchestrator.process_message(message)
            
            # Log da resposta
            logger.info(f"Response generated: {response.response_text[:100]}...")
            
            # Retorna resposta TwiML
            return self.twilio_service.create_webhook_response(response.response_text)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            error_response = """🤖 Ops! Estou com dificuldades técnicas no momento. 

Nossa equipe de IA foi notificada e está trabalhando para me normalizar.

Tente novamente em alguns instantes ou digite 'menu' para reiniciar."""
            return self.twilio_service.create_webhook_response(error_response)
    
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        """Envia mensagem via Twilio"""
        return await self.twilio_service.send_message(to_number, message, media_url)
    
    def _detect_message_type(self, webhook_data: Dict[str, Any]) -> MessageType:
        """Detecta tipo de mensagem"""
        if webhook_data.get('MediaUrl0'):
            return MessageType.MEDIA
        elif webhook_data.get('Latitude') and webhook_data.get('Longitude'):
            return MessageType.LOCATION
        else:
            return MessageType.TEXT
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Status completo do serviço"""
        try:
            active_sessions = await self.session_manager.get_active_sessions_count()
            llm_status = await self.llm_service.get_service_status()
            workflow_status = await self.orchestrator.get_workflow_status()
            twilio_account = await self.twilio_service.get_account_info()
            
            return {
                "status": "healthy",
                "service_type": "LLM-powered-optimized",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "session_manager": {
                        "active_sessions": active_sessions,
                        "status": "online"
                    },
                    "llm_service": llm_status,
                    "langgraph_orchestrator": workflow_status,
                    "twilio_service": {
                        "account_status": twilio_account.get('status', 'unknown'),
                        "phone_number": self.twilio_service.phone_number
                    }
                },
                "configuration": {
                    "ollama_url": "http://192.168.15.31:11435",
                    "model": "llama3.1:8b",
                    "optimized": True
                },
                "capabilities": [
                    "Natural language understanding",
                    "Intelligent intent classification",
                    "Context-aware conversations", 
                    "Dynamic workflow routing",
                    "LLM-powered responses",
                    "Optimized for external Ollama"
                ]
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "service_type": "LLM-powered-optimized",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def reset_user_session(self, phone_number: str):
        """Reseta sessão do usuário"""
        await self.session_manager.delete_session(phone_number)
        # Reset também na memória LLM
        self.llm_service.reset_session_memory(phone_number)
        logger.info(f"User session and LLM memory reset: {phone_number}")
    
    async def broadcast_message(self, phone_numbers: list, message: str) -> Dict[str, bool]:
        """Broadcast para múltiplos usuários"""
        results = {}
        for number in phone_numbers:
            success = await self.send_message(number, message)
            results[number] = success
        
        return results
    
    async def analyze_conversation(self, phone_number: str) -> Dict[str, Any]:
        """Analisa conversa usando LLM"""
        try:
            session = await self.session_manager.get_session(phone_number)
            if not session:
                return {"error": "Session not found"}
            
            # Monta histórico da conversa
            conversation_text = ""
            for msg in session.message_history[-10:]:  # Últimas 10 mensagens
                role = "Usuário" if msg.get("sender") == "user" else "Assistente"
                conversation_text += f"{role}: {msg.get('message', '')}\n"
            
            # Analisa com LLM
            analysis_prompt = f"""Analise esta conversa de WhatsApp e forneça insights:

{conversation_text}

Forneça uma análise em JSON com:
- sentiment: sentimento geral (positive/neutral/negative)
- topics: principais tópicos discutidos
- user_satisfaction: nível de satisfação (1-10)
- next_recommendations: recomendações para próximas interações
- conversation_summary: resumo em 1-2 frases"""
            
            analysis = await self.llm_service.generate_response(
                analysis_prompt,
                "Você é um analista de conversas especializado em customer experience.",
                session.session_id
            )
            
            return {
                "phone_number": phone_number,
                "analysis": analysis,
                "message_count": len(session.message_history),
                "session_duration": (datetime.now() - session.created_at).total_seconds() / 3600,
                "agents_used": list(set([msg.get("agent_id") for msg in session.message_history if msg.get("agent_id")]))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing conversation for {phone_number}: {e}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Limpa recursos"""
        if self.llm_service:
            await self.llm_service.cleanup()