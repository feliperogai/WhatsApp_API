base_agent_py = ""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.is_active = True
    
    @abstractmethod
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Determina se o agente pode processar esta mensagem"""
        pass
    
    @abstractmethod
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa a mensagem e retorna resposta"""
        pass
    
    async def preprocess(self, message: WhatsAppMessage, session: UserSession) -> Optional[Dict[str, Any]]:
        """Pré-processamento antes de processar mensagem"""
        return None
    
    async def postprocess(self, response: AgentResponse, session: UserSession) -> AgentResponse:
        """Pós-processamento após processar mensagem"""
        return response
    
    def get_priority(self) -> int:
        """Retorna prioridade do agente (maior = mais prioritário)"""
        return 1
    
    def log_interaction(self, message: WhatsAppMessage, response: AgentResponse):
        logger.info(f"Agent {self.agent_id} processed message from {message.from_number}: {response.response_text[:100]}")