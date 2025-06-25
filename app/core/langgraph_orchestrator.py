from typing import Dict, Any, List, Optional, TypedDict, Annotated
import logging
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain.schema import BaseMessage, HumanMessage, AIMessage

from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.core.session_manager import SessionManager
from app.services.llm_service import LLMService
from app.agents.llm_reception_agent import LLMReceptionAgent
from app.agents.llm_classification_agent import LLMClassificationAgent
from app.agents.llm_data_agent import LLMDataAgent
from app.agents.llm_support_agent import LLMSupportAgent

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
            "reception_agent": LLMReceptionAgent(self.llm_service),
            "classification_agent": LLMClassificationAgent(self.llm_service),
            "data_agent": LLMDataAgent(self.llm_service),
            "support_agent": LLMSupportAgent(self.llm_service)
        }
        logger.info("LangGraph agents initialized")
    
    def _build_workflow(self):
        """Constrói o workflow do LangGraph"""
        
        # Cria o grafo de estado
        workflow = StateGraph(ConversationState)
        
        # Adiciona nós (agentes)
        workflow.add_node("reception", self._reception_node)
        workflow.add_node("classification", self._classification_node)
        workflow.add_node("data_analysis", self._data_node)
        workflow.add_node("technical_support", self._support_node)
        workflow.add_node("intent_router", self._intent_router_node)
        workflow.add_node("response_formatter", self._response_formatter_node)
        
        # Define ponto de entrada
        workflow.set_entry_point("intent_router")
        
        # Define transições condicionais
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
        
        # Transições de cada agente para o formatador
        workflow.add_edge("reception", "response_formatter")
        workflow.add_edge("classification", "response_formatter")
        workflow.add_edge("data_analysis", "response_formatter")
        workflow.add_edge("technical_support", "response_formatter")
        
        # Transições do formatador
        workflow.add_conditional_edges(
            "response_formatter",
            self._should_continue_conversation,
            {
                "continue": "intent_router",
                "end": END
            }
        )
        
        # Compila o workflow
        self.workflow = workflow.compile()
        logger.info("LangGraph workflow built successfully")
    
    async def process_message(self, message: WhatsAppMessage) -> AgentResponse:
        """Processa mensagem através do LangGraph"""
        try:
            # Obtém ou cria sessão - IMPORTANTE: a sessão é criada aqui, não passada como parâmetro
            session = await self.session_manager.get_or_create_session(message.from_number)
            
            logger.info(f"Processing message for session: {session.session_id}")
            
            # Prepara estado inicial
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
            
            # Executa workflow
            logger.info("Invoking LangGraph workflow...")
            final_state = await self.workflow.ainvoke(initial_state)
            
            logger.info(f"Workflow completed. Agent response: {final_state.get('agent_response', {})}")
            
            # Constrói resposta
            response = AgentResponse(
                agent_id=final_state.get("current_agent", "system"),
                response_text=final_state.get("agent_response", {}).get("text", "Desculpe, não consegui processar sua mensagem."),
                confidence=final_state.get("agent_response", {}).get("confidence", 0.0),
                should_continue=not final_state.get("conversation_complete", False),
                next_agent=final_state.get("agent_response", {}).get("next_agent"),
                metadata=final_state.get("agent_response", {}).get("metadata", {})
            )
            
            # Atualiza sessão
            session.add_message(message.body or "", "user")
            session.add_message(response.response_text, "agent", response.agent_id)
            session.current_agent = response.next_agent or response.agent_id
            session.conversation_context.update(final_state.get("context", {}))
            
            await self.session_manager.save_session(session)
            
            logger.info(f"Message processed successfully by {response.agent_id}")
            return response
            
        except Exception as e:
            logger.error(f"LangGraph processing error: {e}", exc_info=True)
            return self._create_error_response(str(e))
    
    async def _reception_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de recepção"""
        import traceback
        logger.info(f"[ReceptionNode] Iniciando processamento para {state['phone_number']} | input: {state['user_input']}")
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            logger.info(f"[ReceptionNode] Sessão recuperada: {session}")
            logger.info(f"[ReceptionNode] Conteúdo da sessão: {session.__dict__ if session else 'None'}")
            logger.info(f"[ReceptionNode] Estado recebido: {state}")
            if session is None:
                logger.warning(f"[ReceptionNode] Nenhuma sessão encontrada para {state['phone_number']}. Criando nova sessão.")
                session = await self.session_manager.get_or_create_session(state["phone_number"])
                logger.info(f"[ReceptionNode] Nova sessão criada: {session.__dict__}")
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            logger.info(f"[ReceptionNode] Mensagem criada: {message.__dict__}")
            response = await self.agents["reception_agent"].process_message(message, session)
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "reception_agent"
            logger.info(f"[ReceptionNode] Resposta gerada: {response.response_text}")
        except Exception as e:
            logger.error(f"Reception node error: {e}")
            logger.error(traceback.format_exc())
            fallback = "Oi! Tive um probleminha aqui, mas já estou pronto para te ajudar. Pode repetir sua mensagem ou digitar 'menu' para ver opções."
            state["agent_response"] = {"text": fallback, "confidence": 0.0}
        return state
    
    async def _classification_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de classificação"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            
            # Faz classificação de intenção
            intent_analysis = await self.llm_service.classify_intent(state["user_input"], state["session_id"])
            state["intent_analysis"] = intent_analysis
            
            response = await self.agents["classification_agent"].process_message(message, session)
            
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "classification_agent"
            
        except Exception as e:
            logger.error(f"Classification node error: {e}")
            state["agent_response"] = {"text": "Erro na classificação", "confidence": 0.0}
        
        return state
    
    async def _data_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de dados"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            
            response = await self.agents["data_agent"].process_message(message, session)
            
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "data_agent"
            
        except Exception as e:
            logger.error(f"Data node error: {e}")
            state["agent_response"] = {"text": "Erro nos dados", "confidence": 0.0}
        
        return state
    
    async def _support_node(self, state: ConversationState) -> ConversationState:
        """Nó do agente de suporte"""
        try:
            session = await self.session_manager.get_session(state["phone_number"])
            message = WhatsAppMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=state["phone_number"],
                to_number="system",
                body=state["user_input"]
            )
            
            response = await self.agents["support_agent"].process_message(message, session)
            
            state["agent_response"] = {
                "text": response.response_text,
                "confidence": response.confidence,
                "next_agent": response.next_agent,
                "metadata": response.metadata
            }
            state["current_agent"] = "support_agent"
            
        except Exception as e:
            logger.error(f"Support node error: {e}")
            state["agent_response"] = {"text": "Erro no suporte", "confidence": 0.0}
        
        return state
    
    async def _intent_router_node(self, state: ConversationState) -> ConversationState:
        """Nó roteador de intenções"""
        try:
            # Faz análise de intenção
            intent_analysis = await self.llm_service.classify_intent(
                state["user_input"], 
                state["session_id"]
            )
            state["intent_analysis"] = intent_analysis
            
            # Determina roteamento baseado na intenção e agente atual
            current_agent = state["current_agent"]
            intent = intent_analysis.get("intent", "")
            confidence = intent_analysis.get("confidence", 0.0)
            
            # Lógica de roteamento
            if not current_agent or current_agent == "reception_agent":
                if confidence > 0.7:
                    if intent == "data_query":
                        state["routing_decision"] = "data"
                    elif intent == "technical_support":
                        state["routing_decision"] = "support"
                    else:
                        state["routing_decision"] = "reception"
                else:
                    state["routing_decision"] = "classification"
            else:
                # Verifica se quer mudar de agente
                user_input_lower = state["user_input"].lower()
                if any(word in user_input_lower for word in ["menu", "voltar", "início"]):
                    state["routing_decision"] = "reception"
                elif intent == "data_query" and current_agent != "data_agent":
                    state["routing_decision"] = "data"
                elif intent == "technical_support" and current_agent != "support_agent":
                    state["routing_decision"] = "support"
                else:
                    # Mantém no agente atual
                    state["routing_decision"] = current_agent.replace("_agent", "")
            
        except Exception as e:
            logger.error(f"Intent router error: {e}")
            state["routing_decision"] = "reception"
        
        return state
    
    async def _response_formatter_node(self, state: ConversationState) -> ConversationState:
        """Nó formatador de resposta"""
        try:
            # NÃO adiciona rodapé técnico em conversas naturais
            response_text = state["agent_response"].get("text", "")
            
            # Remove qualquer JSON que possa ter vindo por engano
            if "{" in response_text and "intent" in response_text:
                # Tenta extrair apenas o texto útil
                lines = response_text.split('\n')
                response_text = '\n'.join([line for line in lines if not line.strip().startswith('{')])
            
            # Só adiciona menu em contextos específicos
            user_input_lower = state["user_input"].lower()
            agent_id = state["current_agent"]
            
            # NÃO adiciona rodapé automático - deixa a conversa fluir naturalmente
            # O agente já deve incluir sugestões contextuais quando apropriado
            
            state["agent_response"]["text"] = response_text.strip()
            
            # Determina se a conversa deve continuar
            farewell_words = ["tchau", "até", "adeus", "bye", "xau", "obrigado e tchau", "valeu tchau"]
            if any(word in user_input_lower for word in farewell_words):
                state["conversation_complete"] = True
            
        except Exception as e:
            logger.error(f"Response formatter error: {e}")
        
        return state
    
    def _route_to_agent(self, state: ConversationState) -> str:
        """Determina para qual agente rotear"""
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