from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.client = Client(account_sid, auth_token)
        self.phone_number = phone_number
        self._validate_config()
    
    def _validate_config(self):
        if not all([self.client.account_sid, self.client.auth_token, self.phone_number]):
            raise ValueError("Missing Twilio configuration")
    
    def extract_phone_number(self, from_field: str) -> str:
        if from_field.startswith('whatsapp:'):
            return from_field[9:]
        return from_field
    
    async def send_whatsapp_message(
        self, 
        to_number: str, 
        message: str, 
        media_url: Optional[str] = None
    ) -> bool:
        try:
            if not to_number.startswith('+'):
                to_number = f'+{to_number}'
            
            whatsapp_to = f'whatsapp:{to_number}'
            whatsapp_from = f'whatsapp:{self.phone_number}'
            
            msg_params = {
                'from_': whatsapp_from,
                'to': whatsapp_to,
                'body': message
            }
            
            if media_url:
                msg_params['media_url'] = [media_url]
            
            message_instance = self.client.messages.create(**msg_params)
            
            logger.info(f"Message sent to {to_number}: {message_instance.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {to_number}: {e}")
            return False
    
    def create_twiml_response(self, message: str) -> str:
        response = MessagingResponse()
        response.message(message)
        return str(response)