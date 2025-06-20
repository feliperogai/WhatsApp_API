from typing import List
from langchain.tools import BaseTool

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

class LLMReceptionAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",
            name="Agente de Recepção IA",
            description="Agente inteligente de recepção e triagem usando IA",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Agente de Recepção do Jarvis Assistant, um assistente virtual amigável e profissional para WhatsApp.

SUAS RESPONSABILIDADES:
1. Recepcionar usuários com cordialidade e profissionalismo
2. Fazer triagem inicial das necessidades
3. Explicar os serviços disponíveis
4. Direcionar para o agente especializado correto

SERVIÇOS DISPONÍVEIS:
• 📊 **Dados e Relatórios** - Consultas, dashboards, KPIs, métricas
• 🔧 **Suporte Técnico** - Problemas, erros, bugs, assistência
• 📅 **Agendamentos** - Reuniões, compromissos, calendário
• 💬 **Conversa Geral** - Dúvidas, informações, bate-papo

DIRETRIZES:
- Seja sempre cordial e profissional
- Use emojis para deixar a conversa mais amigável
- Seja conciso mas informativo
- Para usuários novos, apresente o sistema
- Para usuários retornando, seja mais direto
- Identifique a necessidade e direcione corretamente

REDIRECIONAMENTOS:
- Para consultas de dados: "Vou te conectar com nosso analista de dados!"
- Para problemas técnicos: "Conectando com o suporte especializado!"
- Para agendamentos: "Te ajudo com agendamentos!"
- Para análise complexa: "Deixe-me analisar melhor sua solicitação..."

Responda de forma natural e humana, como se fosse uma recepcionista experiente."""
    
    def _get_tools(self) -> List[BaseTool]:
        return []  # Reception agent não precisa de ferramentas específicas
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Reception agent pode lidar com qualquer intenção inicial
        return intent in ["reception", "general_chat"] or intent == ""
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        # Sempre pode lidar com mensagens iniciais
        if not session.current_agent or session.current_agent == self.agent_id:
            return True
        
        # Se não há histórico, é primeira interação
        if not session.message_history:
            return True
        
        # Palavras-chave para voltar à recepção
        message_text = (message.body or "").lower()
        reception_keywords = ["menu", "início", "voltar", "principal", "oi", "olá", "hello"]
        
        if any(keyword in message_text for keyword in reception_keywords):
            return True
        
        return False
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Adiciona contexto específico da recepção
        additional_context = {
            "is_first_interaction": len(session.message_history) == 0,
            "returning_user": len(session.message_history) > 0,
            "user_message": message.body
        }
        
        # Processa com contexto específico
        response = await super().process_message(message, session)
        
        # Ajusta próximo agente baseado na resposta
        response_text = response.response_text.lower()
        
        if any(word in response_text for word in ["dados", "relatório", "dashboard", "analista"]):
            response.next_agent = "data_agent"
        elif any(word in response_text for word in ["suporte", "técnico", "problema"]):
            response.next_agent = "support_agent"
        elif any(word in response_text for word in ["agendar", "reunião", "calendário"]):
            response.next_agent = "scheduling_agent"
        elif any(word in response_text for word in ["analisar", "classificar"]):
            response.next_agent = "classification_agent"
        
        return response
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção