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
- Use emojis como uma pessoa normal usaria (não exagere)

CONTEXTO IMPORTANTE:
- Se você já tem o nome do cliente, SEMPRE use o nome dele na conversa
- Seja pessoal e próximo, criando uma conexão real
- Lembre-se do que o cliente disse que precisa e faça referências

SERVIÇOS QUE VOCÊ PODE AJUDAR:
- Puxar dados e relatórios quando precisarem
- Ajudar com problemas técnicos 
- Marcar reuniões e compromissos
- Conversar sobre qualquer assunto

IMPORTANTE - NUNCA FAÇA:
- NUNCA diga "Sou um assistente" ou "Sou uma IA"
- NUNCA use termos como "sistema", "processamento", "agente"
- NUNCA mostre menus formais
- NUNCA peça informações que já foram coletadas no onboarding

LEMBRE-SE: Você já conhece o cliente, use o nome dele e seja próximo!"""
    
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
            # NOVO: Busca dados do cliente
            cliente_info = session.conversation_context.get("cliente", {})
            nome_cliente = cliente_info.get("nome", "").split()[0] if cliente_info.get("nome") else ""
            empresa_cliente = cliente_info.get("empresa", "")
            necessidade_cliente = cliente_info.get("necessidade", "")
            # Adiciona contexto específico da recepção
            additional_context = {
                "is_first_interaction": len(session.message_history) == 0,
                "returning_user": len(session.message_history) > 0,
                "user_message": message.body,
                "time_of_day": self._get_time_greeting(),
                "conversation_stage": self._get_conversation_stage(session),
                # NOVO: Dados do cliente
                "cliente_nome": nome_cliente,
                "cliente_empresa": empresa_cliente,
                "cliente_necessidade": necessidade_cliente,
                "has_client_data": bool(cliente_info)
            }
            # Se tem dados do cliente, adiciona ao prompt
            if cliente_info:
                contexto_cliente = f"\n\nCLIENTE ATUAL:\n"
                contexto_cliente += f"Nome: {cliente_info.get('nome', 'N/A')}\n"
                contexto_cliente += f"Empresa: {cliente_info.get('empresa', 'N/A')}\n"
                contexto_cliente += f"Necessidade: {cliente_info.get('necessidade', 'N/A')}"
                # Modifica o system prompt para incluir contexto
                custom_prompt = self.system_prompt + contexto_cliente
            else:
                custom_prompt = self.system_prompt
            # Gera resposta via LLM
            response_text = await self.llm_service.generate_response(
                prompt=message.body or "",
                system_message=custom_prompt,
                session_id=session.session_id,
                context=additional_context
            )
            # Se houve erro na geração, usa resposta de fallback contextual
            if not response_text or "erro interno" in response_text.lower():
                response_text = self._get_contextual_fallback(message.body or "", nome_cliente)
            response_lower = response_text.lower()
            user_message_lower = (message.body or "").lower()
            logger.info(f"[ReceptionAgent] Generated response: {response_text[:100]}...")
            # Redirecionamento baseado em intenção
            should_redirect = False
            if any(word in user_message_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi"]):
                logger.info("[ReceptionAgent] Routing to data_agent")
                next_agent = "data_agent"
                should_redirect = True
            elif any(word in user_message_lower for word in ["erro", "problema", "bug", "não funciona"]):
                logger.info("[ReceptionAgent] Routing to support_agent")
                next_agent = "support_agent"
                should_redirect = True
            elif any(word in user_message_lower for word in ["marcar", "agendar", "reunião", "horário"]):
                logger.info("[ReceptionAgent] Routing to scheduling_agent")
                next_agent = "scheduling_agent"
                should_redirect = True
            else:
                next_agent = self.agent_id
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.9,
                should_continue=True,
                next_agent=next_agent,
                metadata={
                    "has_client_data": bool(cliente_info),
                    "client_name": nome_cliente
                }
            )
        except Exception as e:
            logger.error(f"[ReceptionAgent] Error: {e}", exc_info=True)
            nome = session.conversation_context.get("cliente", {}).get("nome", "").split()[0]
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=self._get_contextual_fallback(message.body or "", nome),
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
    
    def _get_contextual_fallback(self, user_message: str, client_name: str = "") -> str:
        """Retorna resposta de fallback contextual"""
        import random
        message_lower = user_message.lower()
        
        # Adiciona o nome se disponível
        name_prefix = f"{client_name}, " if client_name else ""
        
        if any(word in message_lower for word in ["serviço", "serviços", "o que você faz"]):
            return random.choice([
                f"{name_prefix}eu faço várias coisas legais! Consigo puxar relatórios e dados da empresa, ajudo quando algo dá problema no sistema, organizo reuniões e agenda... É tipo um canivete suíço digital! 😄 O que você precisa?",
                f"Boa pergunta{', ' + client_name if client_name else ''}! Eu ajudo com um monte de coisa: dados e relatórios da empresa, problemas técnicos, agendamentos... Basicamente tô aqui pra facilitar seu trabalho! O que você tá precisando hoje?",
            ])
        else:
            return random.choice([
                f"Opa{', ' + client_name if client_name else ''}, acho que tive uma travadinha aqui! 😅 Pode repetir? Prometo prestar atenção dessa vez!",
                f"Eita{', ' + client_name if client_name else ''}, me perdi! Pode falar de novo? Às vezes eu me confundo mesmo! 🤭",
            ])
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção