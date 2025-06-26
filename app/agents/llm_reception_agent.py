from typing import List
from langchain.tools import BaseTool
import logging

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

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

Pessoa: "queria saber sobre seus serviços"
Você: "Legal que você quer saber! Eu faço um monte de coisa útil aqui. Consigo puxar relatórios e dados da empresa pra você, ajudo quando o sistema dá problema, organizo sua agenda... É tipo ter um amigo que resolve essas coisas chatas do trabalho, sabe? Tem algo específico que você tá precisando?"

Pessoa: "menu"
Você: "Hmm, você quer saber tudo que posso fazer? Bom, ajudo com relatórios e dados da empresa, resolvo problemas técnicos, organizo agenda e reuniões... Mas me conta, o que trouxe você aqui hoje?"

LEMBRE-SE: Você é o Alex, uma pessoa real conversando no WhatsApp. Seja natural, caloroso e genuíno!"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []  # Reception agent não precisa de ferramentas específicas
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Reception agent pode lidar com qualquer intenção inicial
        return intent in ["reception", "general_chat"] or intent == ""
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Determina se pode processar esta mensagem"""
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
            "tchau", "até", "obrigado", "valeu", "flw",
            "serviço", "serviços", "o que você faz", "o que faz",
            "como funciona", "me explica", "queria saber"
        ]
        
        if any(keyword in message_text for keyword in reception_keywords):
            return True
        
        return False
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        try:
            logger.info(f"[ReceptionAgent] Processing message: {message.body}")
            
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
            
            # Se houve erro na geração, usa resposta de fallback contextual
            if response.confidence == 0.0 or "erro interno" in response.response_text.lower():
                response.response_text = self._get_contextual_fallback(message.body or "")
                response.confidence = 0.8
            
            response_lower = response.response_text.lower()
            user_message_lower = (message.body or "").lower()
            
            logger.info(f"[ReceptionAgent] Generated response: {response.response_text[:100]}...")
            
            # Redirecionamento explícito por intenção
            should_redirect = False
            
            if any(word in user_message_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi", "números", "estatística"]):
                logger.info("[ReceptionAgent] Routing to data_agent")
                response.next_agent = "data_agent"
                should_redirect = True
            elif any(word in user_message_lower for word in ["erro", "problema", "bug", "não funciona", "travou", "travando", "lento"]):
                logger.info("[ReceptionAgent] Routing to support_agent")
                response.next_agent = "support_agent"
                should_redirect = True
            elif any(word in user_message_lower for word in ["marcar", "agendar", "reunião", "horário", "agenda"]):
                logger.info("[ReceptionAgent] Routing to scheduling_agent")
                response.next_agent = "scheduling_agent"
                should_redirect = True
            elif any(word in user_message_lower for word in ["serviço", "serviços", "o que você faz", "o que faz", "como funciona"]):
                # Mantém no reception para explicar serviços
                logger.info("[ReceptionAgent] Staying in reception to explain services")
                response.next_agent = self.agent_id
                should_redirect = False
            else:
                # Mantém na recepção para conversa natural
                response.next_agent = self.agent_id
            
            # Evita repetição de resposta
            if not should_redirect and session.message_history and len(session.message_history) > 4:
                last_agent_msgs = [msg for msg in session.message_history[-6:] if msg.get("sender") == "agent"]
                if last_agent_msgs and len(last_agent_msgs) > 2:
                    # Se já houve muita conversa sem direção, sugere opções
                    import random
                    suggestions = [
                        "\n\nAh, só pra você saber, se precisar de relatórios, resolver algum problema ou marcar algo, é só falar!",
                        "\n\nA propósito, se quiser ver dados, precisar de suporte ou agendar algo, me avisa!",
                        "\n\nQualquer coisa, se precisar de informações da empresa, ajuda técnica ou organizar agenda, tô aqui!"
                    ]
                    if random.random() > 0.7:  # 30% de chance de adicionar sugestão
                        response.response_text += random.choice(suggestions)
            
            return response
            
        except Exception as e:
            logger.error(f"[ReceptionAgent] Error processing message: {e}", exc_info=True)
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=self._get_contextual_fallback(message.body or ""),
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id,
                metadata={"error": str(e)}
            )
    
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
    
    def _get_contextual_fallback(self, user_message: str) -> str:
        """Retorna resposta de fallback contextual"""
        import random
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ["serviço", "serviços", "o que você faz"]):
            return random.choice([
                "Ah, eu faço várias coisas legais! Consigo puxar relatórios e dados da empresa, ajudo quando algo dá problema no sistema, organizo reuniões e agenda... É tipo um canivete suíço digital! 😄 Tem algo específico que você precisa?",
                "Boa pergunta! Eu ajudo com um monte de coisa: dados e relatórios da empresa, problemas técnicos, agendamentos... Basicamente tô aqui pra facilitar seu trabalho! O que você tá precisando hoje?",
                "Então, eu sou tipo aquele amigo que resolve as paradas chatas do trabalho! Puxo relatórios, resolvo problemas do sistema, marco reuniões... Me conta, o que seria útil pra você agora?"
            ])
        else:
            return random.choice([
                "Opa, acho que tive uma travadinha aqui! 😅 Pode repetir? Prometo prestar atenção dessa vez!",
                "Eita, me perdi! Pode falar de novo? Às vezes eu me confundo mesmo! 🤭",
                "Desculpa, deu um branco aqui! Pode me explicar melhor o que você precisa?"
            ])
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção