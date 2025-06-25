from typing import List, Dict, Any
from langchain.tools import BaseTool, tool
import random
from datetime import datetime

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

# Ferramentas específicas para o Support Agent
@tool
def create_support_ticket(description: str, priority: str = "normal") -> Dict[str, Any]:
    """Cria um ticket de suporte"""
    ticket_id = f"TK{random.randint(10000, 99999)}"
    return {
        "ticket_id": ticket_id,
        "description": description,
        "priority": priority,
        "status": "Aberto",
        "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "estimated_resolution": "4 horas úteis" if priority == "normal" else "1 hora"
    }

@tool
def get_system_status() -> Dict[str, Any]:
    """Verifica status dos sistemas"""
    return {
        "api_status": "online" if random.random() > 0.05 else "maintenance",
        "database_status": "online" if random.random() > 0.02 else "slow",
        "cdn_status": "online" if random.random() > 0.1 else "degraded",
        "backup_status": "success" if random.random() > 0.05 else "warning",
        "uptime_percentage": round(random.uniform(96.0, 99.9), 1),
        "active_incidents": random.randint(0, 3),
        "last_update": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

@tool
def search_knowledge_base(query: str) -> Dict[str, Any]:
    """Busca soluções na base de conhecimento"""
    solutions = {
        "login": {
            "title": "Problemas de Login/Acesso",
            "solution": "1. Limpe cache do navegador\n2. Tente modo anônimo\n3. Verifique Caps Lock\n4. Use 'Esqueci senha'",
            "success_rate": "95%"
        },
        "performance": {
            "title": "Problemas de Performance",
            "solution": "1. Teste velocidade internet\n2. Feche outras abas\n3. Reinicie navegador\n4. Limpe cache",
            "success_rate": "88%"
        },
        "error": {
            "title": "Erros Gerais",
            "solution": "1. Recarregue a página\n2. Verifique console do navegador\n3. Tente em outro navegador\n4. Contate suporte",
            "success_rate": "75%"
        }
    }
    
    query_lower = query.lower()
    if "login" in query_lower or "senha" in query_lower:
        return solutions["login"]
    elif "lento" in query_lower or "performance" in query_lower:
        return solutions["performance"]
    else:
        return solutions["error"]

@tool
def escalate_to_specialist(issue_type: str, urgency: str = "normal") -> Dict[str, Any]:
    """Escalona para especialista"""
    specialist_info = {
        "network": {"name": "João Silva", "contact": "joao@empresa.com", "phone": "+5511999998888"},
        "security": {"name": "Maria Santos", "contact": "maria@empresa.com", "phone": "+5511999997777"},
        "database": {"name": "Carlos Lima", "contact": "carlos@empresa.com", "phone": "+5511999996666"},
        "general": {"name": "Suporte L2", "contact": "suporte@empresa.com", "phone": "+5511999999999"}
    }
    
    specialist = specialist_info.get(issue_type, specialist_info["general"])
    escalation_id = f"ESC{random.randint(1000, 9999)}"
    
    return {
        "escalation_id": escalation_id,
        "specialist": specialist,
        "urgency": urgency,
        "estimated_contact": "30 minutos" if urgency == "critical" else "2 horas",
        "escalated_at": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

class LLMSupportAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        tools = [create_support_ticket, get_system_status, search_knowledge_base, escalate_to_specialist]
        super().__init__(
            agent_id="support_agent",
            name="Agente de Suporte Técnico IA",
            description="Especialista IA em suporte técnico e resolução de problemas",
            llm_service=llm_service,
            tools=tools
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, agora ajudando com problemas técnicos!

    PERSONALIDADE:
    - Seja compreensivo e paciente
    - Mostre que entende a frustração
    - Dê soluções práticas e simples
    - Use humor leve quando apropriado

    COMO AJUDAR:
    1. Primeiro, mostre empatia: "Poxa, que chato isso!"
    2. Pergunte detalhes se precisar
    3. Dê passos simples e claros
    4. Ofereça alternativas

    FORMATO EXEMPLO:
    "Eita, erro 500 é chato mesmo! 😕

    Vamos tentar resolver:
    1. Primeiro, tenta limpar o cache do navegador
    2. Se não der, tenta modo anônimo
    3. Ainda com problema? Me avisa que escalo pro pessoal técnico!

    Geralmente o passo 1 já resolve. Tenta aí e me conta!"

    IMPORTANTE:
    - Não use termos muito técnicos
    - Seja positivo: "Vamos resolver isso!"
    - Se for grave, escalone mas mantenha a calma
    - Sempre acompanhe: "Deu certo?"""
    
    def _get_tools(self) -> List[BaseTool]:
        return [create_support_ticket, get_system_status, search_knowledge_base, escalate_to_specialist]
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return intent == "technical_support"
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        user_input = (message.body or "").lower()
        
        # Classifica tipo de problema
        issue_type = "general"
        priority = "normal"
        
        if any(word in user_input for word in ["crítico", "parou", "down", "urgente"]):
            priority = "critical"
        elif any(word in user_input for word in ["importante", "alto", "prioridade"]):
            priority = "high"
        
        if any(word in user_input for word in ["login", "senha", "acesso"]):
            issue_type = "authentication"
        elif any(word in user_input for word in ["lento", "performance", "travando"]):
            issue_type = "performance"
        elif any(word in user_input for word in ["erro", "bug", "falha"]):
            issue_type = "error"
        elif any(word in user_input for word in ["rede", "conexão", "internet"]):
            issue_type = "network"
        elif any(word in user_input for word in ["segurança", "hack", "vírus"]):
            issue_type = "security"
            priority = "critical"  # Sempre crítico
        
        # Adiciona contexto específico do suporte
        additional_context = {
            "issue_type": issue_type,
            "priority": priority,
            "user_message": message.body,
            "system_status": get_system_status.invoke({}),
            "knowledge_base_search": search_knowledge_base.invoke({"query": user_input}),
            "support_tools": [type(tool).__name__ for tool in self._get_tools()]
        }
        
        # Cria ticket automaticamente para problemas críticos
        if priority == "critical":
            ticket = create_support_ticket.invoke({"description": message.body or "Problema crítico", "priority": "critical"})
            additional_context["auto_ticket"] = ticket
        
        # Atualiza contexto da sessão
        session.update_context("issue_type", issue_type)
        session.update_context("priority", priority)
        session.update_context("support_session_start", datetime.now().isoformat())
        
        # Processa com contexto do suporte
        response = await super().process_message(message, session)
        
        # Verifica se precisa escalonar
        if priority == "critical" or any(word in user_input for word in ["especialista", "escalonar"]):
            escalation = escalate_to_specialist.invoke({"issue_type": issue_type, "urgency": priority})
            response.metadata["escalation"] = escalation
        
        # Controla fluxo de saída
        if any(word in user_input for word in ["resolvido", "obrigado", "funcionou", "sair"]):
            response.next_agent = "reception_agent"
        elif any(word in user_input for word in ["outro", "novo", "diferente"]):
            response.next_agent = self.agent_id
        
        # Adiciona metadados específicos
        response.metadata.update({
            "issue_type": issue_type,
            "priority": priority,
            "tools_used": [type(tool).__name__ for tool in self._get_tools()],
            "timestamp": datetime.now().isoformat()
        })
        
        return response
    
    def get_priority(self) -> int:
        return 6