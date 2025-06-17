message_py = ""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    TEXT = "text"
    MEDIA = "media"
    LOCATION = "location"
    DOCUMENT = "document"

class MessageStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    SENT = "sent"
    FAILED = "failed"

class WhatsAppMessage(BaseModel):
    message_id: str
    from_number: str
    to_number: str
    body: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    media_url: Optional[str] = None
    timestamp: datetime = datetime.now()
    status: MessageStatus = MessageStatus.RECEIVED
    metadata: Dict[str, Any] = {}
    
class AgentResponse(BaseModel):
    agent_id: str
    response_text: str
    confidence: float = 0.0
    should_continue: bool = True
    metadata: Dict[str, Any] = {}
    next_agent: Optional[str] = None