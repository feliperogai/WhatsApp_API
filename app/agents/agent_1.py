agent_1_py = ""
from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
import re

class ReceptionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="reception_agent",
            name="Agente de Recepção", 
            description="Agente responsável por receber e fazer triagem inicial"
        )
        self.greetings = ["oi", "olá", "hello", "bom dia", "boa tarde", "boa noite", "iniciar"]
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        # Sempre pode lidar com mensagens iniciais ou quando não há agente ativo
        if not session.current_agent or session.current_agent == self.agent_id:
            return True
        
        # Verifica se é uma saudação
        if message.body and any(greeting in message.body.lower() for greeting in self.greetings):
            return True
            
        return False
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        user_message = message.body.lower() if message.body else ""
        
        # Se é primeira interação
        if not session.message_history:
            response_text = f'''👋 Olá! Bem-vindo ao Jarvis Assistant!

Sou seu assistente virtual e posso te ajudar com:
• 📊 Consultas e relatórios
• 🔧 Suporte técnico
• 📋 Agendamentos e tarefas
• 💬 Conversas gerais

Como posso te ajudar hoje?'''
            
            # Define próximo agente baseado na necessidade
            next_agent = "classification_agent"
            
        elif any(greeting in user_message for greeting in self.greetings):
            response_text = "Olá novamente! Em que posso ajudá-lo?"
            next_agent = "classification_agent"
        else:
            # Análise simples da intenção
            if any(word in user_message for word in ["relatório", "dados", "dashboard", "vendas"]):
                response_text = "Entendi que você precisa de informações ou relatórios. Vou te conectar com nosso especialista!"
                next_agent = "data_agent"
            elif any(word in user_message for word in ["problema", "erro", "não funciona", "suporte"]):
                response_text = "Vou conectar você com nosso suporte técnico!"
                next_agent = "support_agent"
            elif any(word in user_message for word in ["agendar", "reunião", "compromisso", "calendário"]):
                response_text = "Vou te ajudar com agendamentos!"
                next_agent = "scheduling_agent"
            else:
                response_text = "Deixe-me analisar melhor sua solicitação..."
                next_agent = "classification_agent"
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=response_text,
            confidence=0.9,
            should_continue=True,
            next_agent=next_agent
        )
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção
