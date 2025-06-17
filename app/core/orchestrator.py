orchestrator_py = ""
from typing import List, Optional, Dict, Any
import asyncio
import logging
from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.core.session_manager import SessionManager
from app.agents.agent_1 import ReceptionAgent
from app.agents.agent_2 import ClassificationAgent
from app.agents.agent_3 import DataAgent
from app.agents.agent_4 import SupportAgent

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_execution_order: List[str] = []
        self._initialize_agents()
    
    def _initialize_agents(self):
        agents = [
            ReceptionAgent(),
            ClassificationAgent(), 
            DataAgent(),
            SupportAgent()
        ]
        
        for agent in agents:
            self.register_agent(agent)
            logger.info(f"Agent registered: {agent.agent_id}")
    
    def register_agent(self, agent: BaseAgent):
        self.agents[agent.agent_id] = agent
        
        # Ordena agentes por prioridade
        self.agent_execution_order = sorted(
            self.agents.keys(),
            key=lambda aid: self.agents[aid].get_priority(),
            reverse=True
        )
    
    async def process_message(self, message: WhatsAppMessage) -> AgentResponse:
        try:
            # Obtém ou cria sessão do usuário
            session = await self.session_manager.get_or_create_session(message.from_number)
            
            # Adiciona mensagem ao histórico
            session.add_message(message.body or "", "user")
            
            # Determina qual agente deve processar
            active_agent = await self._determine_active_agent(message, session)
            
            if not active_agent:
                logger.warning(f"No agent found for message from {message.from_number}")
                return self._create_fallback_response()
            
            # Processa a mensagem
            response = await self._execute_agent(active_agent, message, session)
            
            # Atualiza sessão com resposta
            session.add_message(response.response_text, "agent", active_agent.agent_id)
            session.current_agent = response.next_agent or active_agent.agent_id
            
            # Salva sessão atualizada
            await self.session_manager.save_session(session)
            
            logger.info(f"Message processed by {active_agent.agent_id} for {message.from_number}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return self._create_error_response(str(e))
    
    async def _determine_active_agent(self, message: WhatsAppMessage, session: UserSession) -> Optional[BaseAgent]:
        
        # Se há um agente ativo na sessão, verifica se ele pode processar
        if session.current_agent and session.current_agent in self.agents:
            current_agent = self.agents[session.current_agent]
            if await current_agent.can_handle(message, session):
                return current_agent
        
        # Caso contrário, verifica todos os agentes por ordem de prioridade
        for agent_id in self.agent_execution_order:
            agent = self.agents[agent_id]
            if agent.is_active and await agent.can_handle(message, session):
                return agent
        
        # Fallback para agente de recepção
        return self.agents.get("reception_agent")
    
    async def _execute_agent(self, agent: BaseAgent, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        try:
            # Pré-processamento
            await agent.preprocess(message, session)
            
            # Processamento principal
            response = await agent.process_message(message, session)
            
            # Pós-processamento
            response = await agent.postprocess(response, session)
            
            # Log da interação
            agent.log_interaction(message, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error executing agent {agent.agent_id}: {str(e)}")
            return AgentResponse(
                agent_id=agent.agent_id,
                response_text=f"Desculpe, ocorreu um erro interno. Tente novamente em alguns instantes.",
                confidence=0.0,
                should_continue=False,
                next_agent="reception_agent"
            )
    
    def _create_fallback_response(self) -> AgentResponse:
        return AgentResponse(
            agent_id="system",
            response_text="Desculpe, não consegui processar sua mensagem. Digite 'menu' para ver as opções disponíveis.",
            confidence=0.1,
            should_continue=True,
            next_agent="reception_agent"
        )
    
    def _create_error_response(self, error: str) -> AgentResponse:
        return AgentResponse(
            agent_id="system",
            response_text="Ops! Ocorreu um erro interno. Nossa equipe foi notificada. Tente novamente em alguns instantes.",
            confidence=0.0,
            should_continue=False,
            next_agent="reception_agent",
            metadata={"error": error}
        )
    
    async def get_agent_status(self) -> Dict[str, Any]:
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "name": agent.name,
                "description": agent.description,
                "is_active": agent.is_active,
                "priority": agent.get_priority()
            }
        return status
    
    async def reset_session(self, phone_number: str):
        await self.session_manager.delete_session(phone_number)
        logger.info(f"Session reset for {phone_number}") 
