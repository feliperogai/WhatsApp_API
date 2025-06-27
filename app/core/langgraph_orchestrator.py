from typing import Dict, Any, List, Optional, TypedDict, Annotated
import logging
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain.schema import BaseMessage, HumanMessage, AIMessage

from app.agents.llm_reception_agent import LLMReceptionAgent
from app.agents.llm_classification_agent import LLMClassificationAgent
from app.agents.llm_data_agent import LLMDataAgent
from app.agents.llm_support_agent import LLMSupportAgent
from app.core.session_manager import SessionManager
from app.services.llm_service import LLMService
from app.models.message import WhatsAppMessage, AgentResponse

logger = logging.getLogger(__name__)

# Estado do grafo de conversação
class ConversationState(TypedDict):
    messages: Annotated[List[BaseMessage], "Mensagens da conversa"]
    current_agent: str
    user_input: str
    session_id: str
    phone_number: str
    intent_analysis: Dict[str, Any]
    agent_response: Dict[str, Any]
    context: Dict[str, Any]
    routing_decision: str
    conversation_complete: bool

class LangGraphOrchestrator:
    def __init__(self, session_manager: SessionManager, llm_service: LLMService):
        self.session_manager = session_manager
        self.llm_service = llm_service
        self.agents = {}
        self.workflow: Optional[CompiledStateGraph] = None
        self._initialize_agents()
        self._build_workflow()
    
    def _initialize_agents(self):
        """Inicializa todos os agentes LLM"""
        self.agents = {
            "reception_agent": LLMReceptionAgent(self.llm_service),  # Não ProactiveReceptionAgent!
            "classification_agent": LLMClassificationAgent(self.llm_service),
            "data_agent": LLMDataAgent(self.llm_service),
            "support_agent": LLMSupportAgent(self.llm_service)
        }
        logger.info("LangGraph agents initialized")

    def _build_workflow(self):
        """Constrói o workflow do LangGraph"""
        workflow = StateGraph(ConversationState)
        workflow.add_node("reception", self._reception_node)
        workflow.add_node("classification", self._classification_node)
        workflow.add_node("data_analysis", self._data_node)
        workflow.add_node("technical_support", self._support_node)
        workflow.add_node("intent_router", self._intent_router_node)
        workflow.add_node("response_formatter", self._response_formatter_node)
        workflow.set_entry_point("intent_router")
        workflow.add_conditional_edges(
            "intent_router",
            self._route_to_agent,
            {
                "reception": "reception",
                "classification": "classification", 
                "data": "data_analysis",
                "support": "technical_support",
                "end": END
            }
        )
        workflow.add_edge("reception", "response_formatter")
        workflow.add_edge("classification", "response_formatter")
        workflow.add_edge("data_analysis", "response_formatter")
        workflow.add_edge("technical_support", "response_formatter")
        workflow.add_conditional_edges(
            "response_formatter",
            self._should_continue_conversation,
            {
                "continue": "intent_router",
                "end": END
            }
        )
        self.workflow = workflow.compile()
        logger.info("LangGraph workflow built successfully")

    async def process_message(self, message: WhatsAppMessage) -> AgentResponse:
        """Processa mensagem através do LangGraph com melhor tratamento de erros e logs detalhados"""
        try:
            session = await self.session_manager.get_or_create_session(message.from_number)
            logger.info(f"[Orchestrator] Processing message for session: {session.session_id}")
            logger.info(f"[Orchestrator] Message: '{message.body}'")
            logger.info(f"[Orchestrator] Current agent: {session.current_agent}")
            initial_state = ConversationState(
                messages=[HumanMessage(content=message.body or "")],
                current_agent=session.current_agent or "reception_agent",
                user_input=message.body or "",
                session_id=session.session_id,
                phone_number=message.from_number,
                intent_analysis={},
                agent_response={},
                context=session.conversation_context,
                routing_decision="",
                conversation_complete=False
            )
            logger.info("[Orchestrator] Invoking LangGraph workflow...")
            try:
                import asyncio
                final_state = await asyncio.wait_for(
                    self.workflow.ainvoke(initial_state),
                    timeout=25.0
                )
            except asyncio.TimeoutError:
                logger.error("[Orchestrator] Workflow timeout!")
                return AgentResponse(
                    agent_id="system",
                    response_text="Opa, demorei demais processando! 😅 Pode tentar de novo? Vou ser mais rápido!",
                    confidence=0.7,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "workflow_timeout"}
                )
            logger.info(f"[Orchestrator] Workflow completed successfully")
            agent_response = final_state.get("agent_response", {})
            logger.info(f"[Orchestrator] agent_response: {agent_response}")
            if not agent_response or not agent_response.get("text"):
                logger.error(f"[Orchestrator] Invalid or empty response from workflow. Final state: {final_state}")
                return self._create_contextual_error_response(message.body or "")
            response = AgentResponse(
                agent_id=final_state.get("current_agent", "system"),
                response_text=agent_response.get("text", ""),
                confidence=agent_response.get("confidence", 0.0),
                should_continue=not final_state.get("conversation_complete", False),
                next_agent=agent_response.get("next_agent"),
                metadata=agent_response.get("metadata", {})
            )
            try:
                session.add_message(message.body or "", "user")
                session.add_message(response.response_text, "agent", response.agent_id)
                session.current_agent = response.next_agent or response.agent_id
                session.conversation_context.update(final_state.get("context", {}))
                await self.session_manager.save_session(session)
                logger.info(f"[Orchestrator] Session updated successfully")
            except Exception as e:
                logger.error(f"[Orchestrator] Error updating session: {e}")
            logger.info(f"[Orchestrator] Message processed by {response.agent_id}")
            logger.info(f"[Orchestrator] Response preview: {response.response_text[:100]}...")
            return response
        except Exception as e:
            logger.error(f"[Orchestrator] Critical error: {type(e).__name__}: {str(e)}", exc_info=True)
            return self._create_contextual_error_response(message.body or "")
    
    def _create_contextual_error_response(self, user_input: str) -> AgentResponse:
        """Cria resposta de erro contextual baseada na entrada do usuário"""
        import random
        input_lower = user_input.lower()
        if any(word in input_lower for word in ["serviço", "serviços", "o que você faz"]):
            error_responses = [
                "Opa! Tive um probleminha, mas já voltei! 😅 Eu ajudo com relatórios, problemas técnicos e agendamentos. O que você precisa?",
                "Eita, bugou aqui! Mas respondendo: faço relatórios da empresa, resolvo problemas e organizo agenda! Como posso ajudar?",
                "Desculpa a demora! Eu trabalho com dados da empresa, suporte técnico e agendamentos. Qual desses você precisa?"
            ]
        elif any(word in input_lower for word in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
            error_responses = [
                "Oi! Desculpa, tive uma travadinha! 😅 Mas tô aqui! Como posso ajudar?",
                "Opa! Tudo bem? Deu uma bugadinha mas já voltei! Em que posso ajudar?",
                "Olá! Foi mal, pequeno problema técnico! Mas tô pronto pra ajudar! O que precisa?"
            ]
        elif any(word in input_lower for word in ["erro", "problema", "bug", "travou"]):
            error_responses = [
                "Poxa, justo quando você tá com problema, eu também bugo! 😅 Mas vamos resolver! Me conta o que aconteceu?",
                "Eita, dois problemas então! O seu e o meu bug! 😄 Mas calma, me explica o que tá pegando aí?",
                "Que ironia, você reportando erro e eu dando erro! 🤦 Mas bora resolver! O que tá acontecendo?"
            ]
        else:
            error_responses = [
                "Ops! Tive um probleminha técnico aqui! 🔧 Pode repetir? Prometo funcionar dessa vez!",
                "Eita, deu ruim aqui! 😅 Mas já tô de volta! O que você precisa?",
                "Desculpa, travei por um segundo! Pode falar de novo? Agora vai!",
                "Poxa, bugou aqui! Mas tô firme e forte! Me conta o que precisa?",
                "Xiii, pequeno problema técnico! Mas já resolvi! Como posso ajudar?"
            ]
        return AgentResponse(
            agent_id="system",
            response_text=random.choice(error_responses),
            confidence=0.7,
            should_continue=True,
            next_agent="reception_agent",
            metadata={"error": "processing_error", "original_input": user_input}
        )
    
    async def _reception_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de recepção com logs detalhados e tratamento robusto de erros"""
        import traceback
        logger.info(f"[ReceptionNode] Iniciando processamento para {state['phone_number']} | input: {state['user_input']}")
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            if session is None:
                logger.warning(f"[ReceptionNode] Nenhuma sessão encontrada para {state['phone_number']}. Criando nova sessão.")
                session = await self.session_manager.get_or_create_session(state["phone_number"])
                logger.info(f"[ReceptionNode] Nova sessão criada: {session.session_id}")
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            logger.info(f"[ReceptionNode] Processando mensagem: '{message.body}'")
            try:
                import asyncio
                response = await asyncio.wait_for(
                    self.agents["reception_agent"].process_message(message, session),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                logger.error("[ReceptionNode] Timeout ao processar mensagem")
                response = AgentResponse(
                    agent_id="reception_agent",
                    response_text="Opa, demorei pra processar! 😅 Pode repetir? Vou ser mais rápido!",
                    confidence=0.7,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "timeout"}
                )
            if not response or not getattr(response, 'response_text', None):
                logger.error(f"[ReceptionNode] Resposta vazia ou inválida do agente: {response}")
                response = AgentResponse(
                    agent_id="reception_agent",
                    response_text="Hmm, tive um probleminha aqui. Pode tentar de novo? 🤔",
                    confidence=0.7,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "empty_response"}
                )
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "reception_agent"
            logger.info(f"[ReceptionNode] Resposta gerada com sucesso: {response.response_text}")
        except Exception as e:
            logger.error(f"[ReceptionNode] Erro crítico: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            user_input = state.get("user_input", "").lower()
            if any(word in user_input for word in ["serviço", "serviços", "o que você faz", "o que faz"]):
                fallback_msg = "Opa! Eu ajudo com várias coisas: relatórios da empresa, problemas técnicos, agendamentos... O que você precisa? 😊"
            elif any(word in user_input for word in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
                fallback_msg = "Oi! Tudo bem? Como posso te ajudar hoje? 😊"
            else:
                import random
                fallback_options = [
                    "Eita, tive um probleminha técnico aqui! 🔧 Mas já voltei! O que você precisa?",
                    "Ops, me confundi! 😅 Pode repetir? Prometo prestar atenção!",
                    "Desculpa, deu uma travadinha! Mas tô aqui! Como posso ajudar?"
                ]
                fallback_msg = random.choice(fallback_options)
            state["agent_response"] = {
                "text": fallback_msg,
                "confidence": 0.7,
                "next_agent": "reception_agent",
                "metadata": {"error": str(e), "error_type": type(e).__name__}
            }
            state["current_agent"] = "reception_agent"
            logger.info(f"[ReceptionNode] Fallback response sent: {fallback_msg}")
        return state
    
    async def _classification_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de classificação com logs detalhados e tratamento robusto de erros"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            intent_analysis = await self.llm_service.classify_intent(state["user_input"], state["session_id"])
            state["intent_analysis"] = intent_analysis
            response = await self.agents["classification_agent"].process_message(message, session)
            if not response or not getattr(response, 'response_text', None):
                logger.error(f"[ClassificationNode] Resposta vazia ou inválida do agente: {response}")
                response = AgentResponse(
                    agent_id="classification_agent",
                    response_text="Erro na classificação. Pode tentar de novo?",
                    confidence=0.0,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "empty_response"}
                )
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "classification_agent"
            logger.info(f"[ClassificationNode] Resposta gerada com sucesso: {response.response_text}")
        except Exception as e:
            logger.error(f"Classification node error: {e}")
            state["agent_response"] = {"text": "Erro na classificação", "confidence": 0.0, "next_agent": "reception_agent", "metadata": {"error": str(e)}}
        return state
    
    async def _data_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de dados com logs detalhados e tratamento robusto de erros"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            response = await self.agents["data_agent"].process_message(message, session)
            if not response or not getattr(response, 'response_text', None):
                logger.error(f"[DataNode] Resposta vazia ou inválida do agente: {response}")
                response = AgentResponse(
                    agent_id="data_agent",
                    response_text="Erro nos dados. Pode tentar de novo?",
                    confidence=0.0,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "empty_response"}
                )
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "data_agent"
            logger.info(f"[DataNode] Resposta gerada com sucesso: {response.response_text}")
        except Exception as e:
            logger.error(f"Data node error: {e}")
            state["agent_response"] = {"text": "Erro nos dados", "confidence": 0.0, "next_agent": "reception_agent", "metadata": {"error": str(e)}}
        return state
    
    async def _support_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de suporte com logs detalhados e tratamento robusto de erros"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            response = await self.agents["support_agent"].process_message(message, session)
            if not response or not getattr(response, 'response_text', None):
                logger.error(f"[SupportNode] Resposta vazia ou inválida do agente: {response}")
                response = AgentResponse(
                    agent_id="support_agent",
                    response_text="Erro no suporte. Pode tentar de novo?",
                    confidence=0.0,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"error": "empty_response"}
                )
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "support_agent"
            logger.info(f"[SupportNode] Resposta gerada com sucesso: {response.response_text}")
        except Exception as e:
            logger.error(f"Support node error: {e}")
            state["agent_response"] = {"text": "Erro no suporte", "confidence": 0.0, "next_agent": "reception_agent", "metadata": {"error": str(e)}}
        return state
    
    async def _intent_router_node(self, state: ConversationState) -> ConversationState:
        try:
            # Lógica de roteamento baseada em intenção
            user_input_lower = state["user_input"].lower()
            # PRIORIDADE 1: Detecta intenção de dados/relatórios
            data_keywords = [
                "dados", "relatório", "relatorio", "relatórios", "relatorios",
                "kpi", "dashboard", "vendas", "faturamento", "receita",
                "métrica", "metrica", "análise", "analise", "números", "numeros",
                "estatística", "estatistica", "performance", "desempenho",
                "resultado", "balanço", "balanco", "cliente", "clientes"
            ]
            if any(word in user_input_lower for word in data_keywords):
                logger.info("[Router] Detectada intenção de dados - roteando direto para data_agent")
                state["routing_decision"] = "data"
                state["intent_analysis"] = {
                    "intent": "data_query",
                    "confidence": 0.9,
                    "reasoning": "Palavras-chave de dados/relatórios detectadas"
                }
                return state
            # PRIORIDADE 2: Problemas técnicos
            support_keywords = [
                "erro", "problema", "bug", "não funciona", "nao funciona", 
                "travou", "lento", "parou", "falha", "crash"
            ]
            if any(word in user_input_lower for word in support_keywords):
                logger.info("[Router] Detectada intenção de suporte - roteando para support_agent")
                state["routing_decision"] = "support"
                state["intent_analysis"] = {
                    "intent": "technical_support",
                    "confidence": 0.9,
                    "reasoning": "Problema técnico detectado"
                }
                return state
            # PRIORIDADE 3: Comandos de navegação
            if any(word in user_input_lower for word in ["menu", "voltar", "início", "iniciar"]):
                state["routing_decision"] = "reception"
                state["intent_analysis"] = {
                    "intent": "reception",
                    "confidence": 0.95,
                    "reasoning": "Comando de navegação"
                }
                return state
            # PRIORIDADE 4: Se já tem agente ativo, mantém
            current_agent = state.get("current_agent")
            if current_agent and current_agent != "reception_agent":
                # Mantém no agente atual
                agent_map = {
                    "data_agent": "data",
                    "support_agent": "support",
                    "classification_agent": "classification"
                }
                state["routing_decision"] = agent_map.get(current_agent, "reception")
                logger.info(f"[Router] Mantendo no agente atual: {current_agent}")
                return state
            # DEFAULT: Reception para casos gerais
            state["routing_decision"] = "reception"
            state["intent_analysis"] = {
                "intent": "general_chat",
                "confidence": 0.5,
                "reasoning": "Conversa geral ou saudação"
            }
        except Exception as e:
            logger.error(f"Intent router error: {e}")
            state["routing_decision"] = "reception"
        return state
    
    def _route_to_agent(self, state: ConversationState) -> str:
        routing = state.get("routing_decision", "reception")
        routing_map = {
            "reception": "reception",
            "classification": "classification",
            "data": "data_analysis", 
            "support": "technical_support"
        }
        return routing_map.get(routing, "reception")
    
    def _should_continue_conversation(self, state: ConversationState) -> str:
        """Determina se deve continuar a conversa"""
        if state.get("conversation_complete", False):
            return "end"
        # Verifica se há redirecionamento para outro agente
        next_agent = state["agent_response"].get("next_agent")
        if next_agent and next_agent != state["current_agent"]:
            state["current_agent"] = next_agent
            return "continue"
        return "end"
    
    def _create_error_response(self, error: str) -> AgentResponse:
        """Cria resposta de erro"""
        return AgentResponse(
            agent_id="system",
            response_text="Ops! Ocorreu um erro interno. Nossa equipe foi notificada. Tente novamente ou digite 'menu'.",
            confidence=0.0,
            should_continue=False,
            next_agent="reception_agent",
            metadata={"error": error}
        )
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """Status do workflow"""
        return {
            "workflow_compiled": self.workflow is not None,
            "agents_count": len(self.agents),
            "available_agents": list(self.agents.keys()),
            "llm_service_status": await self.llm_service.get_service_status()
        }

    async def _response_formatter_node(self, state: ConversationState) -> ConversationState:
        """Nó de formatação de resposta (pode ser expandido para customização futura)"""
        return state