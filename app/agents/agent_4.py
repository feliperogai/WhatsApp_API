agent_4_py = ""
from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
import random
from datetime import datetime

class SupportAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="support_agent",
            name="Agente de Suporte Técnico",
            description="Especialista em suporte técnico e resolução de problemas"
        )
        
        self.common_issues = {
            "login": {
                "keywords": ["login", "senha", "acesso", "entrar", "autenticação"],
                "solution": '''🔐 **PROBLEMAS DE LOGIN**

**Soluções rápidas:**
1️⃣ Limpe cache do navegador
2️⃣ Tente no modo anônimo  
3️⃣ Verifique se Caps Lock está desligado
4️⃣ Use "Esqueci minha senha"

**Se persistir:**
• Verifique sua conexão
• Tente outro navegador
• Entre em contato: suporte@empresa.com'''
            },
            "performance": {
                "keywords": ["lento", "travando", "performance", "demorado", "carregando"],
                "solution": '''⚡ **PROBLEMAS DE PERFORMANCE**

**Verificações básicas:**
1️⃣ Teste sua velocidade de internet
2️⃣ Feche outras abas/programas
3️⃣ Reinicie o navegador
4️⃣ Limpe cache e cookies

**Status dos servidores:**
🟢 API Principal: Normal
🟢 Banco de Dados: Normal
🟡 CDN: Otimização em andamento'''
            },
            "error": {
                "keywords": ["erro", "bug", "falha", "não funciona", "problema"],
                "solution": '''🐛 **RELATÓRIO DE ERRO**

**Para nos ajudar:**
1️⃣ Qual erro apareceu?
2️⃣ O que você estava fazendo?
3️⃣ Que navegador usa?
4️⃣ Pode enviar print?

**Ticket criado:** #{random.randint(1000, 9999)}
**Prioridade:** Alta
**SLA:** 4 horas úteis'''
            }
        }
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        return session.current_agent == self.agent_id
    
    def identify_issue_type(self, message: str) -> str:
        """Identifica o tipo de problema"""
        message_lower = message.lower()
        
        for issue_type, config in self.common_issues.items():
            if any(keyword in message_lower for keyword in config["keywords"]):
                return issue_type
        
        return "general"
    
    def create_ticket(self) -> dict:
        """Cria um ticket de suporte"""
        ticket_id = f"TK{random.randint(10000, 99999)}"
        return {
            "id": ticket_id,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "Aberto",
            "priority": "Normal"
        }
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        user_input = message.body.lower() if message.body else ""
        
        # Identifica o tipo de problema
        issue_type = self.identify_issue_type(user_input)
        
        if issue_type in self.common_issues:
            response_text = self.common_issues[issue_type]["solution"]
            confidence = 0.9
            
        elif any(word in user_input for word in ["ticket", "protocolo", "acompanhar"]):
            ticket = self.create_ticket()
            response_text = f'''🎫 **TICKET DE SUPORTE**

**Protocolo:** {ticket["id"]}
**Criado em:** {ticket["created_at"]}
**Status:** {ticket["status"]}
**Prioridade:** {ticket["priority"]}

📧 Você receberá atualizações por email
⏰ Resposta prevista: 4h úteis
📱 Acompanhe pelo app ou site'''
            confidence = 0.9
            
        elif any(word in user_input for word in ["urgente", "crítico", "parou", "down"]):
            response_text = '''🚨 **SUPORTE CRÍTICO ACIONADO**

**Escalado para:** Plantão 24h
**Protocolo:** URG-{:05d}
**Prioridade:** CRÍTICA

📞 **Contato Direto:**
• WhatsApp: (11) 99999-9999
• Email: urgente@empresa.com
• Teams: Plantão TI

⏰ **SLA Crítico:** 30 minutos'''.format(random.randint(1000, 9999))
            confidence = 1.0
            
        elif user_input.isdigit() and user_input in ["1", "2", "3"]:
            options = {
                "1": self.common_issues["login"]["solution"],
                "2": self.common_issues["performance"]["solution"], 
                "3": self.common_issues["error"]["solution"]
            }
            response_text = options.get(user_input, "Opção inválida.")
            confidence = 0.9
            
        else:
            response_text = '''🔧 **SUPORTE TÉCNICO JARVIS**

**Problemas Comuns:**
1️⃣ Problemas de Login/Acesso
2️⃣ Lentidão/Performance
3️⃣ Erros e Bugs

**Ou descreva seu problema:**
• Seja específico sobre o erro
• Informe o que estava fazendo
• Mencione se é urgente

💬 *Ex: "Não consigo fazer login" ou "Sistema está lento"*'''
            confidence = 0.7
        
        # Verifica se usuário quer sair  
        if any(word in user_input for word in ["resolvido", "obrigado", "sair", "voltar"]):
            response_text += "\n\n✅ Ótimo! Problema resolvido!\n🔄 Te redirecionando para o menu principal..."
            next_agent = "reception_agent"
        else:
            next_agent = self.agent_id
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=response_text,
            confidence=confidence,
            should_continue=True,
            next_agent=next_agent
        )
    
    def get_priority(self) -> int:
        return 6
