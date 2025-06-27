from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool, tool
import random
from datetime import datetime
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

class StrictDataCollector:
    """Coletor de dados com ordem estrita: CNPJ → Empresa → Nome → Email → Cargo"""
    
    # Ordem obrigatória de coleta
    COLLECTION_ORDER = ["cnpj", "empresa", "nome", "email", "cargo"]
    
    @staticmethod
    def get_current_step(cliente: Dict[str, Any]) -> str:
        """Retorna qual campo deve ser coletado agora"""
        for field in StrictDataCollector.COLLECTION_ORDER:
            if not cliente.get(field) or not StrictDataCollector._is_field_valid(field, cliente.get(field, "")):
                return field
        return "complete"
    
    @staticmethod
    def _is_field_valid(field: str, value: str) -> bool:
        """Valida se um campo está correto"""
        if not value:
            return False
            
        if field == "cnpj":
            return StrictDataCollector.validate_cnpj(value)
        elif field == "empresa":
            return len(value.strip()) >= 3
        elif field == "nome":
            return len(value.strip().split()) >= 2  # Nome e sobrenome
        elif field == "email":
            return StrictDataCollector.validate_email(value)
        elif field == "cargo":
            return len(value.strip()) >= 3
        
        return True
    
    @staticmethod
    def extract_field_from_message(message: str, field: str) -> Optional[str]:
        """Extrai um campo específico da mensagem"""
        message_clean = message.strip()
        
        if field == "cnpj":
            # Procura por CNPJ no formato XX.XXX.XXX/XXXX-XX ou apenas números
            cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}|\d{14}'
            match = re.search(cnpj_pattern, message_clean)
            if match:
                return StrictDataCollector.format_cnpj(match.group())
        
        elif field == "empresa":
            # Se não tem padrões específicos, considera a mensagem toda como nome da empresa
            if len(message_clean) >= 3 and len(message_clean) < 100:
                return message_clean.title()
        
        elif field == "nome":
            # Verifica se parece ser um nome completo
            words = message_clean.split()
            if len(words) >= 2 and all(word.replace('-', '').isalpha() for word in words):
                return message_clean.title()
        
        elif field == "email":
            # Procura por email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            match = re.search(email_pattern, message_clean)
            if match:
                return match.group().lower()
        
        elif field == "cargo":
            # Aceita como cargo se tem pelo menos 3 caracteres
            if len(message_clean) >= 3 and len(message_clean) < 50:
                return message_clean.title()
        
        return None
    
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
    def get_progress_message(cliente: Dict[str, Any]) -> str:
        """Retorna mensagem de progresso mostrando o que já foi coletado"""
        parts = ["Ótimo! Já tenho:"]
        
        for field in StrictDataCollector.COLLECTION_ORDER:
            if field in cliente and StrictDataCollector._is_field_valid(field, cliente[field]):
                if field == "cnpj":
                    parts.append(f"CNPJ: {cliente[field]} ✅")
                elif field == "empresa":
                    parts.append(f"Empresa: {cliente[field]} ✅")
                elif field == "nome":
                    parts.append(f"Nome: {cliente[field]} ✅")
                elif field == "email":
                    parts.append(f"Email: {cliente[field]} ✅")
                elif field == "cargo":
                    parts.append(f"Cargo: {cliente[field]} ✅")
        
        return "\n".join(parts) if len(parts) > 1 else ""
    
    @staticmethod
    def get_request_message(field: str, has_progress: bool = False) -> str:
        """Retorna mensagem de solicitação para o campo"""
        messages = {
            "cnpj": [
                "📋 Antes de mostrar os dados, preciso do CNPJ da empresa. Pode informar?",
                "Para liberar o acesso aos dados, qual o CNPJ da empresa?",
                "Primeiro, me passa o CNPJ da empresa, por favor.",
                "Preciso validar o CNPJ da empresa. Qual é?"
            ],
            "empresa": [
                "Agora, qual o nome da empresa?",
                "Ótimo! Agora me diz o nome da empresa.",
                "Perfeito! Qual é o nome da empresa?",
                "Legal! E o nome da empresa é...?"
            ],
            "nome": [
                "Excelente! Agora preciso do seu nome completo.",
                "Ótimo! Como você se chama? (nome completo)",
                "Perfeito! Qual o seu nome completo?",
                "Show! Me diz seu nome completo, por favor."
            ],
            "email": [
                "Qual seu email corporativo?",
                "Me passa seu email de trabalho, por favor.",
                "Preciso do seu email para enviar os relatórios. Qual é?",
                "E seu email profissional?"
            ],
            "cargo": [
                "Para finalizar, qual o seu cargo na empresa?",
                "Último dado: qual sua função/cargo?",
                "E qual cargo você ocupa na empresa?",
                "Por fim, me diz seu cargo, por favor."
            ]
        }
        
        return random.choice(messages.get(field, [f"Por favor, informe: {field}"]))

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
        self.data_collector = StrictDataCollector()
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, especialista em dados e relatórios empresariais!

REGRA ABSOLUTA: SEMPRE siga esta ordem EXATA de coleta:
1. CNPJ (validar formato XX.XXX.XXX/XXXX-XX)
2. Nome da empresa
3. Nome completo do usuário
4. Email corporativo
5. Cargo

IMPORTANTE:
- NUNCA pule etapas ou aceite dados fora de ordem
- Se o usuário tentar dar outro dado, INSISTA no dado correto da sequência
- SEMPRE valide CNPJ antes de aceitar
- Se CNPJ inválido, peça novamente explicando o erro
- Mostre o progresso após cada dado coletado
- Use os emojis apropriados (📋, ✅, ❌, 📊, 🎉)

Seja firme mas educado ao manter a ordem. 
Só mostre dados após coletar TODOS os campos."""
    
    def _get_tools(self) -> List[BaseTool]:
        return [get_sales_data, get_dashboard_metrics, get_customer_analytics, get_performance_metrics]
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return intent == "data_query"
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        # Obtém dados do cliente
        if "cliente" not in session.conversation_context:
            session.conversation_context["cliente"] = {}
        
        cliente = session.conversation_context["cliente"]
        
        # Identifica qual campo devemos coletar agora
        current_step = self.data_collector.get_current_step(cliente)
        
        if current_step != "complete":
            # Ainda coletando dados
            
            # Tenta extrair o campo esperado da mensagem
            extracted_value = self.data_collector.extract_field_from_message(
                message.body or "", 
                current_step
            )
            
            if extracted_value:
                # Validação específica para CNPJ
                if current_step == "cnpj" and not self.data_collector.validate_cnpj(extracted_value):
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text="❌ CNPJ inválido. Por favor, verifique os dígitos e tente novamente.",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id,
                        metadata={"validation_error": "cnpj", "step": current_step}
                    )
                
                # Salva o campo
                cliente[current_step] = extracted_value
                session.conversation_context["cliente"] = cliente
                
                # Verifica próximo passo
                next_step = self.data_collector.get_current_step(cliente)
                
                if next_step != "complete":
                    # Monta resposta com progresso + próxima solicitação
                    progress = self.data_collector.get_progress_message(cliente)
                    request = self.data_collector.get_request_message(next_step)
                    
                    response_text = f"{progress}\n\n{request}" if progress else request
                    
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text=response_text,
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id,
                        metadata={"step": next_step, "collected": cliente}
                    )
            else:
                # Usuário tentou dar outro dado ou dado inválido
                
                # Se tentou pular etapas, insiste no campo correto
                request = self.data_collector.get_request_message(current_step)
                
                # Mensagens específicas para quando tenta burlar
                if current_step == "cnpj":
                    # Verifica se tentou dar nome ou email
                    if "@" in (message.body or ""):
                        response_text = f"Para liberar o acesso aos dados, qual o CNPJ da empresa?"
                    elif any(word in (message.body or "").lower() for word in ["meu nome", "me chamo", "sou"]):
                        response_text = f"Entendi seu nome, mas primeiro preciso do CNPJ da empresa para liberar o acesso. Qual é o CNPJ?"
                    else:
                        response_text = request
                else:
                    response_text = request
                
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text=response_text,
                    confidence=0.9,
                    should_continue=True,
                    next_agent=self.agent_id,
                    metadata={"step": current_step, "waiting_for": current_step}
                )
        
        # Se chegou aqui, todos os dados foram coletados!
        nome_usuario = cliente.get("nome", "").split()[0]
        empresa = cliente.get("empresa", "")
        
        # Mensagem de sucesso
        success_msg = f"🎉 Parabéns {nome_usuario}! Acesso liberado para {empresa}!"
        
        # Identifica qual tipo de dados o usuário quer
        user_input = (message.body or "").lower()
        
        # Gera relatório baseado no pedido
        if any(word in user_input for word in ["vendas", "receita", "faturamento"]):
            sales_data = get_sales_data.invoke({})
            
            report = f"""{success_msg}

📊 **RELATÓRIO DE VENDAS - {empresa.upper()}**

Olá {nome_usuario}, aqui está o relatório solicitado:

💰 **Vendas do Mês**
- Faturamento: R$ {sales_data['vendas_mes']:,.2f}
- Crescimento: +{sales_data['crescimento_mensal']}% 📈
- Clientes ativos: {sales_data['clientes_ativos']}
- Taxa de conversão: {sales_data['conversion_rate']}%

📈 **Comparativo Mensal**
- Mês anterior: R$ {sales_data['vendas_anterior']:,.2f}
- Variação: +R$ {sales_data['vendas_mes'] - sales_data['vendas_anterior']:,.2f}
- Meta atingida: {round((sales_data['vendas_mes'] / 150000) * 100, 1)}%

🎯 **Performance**
- Tickets abertos: {sales_data['tickets_abertos']}
- Tempo médio resolução: 2.4h
- Satisfação: 94.2% ✅

Como {cliente.get('cargo', 'colaborador')}, você tem acesso completo aos dados.
Precisa de algum detalhamento específico?"""
            
        elif any(word in user_input for word in ["cliente", "clientes", "usuários"]):
            customer_data = get_customer_analytics.invoke({})
            
            report = f"""{success_msg}

👥 **ANÁLISE DE CLIENTES - {empresa.upper()}**

Olá {nome_usuario}, aqui estão os dados de clientes:

📊 **Base de Clientes**
- Total: {customer_data['total_customers']}
- Novos (30 dias): +{customer_data['new_customers_30d']}
- Ativos: {customer_data['returning_customers']}
- Inativos: {customer_data['inactive_customers']}

🎯 **Segmentação**
- Premium: {customer_data['segments']['premium']}%
- Standard: {customer_data['segments']['standard']}%
- Basic: {customer_data['segments']['basic']}%

📈 **Engajamento**
- Sessão média: {customer_data['avg_session_duration']} min
- Taxa de rejeição: {customer_data['bounce_rate']}%

Alguma análise específica que gostaria de ver?"""
            
        else:
            # Dashboard geral
            dashboard = get_dashboard_metrics.invoke({})
            
            report = f"""{success_msg}

📊 **DASHBOARD EXECUTIVO - {empresa.upper()}**

Olá {nome_usuario}, aqui está o resumo:

💰 **Receita**
- Total: R$ {dashboard['revenue_total']:,.2f}
- Recorrente: R$ {dashboard['revenue_recurring']:,.2f}
- CAC: R$ {dashboard['customer_acquisition_cost']:,.2f}
- LTV: R$ {dashboard['lifetime_value']:,.2f}

📈 **Indicadores**
- Churn Rate: {dashboard['churn_rate']}%
- NPS Score: {dashboard['nps_score']} pontos
- Usuários ativos: {dashboard['active_users_monthly']}

🔧 **Sistema**
- Uptime: {dashboard['server_uptime']}%
- Performance: Excelente ✅

Gostaria de detalhar alguma métrica específica?"""
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=report,
            confidence=0.95,
            should_continue=True,
            next_agent=self.agent_id,
            metadata={
                "data_complete": True,
                "client_data": cliente,
                "report_type": "sales" if "vendas" in user_input else "general"
            }
        )
    
    def get_priority(self) -> int:
        return 7