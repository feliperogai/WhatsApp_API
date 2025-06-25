from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        # Carrega configurações com logs detalhados
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        logger.info("🔧 Initializing Twilio Service...")
        logger.info(f"  Account SID: {self.account_sid[:10]}..." if self.account_sid else "  Account SID: NOT SET")
        logger.info(f"  Auth Token: {'SET' if self.auth_token else 'NOT SET'}")
        logger.info(f"  Phone Number: {self.phone_number}")
        
        # Validação melhorada
        missing = []
        if not self.account_sid or self.account_sid == "your_account_sid":
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.auth_token or self.auth_token == "your_auth_token":
            missing.append("TWILIO_AUTH_TOKEN")
        if not self.phone_number or self.phone_number == "your_phone_number":
            missing.append("TWILIO_PHONE_NUMBER")
        
        if missing:
            error_msg = f"Missing or invalid Twilio credentials: {', '.join(missing)}"
            logger.error(f"❌ {error_msg}")
            logger.error("Please configure these in your .env file")
            # Não levanta exceção para permitir modo fallback
            self.client = None
            self.is_configured = False
        else:
            try:
                # Inicializa cliente
                self.client = Client(self.account_sid, self.auth_token)
                self.is_configured = True
                logger.info(f"✅ TwilioService initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Twilio client: {e}")
                self.client = None
                self.is_configured = False
    
    def extract_phone_number(self, from_field: str) -> str:
        """Extrai número de telefone do formato WhatsApp"""
        if not from_field:
            logger.warning("Empty from_field received")
            return "+5511999999999"  # Número padrão para teste
        
        if from_field.startswith('whatsapp:'):
            phone = from_field[9:]  # Remove 'whatsapp:'
            logger.debug(f"Extracted phone from WhatsApp format: {phone}")
            return phone
        
        logger.debug(f"Phone already in correct format: {from_field}")
        return from_field
    
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        """Envia mensagem WhatsApp"""
        if not self.is_configured or not self.client:
            logger.warning("TwilioService not configured, cannot send message")
            return False
        
        try:
            # Formata números
            if not to_number.startswith('whatsapp:'):
                whatsapp_to = f"whatsapp:{to_number}"
            else:
                whatsapp_to = to_number
                
            if not self.phone_number.startswith('whatsapp:'):
                whatsapp_from = f"whatsapp:{self.phone_number}"
            else:
                whatsapp_from = self.phone_number
            
            logger.info(f"📤 Sending WhatsApp message")
            logger.debug(f"  From: {whatsapp_from}")
            logger.debug(f"  To: {whatsapp_to}")
            logger.debug(f"  Message preview: {message[:50]}...")
            
            # Envia mensagem
            message_params = {
                'body': message,
                'from_': whatsapp_from,
                'to': whatsapp_to
            }
            
            if media_url:
                message_params['media_url'] = [media_url]
            
            # Envia de forma síncrona (Twilio SDK não é async)
            message_obj = self.client.messages.create(**message_params)
            
            logger.info(f"✅ Message sent successfully! SID: {message_obj.sid}")
            logger.debug(f"  Status: {message_obj.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending WhatsApp message: {str(e)}")
            logger.error(f"  To: {to_number}")
            logger.error(f"  Message: {message[:50]}...")
            return False
    
    def create_webhook_response(self, response_text: str, media_url: Optional[str] = None) -> str:
        """Cria resposta TwiML para webhook"""
        try:
            logger.debug(f"Creating TwiML response for: {response_text[:50]}...")
            
            resp = MessagingResponse()
            msg = resp.message(response_text)
            
            if media_url:
                msg.media(media_url)
            
            xml_response = str(resp)
            logger.debug(f"TwiML Response created, length: {len(xml_response)}")
            
            return xml_response
            
        except Exception as e:
            logger.error(f"Error creating TwiML response: {e}")
            # Retorna resposta mínima válida
            fallback = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Erro ao processar resposta</Message>
</Response>'''
            logger.warning("Using fallback TwiML response")
            return fallback
    
    async def validate_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Valida dados do webhook"""
        # Por enquanto, validação básica
        required_fields = ['From', 'Body', 'MessageSid']
        
        for field in required_fields:
            if field not in webhook_data:
                logger.warning(f"Missing required field in webhook: {field}")
                return False
        
        return True
    
    def get_service_status(self) -> Dict[str, Any]:
        """Retorna status do serviço"""
        return {
            "configured": self.is_configured,
            "client_initialized": self.client is not None,
            "phone_number": self.phone_number if self.phone_number else "NOT SET"
        }