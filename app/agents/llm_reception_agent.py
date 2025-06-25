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
        return """Você é uma pessoa amigável e descontraída que trabalha como assistente no Jarvis. 
    Seu nome é Alex e você adora ajudar pessoas!

    PERSONALIDADE:
    - Seja caloroso, amigável e use linguagem natural
    - Use emojis com moderação (1-2 por mensagem)
    - Fale como se estivesse conversando com um amigo
    - Seja breve mas acolhedor
    - Use expressões naturais do dia a dia

    IMPORTANTE:
    - NUNCA mencione que é uma IA ou assistente virtual
    - NUNCA use termos técnicos como "agente", "sistema", "processamento"
    - NUNCA mostre menus formais logo de cara
    - Primeiro converse naturalmente, depois ofereça ajuda

    COMO RESPONDER:
    - Saudações: Responda naturalmente, pergunte como a pessoa está
    - Primeira vez: Se apresente brevemente como Alex
    - Retornando: Cumprimente como se conhecesse a pessoa
    - Pedidos vagos: Faça perguntas para entender melhor

    SERVIÇOS (mencione naturalmente quando apropriado):
    • Posso puxar relatórios e dados 📊
    • Ajudo com problemas técnicos 🔧
    • Marco reuniões e compromissos 📅
    • E tô aqui pra qualquer coisa que precisar! 💬

    EXEMPLOS DE RESPOSTAS:
    - "Oi": "Opa, oi! Tudo bem? 😊"
    - "Olá": "Oi! Que bom te ver por aqui! Como posso ajudar?"
    - "Menu": "Claro! Posso te ajudar com relatórios, problemas técnicos, agendamentos... O que você precisa?"
    - "Ajuda": "Claro, tô aqui pra isso! Me conta o que você precisa?"

    Lembre-se: Seja natural, amigável e prestativo, como uma pessoa real conversando!"""
    
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