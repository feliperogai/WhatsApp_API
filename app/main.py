from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import re
import asyncio

load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Arquivo para persistir sessões
SESSIONS_FILE = "sessions.json"

class SessionManager:
    """Gerenciador de sessões com persistência"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.load_sessions()
    
    def load_sessions(self):
        """Carrega sessões do arquivo"""
        try:
            if os.path.exists(SESSIONS_FILE):
                with open(SESSIONS_FILE, 'r') as f:
                    data = json.load(f)
                    # Converte strings de data para datetime
                    for phone, session in data.items():
                        if 'created_at' in session:
                            session['created_at'] = datetime.fromisoformat(session['created_at'])
                        if 'updated_at' in session:
                            session['updated_at'] = datetime.fromisoformat(session['updated_at'])
                    self.sessions = data
                logger.info(f"Carregadas {len(self.sessions)} sessões")
        except Exception as e:
            logger.error(f"Erro ao carregar sessões: {e}")
    
    def save_sessions(self):
        """Salva sessões no arquivo"""
        try:
            data = {}
            for phone, session in self.sessions.items():
                data[phone] = session.copy()
                # Converte datetime para string
                if 'created_at' in data[phone] and isinstance(data[phone]['created_at'], datetime):
                    data[phone]['created_at'] = data[phone]['created_at'].isoformat()
                if 'updated_at' in data[phone] and isinstance(data[phone]['updated_at'], datetime):
                    data[phone]['updated_at'] = data[phone]['updated_at'].isoformat()
            
            with open(SESSIONS_FILE, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar sessões: {e}")
    
    def get_or_create_session(self, phone: str) -> Dict[str, Any]:
        """Obtém ou cria sessão"""
        # Remove sessões expiradas
        self.cleanup_expired_sessions()
        
        if phone not in self.sessions:
            self.sessions[phone] = {
                "phone": phone,
                "state": "initial",
                "data": {},
                "history": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            self.save_sessions()
        
        return self.sessions[phone]
    
    def update_session(self, phone: str, updates: Dict[str, Any]):
        """Atualiza sessão"""
        if phone in self.sessions:
            self.sessions[phone].update(updates)
            self.sessions[phone]["updated_at"] = datetime.now()
            self.save_sessions()
    
    def cleanup_expired_sessions(self):
        """Remove sessões inativas há mais de 24h"""
        now = datetime.now()
        expired = []
        
        for phone, session in self.sessions.items():
            updated = session.get("updated_at", now)
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)
            
            if now - updated > timedelta(hours=24):
                expired.append(phone)
        
        for phone in expired:
            del self.sessions[phone]
            logger.info(f"Sessão expirada removida: {phone}")
        
        if expired:
            self.save_sessions()

# Instância global do gerenciador
session_manager = SessionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando Jarvis WhatsApp Extended...")
    # Agenda limpeza periódica
    asyncio.create_task(periodic_cleanup())
    yield
    logger.info("🛑 Parando Jarvis WhatsApp...")
    # Salva sessões finais
    session_manager.save_sessions()

async def periodic_cleanup():
    """Limpeza periódica de sessões"""
    while True:
        await asyncio.sleep(3600)  # A cada hora
        session_manager.cleanup_expired_sessions()

app = FastAPI(
    title="Jarvis WhatsApp Extended",
    description="Sistema de coleta de dados com mais recursos",
    version="2.0",
    lifespan=lifespan
)

class ExtendedConversationFlow:
    """Fluxo de conversa estendido com validações"""
    
    @staticmethod
    def validate_name(name: str) -> tuple[bool, str]:
        """Valida nome do usuário"""
        name = name.strip()
        
        # Verifica se é muito curto
        if len(name) < 2:
            return False, "Por favor, digite seu nome completo."
        
        # Verifica se tem números
        if any(char.isdigit() for char in name):
            return False, "O nome não pode conter números. Por favor, digite seu nome correto."
        
        # Verifica se é só uma palavra (aviso, não erro)
        words = name.split()
        if len(words) == 1:
            return True, f"Ok {name}! Você pode me dizer seu nome completo? (ou digite 'pular' para continuar)"
        
        return True, ""
    
    @staticmethod
    def validate_company(company: str) -> tuple[bool, str]:
        """Valida nome da empresa"""
        company = company.strip()
        
        if len(company) < 2:
            return False, "Por favor, digite o nome da empresa."
        
        # Permite números em nomes de empresa
        return True, ""
    
    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """Extrai email do texto"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None
    
    @staticmethod
    def extract_phone_number(text: str) -> Optional[str]:
        """Extrai telefone do texto"""
        # Remove tudo exceto números
        numbers = re.sub(r'\D', '', text)
        
        # Verifica se tem tamanho de telefone BR
        if len(numbers) == 11:  # Com DDD
            return f"+55{numbers}"
        elif len(numbers) == 13 and numbers.startswith("55"):  # Com código país
            return f"+{numbers}"
        
        return None
    
    @staticmethod
    def process_message(phone: str, message: str) -> str:
        """Processa mensagem com validações e estados extras"""
        session = session_manager.get_or_create_session(phone)
        current_state = session["state"]
        user_data = session["data"]
        msg_lower = message.lower().strip()
        
        # Adiciona mensagem ao histórico
        session["history"].append({
            "timestamp": datetime.now().isoformat(),
            "from": "user",
            "message": message
        })
        
        logger.info(f"📱 {phone} | Estado: {current_state} | Msg: {message}")
        
        # Comandos globais (funcionam em qualquer estado)
        if msg_lower in ["resetar", "recomeçar", "reset", "/start"]:
            session["state"] = "initial"
            session["data"] = {}
            session_manager.update_session(phone, session)
            return "🔄 Ok! Vamos recomeçar do início!\n\nOi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?"
        
        if msg_lower in ["ajuda", "help", "/help"]:
            return """ℹ️ **Comandos disponíveis:**
• Digite normalmente para conversar
• 'resetar' - Recomeça do início
• 'status' - Ver seus dados
• 'ajuda' - Esta mensagem

📱 Estou aqui para coletar seus dados e ajudar com:
• Relatórios e dados
• Suporte técnico
• Agendamentos"""
        
        if msg_lower in ["status", "meus dados", "/status"]:
            if user_data:
                info = "📋 **Seus dados:**\n"
                info += f"• Nome: {user_data.get('nome', 'Não informado')}\n"
                info += f"• Empresa: {user_data.get('empresa', 'Não informada')}\n"
                info += f"• Email: {user_data.get('email', 'Não informado')}\n"
                info += f"• Telefone: {user_data.get('telefone', 'Não informado')}"
                return info
            else:
                return "📋 Ainda não tenho seus dados. Vamos começar? Digite 'oi'!"
        
        # Estados da conversa
        response = ""
        
        # INICIAL
        if current_state == "initial":
            session["state"] = "waiting_name"
            response = "Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual da Jarvis!\n\nQual é o seu nome?"
        
        # ESPERANDO NOME
        elif current_state == "waiting_name":
            is_valid, validation_msg = ExtendedConversationFlow.validate_name(message)
            
            if not is_valid:
                response = f"❌ {validation_msg}"
            else:
                user_data["nome"] = message.title()
                
                if validation_msg and msg_lower != "pular":  # Pedindo nome completo
                    session["state"] = "waiting_full_name"
                    response = validation_msg
                else:
                    session["state"] = "waiting_company"
                    primeiro_nome = user_data["nome"].split()[0]
                    response = f"Prazer em te conhecer, {primeiro_nome}! 😊\n\nDe qual empresa você é?"
        
        # ESPERANDO NOME COMPLETO (opcional)
        elif current_state == "waiting_full_name":
            if msg_lower != "pular":
                user_data["nome"] = message.title()
            
            session["state"] = "waiting_company"
            primeiro_nome = user_data["nome"].split()[0]
            response = f"Perfeito, {primeiro_nome}! 👍\n\nAgora me diz: de qual empresa você é?"
        
        # ESPERANDO EMPRESA
        elif current_state == "waiting_company":
            is_valid, validation_msg = ExtendedConversationFlow.validate_company(message)
            
            if not is_valid:
                response = f"❌ {validation_msg}"
            else:
                user_data["empresa"] = message.title()
                session["state"] = "waiting_contact_preference"
                primeiro_nome = user_data["nome"].split()[0]
                response = f"Excelente, {primeiro_nome}! A {message.title()} é nossa parceira! 🎯\n\n"
                response += "Para finalizar seu cadastro, como prefere que eu entre em contato?\n"
                response += "📧 Email ou 📱 WhatsApp? (ou digite 'pular' para ir direto aos serviços)"
        
        # ESPERANDO PREFERÊNCIA DE CONTATO
        elif current_state == "waiting_contact_preference":
            primeiro_nome = user_data["nome"].split()[0]
            
            if msg_lower in ["pular", "depois", "não"]:
                session["state"] = "ready"
                response = f"Sem problemas, {primeiro_nome}! 😊\n\n"
                response += "Como posso te ajudar hoje?\n"
                response += "• 📊 Ver relatórios e dados\n"
                response += "• 🔧 Suporte técnico\n"
                response += "• 📅 Agendar reunião"
            
            elif "email" in msg_lower or "@" in message:
                # Extrai email se já veio junto
                email = ExtendedConversationFlow.extract_email(message)
                if email:
                    user_data["email"] = email
                    user_data["contato_preferido"] = "email"
                    session["state"] = "ready"
                    response = f"✅ Email {email} salvo!\n\n"
                    response += "Como posso te ajudar hoje?"
                else:
                    session["state"] = "waiting_email"
                    response = "📧 Por favor, digite seu email:"
            
            elif "whatsapp" in msg_lower or "zap" in msg_lower:
                user_data["telefone"] = phone  # Usa o próprio número
                user_data["contato_preferido"] = "whatsapp"
                session["state"] = "ready"
                response = f"✅ Vou usar este WhatsApp para contato!\n\n"
                response += "Como posso te ajudar hoje?"
            
            else:
                response = "Por favor, escolha: Email ou WhatsApp? (ou 'pular')"
        
        # ESPERANDO EMAIL
        elif current_state == "waiting_email":
            email = ExtendedConversationFlow.extract_email(message)
            
            if email:
                user_data["email"] = email
                session["state"] = "ready"
                primeiro_nome = user_data["nome"].split()[0]
                response = f"✅ Perfeito, {primeiro_nome}! Email salvo.\n\n"
                response += "Como posso te ajudar hoje?\n"
                response += "• 📊 Ver relatórios\n"
                response += "• 🔧 Suporte técnico\n"
                response += "• 📅 Agendar reunião"
            else:
                response = "❌ Email inválido. Por favor, digite um email válido (ou 'pular'):"
        
        # PRONTO - Conversa normal
        elif current_state == "ready":
            primeiro_nome = user_data["nome"].split()[0]
            empresa = user_data["empresa"]
            
            # Respostas baseadas em intenção
            if any(word in msg_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi", "métrica"]):
                response = f"📊 **RELATÓRIO - {empresa.upper()}**\n\n"
                response += f"Olá {primeiro_nome}, aqui estão seus dados:\n\n"
                response += "**Vendas (Novembro/2024)**\n"
                response += "• Faturamento: R$ 125.000\n"
                response += "• Crescimento: +15% 📈\n"
                response += "• Novos clientes: 47\n"
                response += "• Ticket médio: R$ 2.659\n\n"
                response += "**Performance**\n"
                response += "• Taxa conversão: 3.2%\n"
                response += "• Churn: 2.1% ✅\n"
                response += "• NPS: 72 😊\n\n"
                response += "Quer ver algum dado específico?"
            
            elif any(word in msg_lower for word in ["erro", "problema", "bug", "ajuda", "não funciona", "travou"]):
                response = f"🔧 **SUPORTE TÉCNICO**\n\n"
                response += f"{primeiro_nome}, vou te ajudar! Me conta:\n\n"
                response += "1️⃣ Qual sistema está com problema?\n"
                response += "2️⃣ Que erro aparece?\n"
                response += "3️⃣ Quando começou?\n\n"
                response += f"🎫 Vou criar um chamado prioritário para {empresa}."
                
                # Se tem email, menciona
                if user_data.get("email"):
                    response += f"\n\n📧 Enviarei atualizações para: {user_data['email']}"
            
            elif any(word in msg_lower for word in ["agendar", "marcar", "reunião", "horário", "meeting", "call"]):
                response = f"📅 **AGENDAMENTO**\n\n"
                response += f"{primeiro_nome}, vamos agendar sua reunião!\n\n"
                response += "**Horários disponíveis:**\n"
                response += "• Segunda 28/11 - 14h ou 16h\n"
                response += "• Terça 29/11 - 10h ou 15h\n"
                response += "• Quarta 30/11 - 11h ou 14h\n\n"
                response += "Qual horário fica melhor? (ex: 'segunda 14h')"
                session["state"] = "scheduling"
            
            elif any(word in msg_lower for word in ["tchau", "obrigado", "até", "valeu", "fim", "sair"]):
                response = f"Foi um prazer ajudar, {primeiro_nome}! 😊\n\n"
                response += f"Sempre que precisar de algo para a {empresa}, é só me chamar!\n\n"
                
                # Menciona contato preferido
                if user_data.get("contato_preferido") == "email":
                    response += f"📧 Qualquer novidade, envio para {user_data['email']}\n"
                
                response += "Até mais! 👋"
                
                # Opcional: limpar sessão após despedida
                # session["state"] = "initial"
                # session["data"] = {}
            
            else:
                # Não entendeu - oferece opções
                response = f"{primeiro_nome}, não entendi bem. 🤔\n\n"
                response += "Posso te ajudar com:\n\n"
                response += "📊 **Relatórios** - Digite 'relatório' ou 'dados'\n"
                response += "🔧 **Suporte** - Digite 'problema' ou 'erro'\n"
                response += "📅 **Agendamento** - Digite 'agendar' ou 'reunião'\n\n"
                response += "O que você precisa?"
        
        # AGENDAMENTO
        elif current_state == "scheduling":
            primeiro_nome = user_data["nome"].split()[0]
            
            if any(day in msg_lower for day in ["segunda", "terça", "quarta", "seg", "ter", "qua"]):
                # Extrai horário
                horario_match = re.search(r'(\d{1,2})[h:]?', message)
                horario = horario_match.group(1) + "h" if horario_match else "14h"
                
                user_data["agendamento"] = f"{message} às {horario}"
                session["state"] = "ready"
                
                response = f"✅ **AGENDAMENTO CONFIRMADO**\n\n"
                response += f"{primeiro_nome}, agendei sua reunião:\n"
                response += f"📅 {user_data['agendamento']}\n"
                response += f"🏢 Empresa: {user_data['empresa']}\n\n"
                
                if user_data.get("email"):
                    response += f"📧 Enviarei o convite para: {user_data['email']}\n"
                
                response += "\nAlgo mais que posso ajudar?"
            
            else:
                response = "Por favor, escolha um dos horários disponíveis (ex: 'segunda 14h') ou digite 'cancelar':"
        
        # Atualiza sessão
        session_manager.update_session(phone, session)
        
        # Adiciona resposta ao histórico
        session["history"].append({
            "timestamp": datetime.now().isoformat(),
            "from": "assistant",
            "message": response
        })
        
        return response