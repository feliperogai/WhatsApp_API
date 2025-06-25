# app/services/twilio_service_fix.py
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        # Carrega configurações
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        # Validação
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            logger.error("Twilio credentials not properly configured!")
            logger.error(f"SID: {'✓' if self.account_sid else '✗'}")
            logger.error(f"Token: {'✓' if self.auth_token else '✗'}")
            logger.error(f"Phone: {'✓' if self.phone_number else '✗'}")
            raise ValueError("Missing Twilio credentials")
        
        # Inicializa cliente
        self.client = Client(self.account_sid, self.auth_token)
        logger.info(f"TwilioService initialized with phone: {self.phone_number}")
        
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        """Envia mensagem WhatsApp"""
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
            
            logger.info(f"Sending WhatsApp message from {whatsapp_from} to {whatsapp_to}")
            
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
            logger.info(f"Status: {message_obj.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending WhatsApp message: {str(e)}")
            logger.error(f"To: {to_number}, Message: {message[:50]}...")
            return False
    
    def create_webhook_response(self, response_text: str, media_url: Optional[str] = None) -> str:
        """Cria resposta TwiML para webhook"""
        try:
            resp = MessagingResponse()
            msg = resp.message(response_text)
            
            if media_url:
                msg.media(media_url)
            
            xml_response = str(resp)
            logger.debug(f"TwiML Response: {xml_response}")
            return xml_response
            
        except Exception as e:
            logger.error(f"Error creating TwiML response: {e}")
            # Retorna resposta mínima válida
            return '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Erro no sistema</Message></Response>'