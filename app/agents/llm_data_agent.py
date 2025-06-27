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
        """Extrai informações do texto com prioridade para dados da empresa"""
        extracted = {}
        text_lower = text.lower()
        cliente = context.get("cliente", {})
        
        # PRIORIDADE 1: CNPJ (sempre primeiro)
        if not cliente.get("cnpj"):
            cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}|\d{14}'
            cnpj_match = re.search(cnpj_pattern, text)
            if cnpj_match:
                extracted["cnpj"] = DataCollector.format_cnpj(cnpj_match.group())
        
        # PRIORIDADE 2: Nome da empresa (só depois do CNPJ)
        if cliente.get("cnpj") and not cliente.get("empresa"):
            empresa_patterns = [
                r'(?:empresa|trabalho na|sou da|represento a?)\s+([A-Za-zÀ-ÿ0-9\s&\-\.]+)',
                r'(?:da|na)\s+([A-Z][A-Za-zÀ-ÿ0-9\s&\-\.]+(?:LTDA|ME|SA|S\.A\.|Ltd|Inc)?)',
                # Padrão mais genérico para capturar nomes de empresa
                r'([A-Z][A-Za-zÀ-ÿ0-9\s&\-\.]{2,}(?:LTDA|ME|SA|S\.A\.|Ltd|Inc)?)'
            ]
            for pattern in empresa_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    empresa = match.group(1).strip()
                    # Valida se parece ser nome de empresa
                    if len(empresa) > 2 and not any(word in empresa.lower() for word in ["meu", "nome", "é", "sou"]):
                        extracted["empresa"] = empresa.title()
                        break
        
        # Só extrai dados do usuário se CNPJ e empresa já estão válidos
        if DataCollector._has_valid_company_data(dict(cliente, **extracted)):
            # PRIORIDADE 3: Nome do usuário
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
                            if not any(word in nome.lower() for word in ["oi", "olá", "bom", "boa"]):
                                extracted["nome"] = nome
                                break
            
            # PRIORIDADE 4: Email
            if not cliente.get("email"):
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                email_match = re.search(email_pattern, text)
                if email_match:
                    extracted["email"] = email_match.group().lower()
            
            # PRIORIDADE 5: Cargo
            if not cliente.get("cargo"):
                cargo_patterns = [
                    r'(?:cargo|sou|trabalho como|minha função é|atuo como)\s*:?\s*([A-Za-zÀ-ÿ\s]+)',
                    r'(?:diretor|gerente|analista|coordenador|supervisor|assistente|desenvolvedor|designer)(?:\s+[A-Za-zÀ-ÿ]+)*'
                ]
                for pattern in cargo_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        cargo = match.group(1) if match.groups() else match.group(0)
                        cargo = cargo.strip().title()
                        if len(cargo) > 2 and len(cargo) < 50:
                            extracted["cargo"] = cargo
                            break
        
        return extracted
    
    @staticmethod
    def format_cnpj(cnpj: str) -> str:
        """Formata CNPJ para o padrão XX.XXX.XXX/XXXX-XX"""
        numbers = re.sub(r'[^0-9]', '', cnpj)
        if len(numbers) == 14:
            return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"
        return cnpj
    
    @staticmethod
    def validate_cnpj(cnpj: str) -> bool:
        """Valida CNPJ com algoritmo completo"""
        # Remove formatação
        cnpj = re.sub(r'[^0-9]', '', cnpj)
        
        # Verifica se tem 14 dígitos
        if len(cnpj) != 14:
            return False
        
        # Verifica se não é sequência de números iguais
        if cnpj == cnpj[0] * 14:
            return False
        
        # Validação dos dígitos verificadores
        # Primeiro dígito
        soma = 0
        peso = 5
        for i in range(12):
            soma += int(cnpj[i]) * peso
            peso = peso - 1 if peso > 2 else 9
        
        digito1 = 11 - (soma % 11)
        digito1 = 0 if digito1 > 9 else digito1
        
        if int(cnpj[12]) != digito1:
            return False
        
        # Segundo dígito
        soma = 0
        peso = 6
        for i in range(13):
            soma += int(cnpj[i]) * peso
            peso = peso - 1 if peso > 2 else 9
        
        digito2 = 11 - (soma % 11)
        digito2 = 0 if digito2 > 9 else digito2
        
        return int(cnpj[13]) == digito2
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Valida formato de email"""
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_all(cliente: Dict[str, Any]) -> Dict[str, bool]:
        """Valida todos os campos necessários"""
        return {
            "cnpj": DataCollector.validate_cnpj(cliente.get("cnpj", "")),
            "empresa": bool(cliente.get("empresa") and len(cliente.get("empresa", "")) > 2),
            "nome": bool(cliente.get("nome") and len(cliente.get("nome", "")) > 2),
            "email": DataCollector.validate_email(cliente.get("email", "")),
            "cargo": bool(cliente.get("cargo") and len(cliente.get("cargo", "")) > 2),
        }
    
    @staticmethod
    def _has_valid_company_data(cliente: Dict[str, Any]) -> bool:
        """Verifica se os dados da empresa estão válidos"""
        valids = DataCollector.validate_all(cliente)
        return valids["cnpj"] and valids["empresa"]
    
    @staticmethod
    def get_missing_or_invalid(cliente: Dict[str, Any]) -> list:
        """Retorna campos faltantes ou inválidos, priorizando empresa"""
        valids = DataCollector.validate_all(cliente)
        missing = []
        
        # SEMPRE prioriza dados da empresa
        if not valids["cnpj"]:
            missing.append("CNPJ da empresa")
        if not valids["empresa"]:
            missing.append("nome da empresa")
        
        # Só pede dados do usuário se empresa estiver completa e válida
        if valids["cnpj"] and valids["empresa"]:
            if not valids["nome"]:
                missing.append("seu nome completo")
            if not valids["email"]:
                missing.append("seu email")
            if not valids["cargo"]:
                missing.append("seu cargo na empresa")
        
        return missing
    
    @staticmethod
    def natural_request(missing: str) -> str:
        """Gera pedido natural para informação faltante"""
        pedidos = {
            "CNPJ da empresa": [
                "📋 Antes de mostrar os dados, preciso do CNPJ da empresa. Pode informar?",
                "Para liberar o acesso aos dados, qual o CNPJ da empresa?",
                "Primeiro, me passa o CNPJ da empresa, por favor.",
                "Preciso validar o CNPJ da empresa. Qual é?"
            ],
            "nome da empresa": [
                "Agora, qual o nome da empresa?",
                "Ótimo! Agora me diz o nome da empresa.",
                "Perfeito! Qual é o nome da empresa?",
                "Legal! E o nome da empresa é...?"
            ],
            "seu nome completo": [
                "Excelente! Agora preciso do seu nome completo.",
                "Ótimo! Como você se chama? (nome completo)",
                "Perfeito! Qual o seu nome completo?",
                "Show! Me diz seu nome completo, por favor."
            ],
            "seu email": [
                "Qual seu email corporativo?",
                "Me passa seu email de trabalho, por favor.",
                "Preciso do seu email para enviar os relatórios. Qual é?",
                "E seu email profissional?"
            ],
            "seu cargo na empresa": [
                "Para finalizar, qual o seu cargo na empresa?",
                "Último dado: qual sua função/cargo?",
                "E qual cargo você ocupa na empresa?",
                "Por fim, me diz seu cargo, por favor."
            ]
        }
        return random.choice(pedidos.get(missing, [f"Por favor, informe: {missing}"]))
    
    @staticmethod
    def get_validation_feedback(field: str, value: str) -> Optional[str]:
        """Retorna feedback de validação específico"""
        if field == "cnpj":
            if not DataCollector.validate_cnpj(value):
                return "❌ CNPJ inválido. Por favor, verifique os dígitos e tente novamente."
        elif field == "email":
            if not DataCollector.validate_email(value):
                return "❌ Email inválido. Use o formato: nome@empresa.com"
        elif field == "empresa":
            if len(value) < 3:
                return "❌ Nome da empresa muito curto. Digite o nome completo."
        elif field == "nome":
            if len(value.split()) < 2:
                return "⚠️ Por favor, informe seu nome completo (nome e sobrenome)."
        
        return None

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
        return """Você é o Alex, especialista em dados e relatórios empresariais!

PERSONALIDADE:
- Fale naturalmente, como uma pessoa
- Seja profissional mas amigável
- Use linguagem clara e direta

PROCESSO DE COLETA DE DADOS:
1. SEMPRE colete primeiro os dados da EMPRESA:
   - CNPJ (validar formato XX.XXX.XXX/XXXX-XX)
   - Nome da empresa
2. SOMENTE depois de ter CNPJ e nome da empresa válidos, colete dados do USUÁRIO:
   - Nome completo
   - Email corporativo
   - Cargo

IMPORTANTE:
- NUNCA mostre dados sem ter CNPJ e empresa validados
- Valide CNPJ antes de aceitar
- Se CNPJ inválido, peça novamente explicando o erro
- Seja firme mas educado ao solicitar os dados
- Use emojis apropriados (📋, ✅, ❌, 📊)

Após coletar todos os dados, mostre relatórios de forma empolgante e profissional!"""
    
    def _get_tools(self) -> List[BaseTool]:
        return [get_sales_data, get_dashboard_metrics, get_customer_analytics, get_performance_metrics]
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return intent == "data_query"
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Obtém dados do cliente
        cliente = session.conversation_context.get("cliente", {})
        
        # Extrai novos dados do texto
        extracted = self.data_collector.extract_info(message.body or "", session.conversation_context)
        
        # Atualiza dados do cliente se houver novos
        if extracted:
            if "cliente" not in session.conversation_context:
                session.conversation_context["cliente"] = {}
            
            # Valida dados extraídos antes de salvar
            for field, value in extracted.items():
                feedback = self.data_collector.get_validation_feedback(field, value)
                if feedback:
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text=feedback,
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id,
                        metadata={"validation_error": field}
                    )
                else:
                    session.conversation_context["cliente"][field] = value
            
            cliente = session.conversation_context["cliente"]
        
        # Verifica o que está faltando ou inválido
        missing = self.data_collector.get_missing_or_invalid(cliente)
        
        if missing:
            # Gera pedido natural para o próximo campo
            pedido = self.data_collector.natural_request(missing[0])
            
            # Se já tem alguns dados, menciona o progresso
            if cliente:
                collected = []
                if cliente.get("cnpj"):
                    collected.append(f"CNPJ: {cliente['cnpj']} ✅")
                if cliente.get("empresa"):
                    collected.append(f"Empresa: {cliente['empresa']} ✅")
                if cliente.get("nome"):
                    collected.append(f"Nome: {cliente['nome']} ✅")
                
                if collected:
                    pedido = f"Ótimo! Já tenho:\n" + "\n".join(collected) + f"\n\n{pedido}"
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=pedido,
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id,
                metadata={"missing_fields": missing, "collected": cliente}
            )
        
        # Se chegou aqui, tem todos os dados válidos!
        # Identifica qual tipo de dados o usuário quer
        user_input = (message.body or "").lower()
        
        # Adiciona contexto sobre tipo de consulta
        query_type = "general"
        if any(word in user_input for word in ["vendas", "receita", "faturamento"]):
            query_type = "sales"
        elif any(word in user_input for word in ["dashboard", "resumo", "kpi", "geral"]):
            query_type = "dashboard"
        elif any(word in user_input for word in ["clientes", "customers", "usuários"]):
            query_type = "customers"
        elif any(word in user_input for word in ["performance", "sistema", "servidor"]):
            query_type = "performance"
        
        additional_context = {
            "query_type": query_type,
            "user_message": message.body,
            "cliente_validado": cliente,
            "empresa": cliente.get("empresa"),
            "user_name": cliente.get("nome"),
            "cargo": cliente.get("cargo", ""),
            "available_data_sources": ["sales", "dashboard", "customers", "performance"]
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
            # Para consultas gerais, inclui resumo
            additional_context["summary_data"] = {
                "sales": get_sales_data.invoke({}),
                "dashboard": get_dashboard_metrics.invoke({})
            }
        
        # Atualiza contexto da sessão
        session.update_context("query_type", query_type)
        session.update_context("last_data_request", datetime.now().isoformat())
        session.update_context("data_access_granted", True)
        
        # Adiciona header personalizado ao prompt
        nome_usuario = cliente.get("nome", "").split()[0]
        custom_prompt = self._get_system_prompt() + f"\n\nDados validados para {cliente.get('empresa')}. Usuário: {nome_usuario} ({cliente.get('cargo', 'Colaborador')})"
        
        # Processa com contexto específico
        response = await super().process_message(message, session)
        
        # Adiciona saudação personalizada se for primeira consulta após validação
        if session.conversation_context.get("first_data_access", True):
            prefix = f"🎉 Parabéns {nome_usuario}! Acesso liberado para {cliente['empresa']}!\n\n"
            response.response_text = prefix + response.response_text
            session.conversation_context["first_data_access"] = False
        
        # Verifica redirecionamento
        if any(word in user_input for word in ["sair", "voltar", "menu", "principal"]):
            response.next_agent = "reception_agent"
        elif any(word in user_input for word in ["outro", "nova", "diferente", "mais"]):
            response.next_agent = self.agent_id
        
        # Adiciona metadados
        response.metadata.update({
            "query_type": query_type,
            "data_validated": True,
            "client_data": cliente,
            "timestamp": datetime.now().isoformat()
        })
        
        return response
    
    def get_priority(self) -> int:
        return 7