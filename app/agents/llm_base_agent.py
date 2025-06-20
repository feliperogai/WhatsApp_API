from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import BaseTool
from langchain.schema import SystemMessage, HumanMessage
from langchain.memory import ConversationBufferWindowMemory
import logging

from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class LLMBaseAgent(BaseAgent):
    def __init__(
        self, 
        agent_id: str, 
        name: str, 
        description: str,
        llm_service: LLMService,
        tools: List[BaseTool] = None
    ):
        super().__init__(agent_id, name, description)
        self.llm_service = llm_service
        self.tools = tools or []
        self.system_prompt = self._get_system_prompt()
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Retorna o prompt do sistema para este agente"""
        pass
    
    @abstractmethod
    def _get_tools(self) -> List[BaseTool]:
        """Retorna as ferramentas disponíveis para este agente"""
        return []
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Usa LLM para determinar se pode processar a mensagem"""
        
        # Se é o agente ativo na sessão
        if session.current_agent == self.agent_id:
            return True
        
        # Usa LLM para classificar
        classification = await self.llm_service.classify_intent(
            message.body or "", 
            session.session_id
        )
        
        # Verifica se a intenção é compatível
        return self._is_intent_compatible(classification.get("intent", ""))
    
    @abstractmethod
    def _is_intent_compatible(self, intent: str) -> bool:
        """Verifica se a intenção é compatível com este agente"""
        pass
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem usando LLM"""
        
        try:
            # Constrói contexto
            context = self._build_context(message, session)
            
            # Gera resposta
            response_text = await self.llm_service.generate_response(
                prompt=message.body or "",
                system_message=self.system_prompt,
                session_id=session.session_id,
                context=context
            )
            
            # Determina próximo agente
            next_agent = await self._determine_next_agent(response_text, session)
            
            # Extrai metadados da resposta
            metadata = self._extract_metadata(response_text)
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=self._clean_response(response_text),
                confidence=0.9,
                should_continue=True,
                next_agent=next_agent,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error processing message in {self.agent_id}: {e}")
            return self._create_error_response(str(e))
    
    def _build_context(self, message: WhatsAppMessage, session: UserSession) -> Dict[str, Any]:
        """Constrói contexto para o LLM"""
        return {
            "agent_info": {
                "id": self.agent_id,
                "name": self.name,
                "description": self.description
            },
            "user_info": {
                "phone_number": session.phone_number,
                "session_id": session.session_id
            },
            "conversation_context": session.conversation_context,
            "message_history_count": len(session.message_history),
            "current_timestamp": message.timestamp.isoformat()
        }
    
    async def _determine_next_agent(self, response: str, session: UserSession) -> Optional[str]:
        """Determina próximo agente baseado na resposta"""
        
        # Palavras-chave para redirecionamento
        redirects = {
            "reception_agent": ["menu", "início", "voltar", "principal"],
            "data_agent": ["relatório", "dados", "dashboard", "kpi"],
            "support_agent": ["suporte", "problema", "erro", "bug"],
            "classification_agent": ["classificar", "analisar", "identificar"]
        }
        
        response_lower = response.lower()
        
        for agent_id, keywords in redirects.items():
            if any(keyword in response_lower for keyword in keywords):
                return agent_id
        
        # Mantém no agente atual por padrão
        return self.agent_id
    
    def _extract_metadata(self, response: str) -> Dict[str, Any]:
        """Extrai metadados da resposta do LLM"""
        metadata = {}
        
        # Procura por marcadores especiais na resposta
        if "🔄" in response:
            metadata["requires_redirect"] = True
        if "⚠️" in response:
            metadata["warning"] = True
        if "✅" in response:
            metadata["success"] = True
        if "❌" in response:
            metadata["error"] = True
        
        return metadata
    
    def _clean_response(self, response: str) -> str:
        """Limpa a resposta removendo marcadores especiais"""
        # Remove possíveis artefatos de formatação
        response = response.replace("```", "")
        response = response.replace("**", "")
        
        # Remove linhas vazias excessivas
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def _create_error_response(self, error: str) -> AgentResponse:
        """Cria resposta de erro"""
        return AgentResponse(
            agent_id=self.agent_id,
            response_text="Desculpe, ocorreu um erro interno. Tente novamente ou digite 'menu' para voltar ao início.",
            confidence=0.0,
            should_continue=False,
            next_agent="reception_agent",
            metadata={"error": error}
        )