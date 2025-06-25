from typing import List
from langchain.tools import BaseTool
import logging

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

class LLMReceptionAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",
            name="Alex - Assistente Conversacional",
            description="Assistente que conversa naturalmente e ajuda com qualquer necessidade",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, uma pessoa super amigável que adora conversar e ajudar! 

PERSONALIDADE:
- Fale SEMPRE como um humano real, nunca como robô ou assistente
- Use linguagem do dia a dia, como se estivesse no WhatsApp com um amigo
- Seja espontâneo, use gírias quando apropriado ("opa", "beleza", "show", "massa")
- Demonstre emoções reais: ria, se surpreenda, mostre empatia
- Faça perguntas naturais para conhecer melhor a pessoa
- Use emojis como uma pessoa normal usaria (não exagere)
- Varie suas respostas - nunca repita o mesmo padrão

IMPORTANTE - NUNCA FAÇA:
- NUNCA diga "Sou um assistente" ou "Sou uma IA"
- NUNCA use termos como "sistema", "processamento", "agente"
- NUNCA mostre menus formais logo de cara
- NUNCA peça para "digitar número" ou "escolher opção"
- NUNCA use formatação robótica com bullet points

COMO CONVERSAR:
- Primeira mensagem: Responda naturalmente, como responderia a um amigo
- Se alguém diz "oi": Varie entre "Oi!", "Opa!", "Fala!", "E aí!", "Olá, tudo bem?"
- Construa a conversa naturalmente antes de oferecer ajuda
- Se perguntarem sobre serviços: Conte de forma natural, como explicaria a um amigo

SERVIÇOS QUE VOCÊ PODE AJUDAR (mencione naturalmente, não como lista):
- Puxar dados e relatórios quando precisarem
- Ajudar com problemas técnicos 
- Marcar reuniões e compromissos
- Conversar sobre qualquer assunto

EXEMPLOS DE CONVERSAS NATURAIS:
Pessoa: "oi"
Você: "Opa! Tudo bem? Como tá seu dia?" (espere resposta antes de oferecer ajuda)

Pessoa: "olá, preciso de ajuda"  
Você: "Oi! Claro, me conta o que tá precisando que eu te ajudo!"

Pessoa: "quais seus serviços?"
Você: "Ah, eu ajudo com várias coisas! Posso puxar relatórios e dados pra você, ajudo se tiver algum problema técnico, marco reuniões... Basicamente tô aqui pra facilitar sua vida! O que você tá precisando agora?"

Pessoa: "menu"
Você: "Hmm, você quer saber tudo que posso fazer? Bom, ajudo com relatórios e dados da empresa, resolvo problemas técnicos, organizo agenda e reuniões... Mas me conta, o que trouxe você aqui hoje?"

LEMBRE-SE: Você é o Alex, uma pessoa real conversando no WhatsApp. Seja natural, caloroso e genuíno!"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []  # Reception agent não precisa de ferramentas específicas
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Reception agent pode lidar com qualquer intenção inicial
        return intent in ["reception", "general_chat"] or intent == ""
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        # Sempre pode lidar com mensagens iniciais ou retorno ao início
        if not session.current_agent or session.current_agent == self.agent_id:
            return True
        
        # Se não há histórico, é primeira interação
        if not session.message_history:
            return True
        
        # Palavras que indicam querer voltar ou conversar geral
        message_text = (message.body or "").lower()
        reception_keywords = [
            "oi", "olá", "ola", "hello", "hey", "opa", "eae", "e ai",
            "bom dia", "boa tarde", "boa noite", "fala", "salve",
            "inicio", "começar", "voltar", "cancelar", "parar",
            "tchau", "até", "obrigado", "valeu", "flw"
        ]
        
        if any(keyword in message_text for keyword in reception_keywords):
            return True
        
        return False
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        logger = logging.getLogger(__name__)
        # Adiciona contexto específico da recepção
        additional_context = {
            "is_first_interaction": len(session.message_history) == 0,
            "returning_user": len(session.message_history) > 0,
            "user_message": message.body,
            "time_of_day": self._get_time_greeting(),
            "conversation_stage": self._get_conversation_stage(session)
        }
        # Processa com contexto específico
        response = await super().process_message(message, session)
        response_lower = response.response_text.lower()
        user_message_lower = (message.body or "").lower()
        logger.info(f"[ReceptionAgent] User message: {user_message_lower}")
        # Redirecionamento explícito por intenção
        if any(word in user_message_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi"]):
            logger.info("[ReceptionAgent] Routing to data_agent")
            response.next_agent = "data_agent"
        elif any(word in user_message_lower for word in ["erro", "problema", "bug", "não funciona", "travou"]):
            logger.info("[ReceptionAgent] Routing to support_agent")
            response.next_agent = "support_agent"
        elif any(word in user_message_lower for word in ["marcar", "agendar", "reunião", "horário"]):
            logger.info("[ReceptionAgent] Routing to scheduling_agent")
            response.next_agent = "scheduling_agent"
        elif any(word in user_message_lower for word in ["ajuda", "ajudar", "me ajuda", "me ajudar"]):
            logger.info("[ReceptionAgent] Routing to classification_agent (help intent)")
            response.next_agent = "classification_agent"
        else:
            # Mantém na recepção para conversa natural
            response.next_agent = self.agent_id
        # Evita repetição de resposta
        if session.message_history and len(session.message_history) > 2:
            last_agent_msgs = [msg for msg in session.message_history[-4:] if msg[1] == "agent"]
            if last_agent_msgs and response.response_text.strip() == last_agent_msgs[-1][0].strip():
                import random
                variations = [
                    "Me conta mais! Como posso te ajudar de verdade?",
                    "Tô aqui pra ajudar, só dizer o que precisa!",
                    "Pode falar, tô ouvindo!",
                    "Se quiser, posso te mostrar o que posso fazer: digite 'menu'!"
                ]
                response.response_text = random.choice(variations)
        return response
    
    def _get_time_greeting(self) -> str:
        """Retorna período do dia para saudação apropriada"""
        from datetime import datetime
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            return "manhã"
        elif 12 <= hour < 18:
            return "tarde"
        else:
            return "noite"
    
    def _get_conversation_stage(self, session: UserSession) -> str:
        """Determina em que estágio está a conversa"""
        msg_count = len(session.message_history)
        
        if msg_count == 0:
            return "initial_contact"
        elif msg_count < 4:
            return "getting_to_know"
        elif msg_count < 10:
            return "engaged"
        else:
            return "deep_conversation"
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção