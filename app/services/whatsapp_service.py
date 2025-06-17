whatsapp_service_py = ""
import logging
from typing import Optional, Dict, Any
from app.services.twilio_service import TwilioService
from app.models.message import WhatsAppMessage, MessageType, MessageStatus
from app.core.orchestrator import AgentOrchestrator
from app.core.session_manager import SessionManager
from datetime import datetime

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.session_manager = SessionManager()
        self.twilio_service = TwilioService()
        self.orchestrator = AgentOrchestrator(self.session_manager)
    
    async def initialize(self):
        await self.session_manager.initialize()
        logger.info("WhatsApp service initialized")
    
    async def process_incoming_webhook(self, webhook_data: Dict[str, Any]) -> str:
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
            
            # Processa através do orquestrador
            response = await self.orchestrator.process_message(message)
            
            # Retorna resposta TwiML
            return self.twilio_service.create_webhook_response(response.response_text)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            error_response = "Desculpe, ocorreu um erro interno. Tente novamente em alguns instantes."
            return self.twilio_service.create_webhook_response(error_response)
    
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        return await self.twilio_service.send_message(to_number, message, media_url)
    
    def _detect_message_type(self, webhook_data: Dict[str, Any]) -> MessageType:
        if webhook_data.get('MediaUrl0'):
            return MessageType.MEDIA
        elif webhook_data.get('Latitude') and webhook_data.get('Longitude'):
            return MessageType.LOCATION
        else:
            return MessageType.TEXT
    
    async def get_service_status(self) -> Dict[str, Any]:
        try:
            active_sessions = await self.session_manager.get_active_sessions_count()
            agent_status = await self.orchestrator.get_agent_status()
            twilio_account = await self.twilio_service.get_account_info()
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "active_sessions": active_sessions,
                "agents": agent_status,
                "twilio_account": twilio_account.get('status', 'unknown')
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def reset_user_session(self, phone_number: str):
        await self.orchestrator.reset_session(phone_number)
        logger.info(f"User session reset: {phone_number}")
    
    async def broadcast_message(self, phone_numbers: list, message: str) -> Dict[str, bool]:
        results = {}
        for number in phone_numbers:
            success = await self.send_message(number, message)
            results[number] = success
        
        return results
