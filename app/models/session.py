session_py = ""
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

class UserSession(BaseModel):
    session_id: str
    phone_number: str
    current_agent: Optional[str] = None
    conversation_context: Dict[str, Any] = {}
    message_history: List[Dict[str, Any]] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    expires_at: datetime = datetime.now() + timedelta(hours=24)
    is_active: bool = True
    
    def add_message(self, message: str, sender: str = "user", agent_id: str = None):
        msg_data = {
            "message": message,
            "sender": sender,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id
        }
        self.message_history.append(msg_data)
        self.updated_at = datetime.now()
    
    def update_context(self, key: str, value: Any):
        self.conversation_context[key] = value
        self.updated_at = datetime.now()