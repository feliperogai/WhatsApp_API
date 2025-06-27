from typing import List, Dict, Any
from langchain.tools import BaseTool, tool
import random
from datetime import datetime, timedelta
import re

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

class DataCollector:
    """Coletor e validador de dados cadastrais para o DataAgent"""
    @staticmethod
    def extract_info(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        extracted = {}
        text_lower = text.lower()
        cliente = context.get("cliente", {})
        # CNPJ
        if not cliente.get("cnpj"):
            cnpj_pattern = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}'
            cnpj_match = re.search(cnpj_pattern, text)
            if cnpj_match:
                extracted["cnpj"] = DataCollector.format_cnpj(cnpj_match.group())
        # Nome da empresa
        if not cliente.get("empresa"):
            empresa_patterns = [
                r'(?:empresa|trabalho na|sou da|represento a?)\s+([A-Za-zÀ-ÿ0-9\s&\-\.]+)',
                r'(?:da|na)\s+([A-Z][A-Za-zÀ-ÿ0-9\s&\-\.]+(?:LTDA|ME|SA|S\.A\.|Ltd|Inc)?)',
            ]
            for pattern in empresa_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    empresa = match.group(1).strip()
                    if len(empresa) > 2:
                        extracted["empresa"] = empresa
                        break
        # Só coleta dados do usuário se CNPJ e empresa já estão válidos
        temp_cliente = dict(cliente)
        temp_cliente.update(extracted)
        valids = DataCollector.validate_all(temp_cliente)
        if valids["cnpj"] and valids["empresa"]:
            # Nome do usuário
            if not cliente.get("nome"):
                name_patterns = [
                    r'(?:meu nome é|me chamo|sou o?a?|aqui é o?a?)\s+([A-Za-zÀ-ÿ\s]+)',
                    r'(?:é o?a?)\s+([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.)',
                    r'^([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.|\!)',
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        nome = match.group(1).strip().title()
                        if len(nome.split()) <= 5 and len(nome) > 2:
                            extracted["nome"] = nome
                            break
            # Email
            if not cliente.get("email"):
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                email_match = re.search(email_pattern, text)
                if email_match:
                    extracted["email"] = email_match.group().lower()
            # Cargo
            if not cliente.get("cargo"):
                cargo_pattern = r'(?:cargo|sou|trabalho como|minha função é)\s*:?
*([A-Za-zÀ-ÿ\s]+)'
                cargo_match = re.search(cargo_pattern, text, re.IGNORECASE)
                if cargo_match:
                    cargo = cargo_match.group(1).strip().title()
                    if len(cargo) > 2 and len(cargo) < 40:
                        extracted["cargo"] = cargo
        return extracted

    @staticmethod
    def format_cnpj(cnpj: str) -> str:
        numbers = re.sub(r'[^0-9]', '', cnpj)
        if len(numbers) == 14:
            return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"
        return cnpj

    @staticmethod
    def validate_all(cliente: Dict[str, Any]) -> Dict[str, bool]:
        """Valida todos os campos necessários"""
        def valid_cnpj(cnpj):
            return bool(re.match(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', cnpj))
        def valid_email(email):
            return bool(re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email))
        return {
            "cnpj": valid_cnpj(cliente.get("cnpj", "")),
            "empresa": bool(cliente.get("empresa")),
            "nome": bool(cliente.get("nome")),
            "email": valid_email(cliente.get("email", "")),
            "cargo": bool(cliente.get("cargo")),
        }

    @staticmethod
    def get_missing_or_invalid(cliente: Dict[str, Any]) -> list:
        """Retorna a ordem dos campos faltantes ou inválidos, priorizando empresa antes do usuário"""
        valids = DataCollector.validate_all(cliente)
        missing = []
        # Sempre prioriza empresa
        if not valids["cnpj"]:
            missing.append("CNPJ da empresa")
        if not valids["empresa"]:
            missing.append("nome da empresa")
        # Só pede dados do usuário se empresa estiver completa
        if valids["cnpj"] and valids["empresa"]:
            if not valids["nome"]:
                missing.append("seu nome")
            if not valids["email"]:
                missing.append("seu email")
            if not valids["cargo"]:
                missing.append("seu cargo")
        return missing

    @staticmethod
    def natural_request(missing: str) -> str:
        pedidos = {
            "CNPJ da empresa": [
                "Antes de mostrar os dados, preciso do CNPJ da empresa. Pode informar?",
                "Qual o CNPJ da empresa, por favor?",
                "Me passa o CNPJ da empresa para eu liberar os dados."
            ],
            "nome da empresa": [
                "Qual o nome da empresa?",
                "Preciso do nome da empresa para continuar. Pode informar?",
                "Me diz o nome da empresa, por favor."
            ],
            "seu nome": [
                "Agora preciso do seu nome. Como você se chama?",
                "Qual o seu nome completo?",
                "Me diz seu nome, por favor."
            ],
            "seu email": [
                "Qual seu email de contato?",
                "Me passa seu email, por favor.",
                "Preciso do seu email para continuar."
            ],
            "seu cargo": [
                "Qual o seu cargo na empresa?",
                "Me diz seu cargo, por favor.",
                "Para finalizar, qual o seu cargo?"
            ]
        }
        return random.choice(pedidos.get(missing, [f"Por favor, informe: {missing}"]))

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
        self.data_collector = DataCollector()
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, agora mostrando dados e relatórios de forma empolgante!

PERSONALIDADE:
- Fale naturalmente, como uma pessoa
- Seja didático, mas não robótico
- Use linguagem simples e clara

QUANDO RESPONDER:
- Se a pessoa pedir dados, relatórios, dashboards, KPIs, etc.
- Se não tiver certeza, pergunte mais detalhes

IMPORTANTE:
- NUNCA mencione "dados internos" ou "API"
- Apenas mostre as informações de forma útil
- Se não entender, pergunte: "Pode detalhar melhor o que você quer ver?"

Seja natural, prestativo e empolgado!"""
    
    def _get_tools(self) -> List[BaseTool]:
        return [get_sales_data, get_dashboard_metrics, get_customer_analytics, get_performance_metrics]
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return intent == "data_query"
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Coleta e valida dados cadastrais antes de responder
        cliente = session.conversation_context.get("cliente", {})
        # Extrai dados do texto
        extracted = self.data_collector.extract_info(message.body or "", session.conversation_context)
        if extracted:
            if "cliente" not in session.conversation_context:
                session.conversation_context["cliente"] = {}
            session.conversation_context["cliente"].update(extracted)
            cliente = session.conversation_context["cliente"]
        # Valida e pede o que falta
        missing = self.data_collector.get_missing_or_invalid(cliente)
        if missing:
            pedido = self.data_collector.natural_request(missing[0])
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=pedido,
                confidence=0.8,
                should_continue=True,
                next_agent=self.agent_id,
                metadata={"missing": missing}
            )
        
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
            "tools_available": [type(tool).__name__ for tool in self._get_tools()]
        }
        
        # Adiciona dados relevantes baseado no tipo de consulta
        if query_type == "sales":
            additional_context["sales_data"] = get_sales_data.invoke({})
        elif query_type == "dashboard":
            additional_context["dashboard_data"] = get_dashboard_metrics.invoke({})
        elif query_type == "customers":
            additional_context["customer_data"] = get_customer_analytics.invoke({})
        elif query_type == "performance":
            additional_context["performance_data"] = get_performance_metrics.invoke({})
        else:
            # Para consultas gerais, inclui resumo de tudo
            additional_context["summary_data"] = {
                "sales": get_sales_data.invoke({}),
                "dashboard": get_dashboard_metrics.invoke({}),
                "customers": get_customer_analytics.invoke({}),
                "performance": get_performance_metrics.invoke({})
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