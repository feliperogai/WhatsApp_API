from typing import List, Dict, Any
from langchain.tools import BaseTool, tool
import random
from datetime import datetime, timedelta

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

# Ferramentas específicas para o Data Agent
@tool
def get_sales_data() -> Dict[str, Any]:
    """Obtém dados de vendas atuais"""
    return {
        "vendas_mes": 125000 + random.randint(-10000, 20000),
        "vendas_anterior": 98000 + random.randint(-5000, 15000),
        "clientes_ativos": 1247 + random.randint(-50, 100),
        "conversion_rate": round(3.2 + random.uniform(-0.5, 0.8), 1),
        "tickets_abertos": random.randint(15, 35),
        "crescimento_mensal": round(random.uniform(5.0, 25.0), 1)
    }

@tool
def get_dashboard_metrics() -> Dict[str, Any]:
    """Obtém métricas do dashboard executivo"""
    return {
        "revenue_total": 1250000 + random.randint(-50000, 100000),
        "revenue_recurring": 800000 + random.randint(-30000, 50000),
        "customer_acquisition_cost": round(random.uniform(50, 150), 2),
        "lifetime_value": round(random.uniform(500, 1500), 2),
        "churn_rate": round(random.uniform(2.0, 8.0), 1),
        "nps_score": random.randint(45, 85),
        "active_users_monthly": random.randint(8000, 12000),
        "server_uptime": round(random.uniform(95.0, 99.9), 1)
    }

@tool  
def get_customer_analytics() -> Dict[str, Any]:
    """Obtém análises detalhadas de clientes"""
    return {
        "total_customers": 1247 + random.randint(-50, 100),
        "new_customers_30d": random.randint(80, 200),
        "returning_customers": random.randint(300, 600),
        "inactive_customers": random.randint(150, 400),
        "segments": {
            "premium": round(random.uniform(15, 30), 1),
            "standard": round(random.uniform(40, 55), 1),
            "basic": round(random.uniform(20, 35), 1)
        },
        "avg_session_duration": round(random.uniform(15, 45), 1),
        "bounce_rate": round(random.uniform(20, 40), 1)
    }

@tool
def get_performance_metrics() -> Dict[str, Any]:
    """Obtém métricas de performance do sistema"""
    return {
        "api_response_time": round(random.uniform(100, 500), 0),
        "database_performance": round(random.uniform(80, 99), 1),
        "error_rate": round(random.uniform(0.1, 2.0), 2),
        "concurrent_users": random.randint(200, 800),
        "bandwidth_usage": round(random.uniform(60, 95), 1),
        "storage_usage": round(random.uniform(45, 85), 1),
        "backup_status": "success" if random.random() > 0.1 else "warning",
        "last_backup": (datetime.now() - timedelta(hours=random.randint(1, 24))).strftime("%d/%m/%Y %H:%M")
    }

class LLMDataAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        tools = [get_sales_data, get_dashboard_metrics, get_customer_analytics, get_performance_metrics]
        super().__init__(
            agent_id="data_agent",
            name="Agente de Dados e Analytics IA",
            description="Especialista IA em análise de dados, relatórios e insights de negócio",
            llm_service=llm_service,
            tools=tools
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, e agora está na área de dados e relatórios do Jarvis!

    PERSONALIDADE:
    - Continue sendo amigável e natural
    - Explique números de forma simples
    - Use analogias quando ajudar
    - Celebre boas notícias com o usuário!

    COMO APRESENTAR DADOS:
    - Use emojis para deixar visual: 📈📊💰
    - Destaque o que é mais importante
    - Compare com períodos anteriores
    - Sugira próximos passos

    FORMATO EXEMPLO:
    "Opa! Olha só que legal os números desse mês! 🎉

    Vendas: R$ 125.000 (subiu 27% 📈)
    Clientes novos: 89 pessoas
    Ticket médio: R$ 100

    Tá indo super bem! Quer ver mais algum detalhe específico?"

    IMPORTANTE:
    - Fale dos números como conquistas
    - Seja otimista mas honesto
    - Não use jargões técnicos
    - Pergunte se quer mais detalhes"""
    
    def _get_tools(self) -> List[BaseTool]:
        return [get_sales_data, get_dashboard_metrics, get_customer_analytics, get_performance_metrics]
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return intent == "data_query"
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Identifica qual tipo de dados o usuário quer
        user_input = (message.body or "").lower()
        
        # Adiciona contexto sobre tipo de consulta
        query_type = "general"
        if any(word in user_input for word in ["vendas", "receita", "faturamento"]):
            query_type = "sales"
        elif any(word in user_input for word in ["dashboard", "resumo", "kpi"]):
            query_type = "dashboard"
        elif any(word in user_input for word in ["clientes", "customers", "usuários"]):
            query_type = "customers"
        elif any(word in user_input for word in ["performance", "sistema", "servidor"]):
            query_type = "performance"
        
        additional_context = {
            "query_type": query_type,
            "user_message": message.body,
            "available_data_sources": ["sales", "dashboard", "customers", "performance"],
            "tools_available": [tool.__name__ for tool in self._get_tools()]
        }
        
        # Adiciona dados relevantes baseado no tipo de consulta
        if query_type == "sales":
            additional_context["sales_data"] = get_sales_data()
        elif query_type == "dashboard":
            additional_context["dashboard_data"] = get_dashboard_metrics()
        elif query_type == "customers":
            additional_context["customer_data"] = get_customer_analytics()
        elif query_type == "performance":
            additional_context["performance_data"] = get_performance_metrics()
        else:
            # Para consultas gerais, inclui resumo de tudo
            additional_context["summary_data"] = {
                "sales": get_sales_data(),
                "dashboard": get_dashboard_metrics(),
                "customers": get_customer_analytics(),
                "performance": get_performance_metrics()
            }
        
        # Atualiza contexto da sessão
        session.update_context("query_type", query_type)
        session.update_context("last_data_request", datetime.now().isoformat())
        
        # Processa com contexto específico
        response = await super().process_message(message, session)
        
        # Verifica se usuário quer sair ou fazer nova consulta
        response_text = response.response_text.lower()
        if any(word in user_input for word in ["sair", "voltar", "menu", "principal"]):
            response.next_agent = "reception_agent"
        elif any(word in user_input for word in ["outro", "nova", "diferente"]):
            response.next_agent = self.agent_id  # Continua no data agent
        
        # Adiciona metadados específicos
        response.metadata.update({
            "query_type": query_type,
            "data_sources_used": additional_context.get("tools_available", []),
            "timestamp": datetime.now().isoformat()
        })
        
        return response
    
    def get_priority(self) -> int:
        return 7