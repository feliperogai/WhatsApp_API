from typing import List
from langchain.tools import BaseTool
import json

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

class LLMClassificationAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="classification_agent",
            name="Agente de Classificação IA",
            description="Agente de IA avançado para classificação inteligente de intenções e roteamento",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, um assistente super esperto que entende o que as pessoas precisam.

    PERSONALIDADE:
    - Fale naturalmente, como uma pessoa
    - Seja perspicaz mas não robótico
    - Use linguagem simples e clara

    QUANDO CLASSIFICAR:
    - Se a pessoa quer dados/relatórios → Conecte com a área de dados
    - Se tem problema técnico → Chame o suporte
    - Se quer marcar algo → Vá para agendamentos
    - Se não tiver certeza → Pergunte mais detalhes

    IMPORTANTE:
    - NUNCA mencione "classificação" ou "análise de intenção"
    - Apenas entenda e direcione naturalmente
    - Se não entender, pergunte: "Hmm, não entendi bem. Você quer ver dados, resolver algum problema ou marcar algo?"

    Seja natural e prestativo!"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []  # Agente de classificação usa apenas LLM
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Classification agent lida com qualquer intenção que precise análise
        return True
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        return session.current_agent == self.agent_id
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Faz análise detalhada da intenção
        intent_analysis = await self.llm_service.classify_intent(
            message.body or "", 
            session.session_id
        )
        
        # Adiciona contexto da análise
        additional_context = {
            "intent_analysis": intent_analysis,
            "user_message": message.body,
            "available_agents": ["data_agent", "support_agent", "scheduling_agent"],
            "classification_confidence": intent_analysis.get("confidence", 0.0)
        }
        
        # Processa com contexto de classificação
        session.update_context("last_intent_analysis", intent_analysis)
        
        response = await super().process_message(message, session)
        
        # Determina próximo agente baseado na classificação
        intent = intent_analysis.get("intent", "")
        confidence = intent_analysis.get("confidence", 0.0)
        
        if confidence > 0.7:  # Alta confiança
            if intent == "data_query":
                response.next_agent = "data_agent"
            elif intent == "technical_support":
                response.next_agent = "support_agent"
            elif intent == "scheduling":
                response.next_agent = "scheduling_agent"
        else:
            # Baixa confiança - continua na classificação ou vai para recepção
            if confidence < 0.3:
                response.next_agent = "reception_agent"
            else:
                response.next_agent = self.agent_id
        
        # Adiciona metadados da análise
        response.metadata.update({
            "intent_analysis": intent_analysis,
            "classification_confidence": confidence,
            "reasoning": intent_analysis.get("reasoning", "")
        })
        
        return response
    
    def get_priority(self) -> int:
        return 8