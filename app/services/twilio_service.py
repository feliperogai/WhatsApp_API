twilio_service_py = ""
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from typing import Optional, Dict, Any
from app.config.settings import settings

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.phone_number = settings.twilio_phone_number
        
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        try:
            # Formata número para WhatsApp
            whatsapp_to = f"whatsapp:{to_number}"
            whatsapp_from = f"whatsapp:{self.phone_number}"
            
            message_params = {
                'body': message,
                'from_': whatsapp_from,
                'to': whatsapp_to
            }
            
            # Adiciona mídia se fornecida
            if media_url:
                message_params['media_url'] = [media_url]
            
            message_obj = self.client.messages.create(**message_params)
            
            logger.info(f"Message sent to {to_number}, SID: {message_obj.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to {to_number}: {str(e)}")
            return False
    
    def create_webhook_response(self, response_text: str, media_url: Optional[str] = None) -> str:
        resp = MessagingResponse()
        message = resp.message(response_text)
        
        if media_url:
            message.media(media_url)
        
        return str(resp)
    
    async def validate_webhook(self, request_data: Dict[str, Any]) -> bool:
        try:
            # Aqui você pode adicionar validação de assinatura Twilio
            required_fields = ['From', 'Body', 'MessageSid']
            return all(field in request_data for field in required_fields)
        except Exception as e:
            logger.error(f"Webhook validation error: {e}")
            return False
    
    def extract_phone_number(self, from_field: str) -> str:
        # Remove prefixo 'whatsapp:'
        return from_field.replace('whatsapp:', '') if from_field.startswith('whatsapp:') else from_field
    
    async def get_account_info(self) -> Dict[str, Any]:
        try:
            account = self.client.api.accounts(settings.twilio_account_sid).fetch()
            return {
                'account_sid': account.sid,
                'friendly_name': account.friendly_name,
                'status': account.status,
                'type': account.type
            }
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {} 
