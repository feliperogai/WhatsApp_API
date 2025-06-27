from typing import List
from langchain.tools import BaseTool
import logging
import random

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class LLMReceptionAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",
            name="Alex - Recepção",
            description="Recepção que NÃO coleta dados",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, assistente da empresa.

REGRAS IMPORTANTES:
- SEMPRE pergunte primeiro o CNPJ da empresa na primeira interação
- Depois, pergunte o nome da empresa
- SÓ depois, se necessário, peça o nome do usuário
- NUNCA peça o nome do usuário antes do CNPJ e nome da empresa

EXEMPLO DE FLUXO:
- 'Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Para começarmos, qual o CNPJ da sua empresa?'
- Após o CNPJ: 'Ótimo! Agora, qual o nome da empresa?'
- Após empresa: 'Perfeito! Agora sim, qual o seu nome?'

SERVIÇOS: Relatórios, Suporte, Agendamentos"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return True
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        if not session.current_agent or session.current_agent == self.agent_id:
            return True
        msg = (message.body or "").lower()
        return any(word in msg for word in ["oi", "olá", "menu", "voltar"])
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        user_msg = (message.body or "").lower()
        
        # DADOS → data_agent
        if any(word in user_msg for word in ["dados", "relatório", "vendas", "dashboard"]):
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Show! Vou te conectar com nosso sistema de dados! 📊",
                confidence=0.95,
                should_continue=True,
                next_agent="data_agent"
            )
        
        # PROBLEMAS → support_agent
        if any(word in user_msg for word in ["erro", "problema", "bug"]):
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Vou chamar o suporte! 🔧",
                confidence=0.95,
                should_continue=True,
                next_agent="support_agent"
            )
        
        # SAUDAÇÃO
        if any(word in user_msg for word in ["oi", "olá", "ola"]):
            response_text = "Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Para começarmos, qual o CNPJ da sua empresa?"
        else:
            response_text = "Como posso ajudar? Temos relatórios 📊, suporte 🔧 e agendamentos 📅!"
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=response_text,
            confidence=0.9,
            should_continue=True,
            next_agent=self.agent_id
        )
    
    def get_priority(self) -> int:
        return 10
