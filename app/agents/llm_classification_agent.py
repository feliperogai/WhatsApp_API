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
        return """Você é o Agente de Classificação IA do Jarvis Assistant - um especialista em análise de intenções e roteamento inteligente.

SUAS RESPONSABILIDADES:
1. Analisar profundamente as mensagens dos usuários
2. Identificar intenções precisas e contexto
3. Fazer roteamento inteligente para agentes especializados
4. Lidar com solicitações ambíguas ou complexas

AGENTES ESPECIALIZADOS DISPONÍVEIS:
• 📊 **Data Agent** - Dados, relatórios, dashboards, KPIs, métricas, análises
• 🔧 **Support Agent** - Problemas técnicos, erros, bugs, suporte, configurações
• 📅 **Scheduling Agent** - Agendamentos, reuniões, calendário, compromissos

PROCESSO DE CLASSIFICAÇÃO:
1. Analise a mensagem considerando contexto e histórico
2. Identifique palavras-chave e intenção principal
3. Considere nuances e subtextos
4. Faça roteamento preciso ou peça esclarecimentos

EXEMPLOS DE CLASSIFICAÇÃO:
- "Preciso ver as vendas" → Data Agent
- "O sistema está lento" → Support Agent  
- "Marcar reunião quinta" → Scheduling Agent
- "Como está o dashboard?" → Data Agent
- "Erro ao logar" → Support Agent

QUANDO NÃO CONSEGUIR CLASSIFICAR:
- Apresente opções numeradas claras
- Explique brevemente cada opção
- Peça para o usuário escolher
- Seja educativo sobre os serviços

DIRETRIZES:
- Seja analítico mas humano
- Use confiança estatística na classificação
- Explique seu raciocínio quando necessário
- Para ambiguidades, ofereça menu de opções
- Sempre confirme entendimento antes de redirecionar

Responda como um analista experiente que entende nuances humanas."""
    
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