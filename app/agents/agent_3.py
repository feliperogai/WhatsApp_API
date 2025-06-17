agent_3_py = ""
from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
import random
from datetime import datetime, timedelta

class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="data_agent",
            name="Agente de Dados e Analytics",
            description="Especialista em consultas de dados, relatórios e analytics"
        )
        
        # Simulação de dados (conecte com seu banco/API real)
        self.mock_data = {
            "vendas_mes": 125000,
            "vendas_anterior": 98000,
            "clientes_ativos": 1247,
            "conversion_rate": 3.2,
            "tickets_abertos": 23
        }
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        return session.current_agent == self.agent_id
    
    def generate_sales_report(self) -> str:
        """Gera relatório de vendas (conecte com seu sistema real)"""
        data = self.mock_data
        crescimento = ((data["vendas_mes"] - data["vendas_anterior"]) / data["vendas_anterior"]) * 100
        
        return f'''📊 **RELATÓRIO DE VENDAS - {datetime.now().strftime("%B/%Y")}**

💰 Receita Atual: R$ {data["vendas_mes"]:,.2f}
📈 Mês Anterior: R$ {data["vendas_anterior"]:,.2f}
📊 Crescimento: {crescimento:.1f}%

👥 Clientes Ativos: {data["clientes_ativos"]:,}
🎯 Taxa Conversão: {data["conversion_rate"]}%
🎫 Tickets Abertos: {data["tickets_abertos"]}

✨ Status: {"🟢 Acima da meta!" if crescimento > 10 else "🟡 Dentro do esperado" if crescimento > 0 else "🔴 Abaixo da meta"}'''

    def generate_dashboard_summary(self) -> str:
        """Gera resumo do dashboard"""
        return f'''🎛️ **DASHBOARD EXECUTIVO**

**KPIs Principais:**
• Revenue: R$ {self.mock_data["vendas_mes"]:,.2f}
• Clientes: {self.mock_data["clientes_ativos"]:,}
• Conversão: {self.mock_data["conversion_rate"]}%

**Status dos Sistemas:**
• ERP: 🟢 Online
• CRM: 🟢 Online  
• Analytics: 🟢 Online
• E-commerce: 🟡 Manutenção

**Alertas:**
• {self.mock_data["tickets_abertos"]} tickets pendentes
• Backup realizado às 03:00h
• Performance 97.2% uptime'''

    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        user_input = message.body.lower() if message.body else ""
        
        # Processa diferentes tipos de consulta
        if any(word in user_input for word in ["vendas", "receita", "faturamento"]):
            response_text = self.generate_sales_report()
            confidence = 0.9
            
        elif any(word in user_input for word in ["dashboard", "resumo", "overview", "kpi"]):
            response_text = self.generate_dashboard_summary()
            confidence = 0.9
            
        elif any(word in user_input for word in ["clientes", "customers", "usuários"]):
            response_text = f'''👥 **RELATÓRIO DE CLIENTES**

🟢 Ativos: {self.mock_data["clientes_ativos"]:,}
🆕 Novos (30d): {random.randint(50, 150)}
🔄 Retorno (30d): {random.randint(200, 400)}
💤 Inativos: {random.randint(100, 300)}

📊 Segmentação:
• Premium: 23%
• Standard: 45% 
• Basic: 32%'''
            confidence = 0.9
            
        elif user_input.isdigit() and user_input in ["1", "2", "3", "4"]:
            # Menu de opções
            options = {
                "1": self.generate_sales_report(),
                "2": self.generate_dashboard_summary(),
                "3": "📊 Relatório customizado será gerado...",
                "4": "📈 Análise preditiva em desenvolvimento..."
            }
            response_text = options.get(user_input, "Opção inválida.")
            confidence = 0.8
            
        else:
            response_text = '''📊 **CONSULTAS DISPONÍVEIS:**

1️⃣ Relatório de Vendas
2️⃣ Dashboard Executivo
3️⃣ Análise de Clientes
4️⃣ Métricas de Performance

Digite o número da consulta ou descreva o que precisa.

💡 *Exemplos: "vendas do mês", "dashboard", "quantos clientes"*'''
            confidence = 0.7
        
        # Verifica se usuário quer sair
        if any(word in user_input for word in ["sair", "voltar", "menu", "principal"]):
            response_text += "\n\n🔄 Te redirecionando para o menu principal..."
            next_agent = "reception_agent"
        else:
            next_agent = self.agent_id  # Continua neste agente
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=response_text,
            confidence=confidence,
            should_continue=True,
            next_agent=next_agent
        )
    
    def get_priority(self) -> int:
        return 7
