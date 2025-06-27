import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re
import random

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class ProactiveDataCollector:
    """Coletor proativo de dados do cliente"""
    
    @staticmethod
    def extract_client_info(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai informações do cliente de forma inteligente do texto"""
        extracted = {}
        text_lower = text.lower()
        
        # Extrai nome
        if not context.get("cliente", {}).get("nome"):
            name_patterns = [
                r"(?:meu nome é|me chamo|sou o?a?|aqui é o?a?)\s+([A-Za-zÀ-ÿ\s]+)",
                r"(?:é o?a?)\s+([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.)",
                r"^([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.|\!)",
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    nome = match.group(1).strip().title()
                    palavras = nome.split()
                    if (len(palavras) <= 5 and 
                        not any(word in nome.lower() for word in ["oi", "olá", "bom", "boa"]) and
                        len(nome) > 2):
                        extracted["nome"] = nome
                        logger.info(f"Nome extraído: {nome}")
                        break
        
        # Extrai empresa
        if not context.get("cliente", {}).get("empresa"):
            empresa_patterns = [
                r"(?:empresa|trabalho na|sou da|represento a?)\s+([A-Za-zÀ-ÿ0-9\s&\-\.]+?)(?:\.|,|$)",
                r"(?:da|na)\s+([A-Z][A-Za-zÀ-ÿ0-9\s&\-\.]+(?:LTDA|ME|SA|S\.A\.|Ltd|Inc)?)",
            ]
            
            for pattern in empresa_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    empresa = match.group(1).strip()
                    if len(empresa) > 2 and len(empresa) < 50:
                        extracted["empresa"] = empresa
                        logger.info(f"Empresa extraída: {empresa}")
                        break
        
        # Extrai email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match and not context.get("cliente", {}).get("email"):
            email = email_match.group().lower()
            extracted["email"] = email
            logger.info(f"Email extraído: {email}")
        
        return extracted
    
    @staticmethod
    def get_missing_essential_info(context: Dict[str, Any]) -> List[str]:
        """Retorna informações essenciais que faltam"""
        cliente = context.get("cliente", {})
        missing = []
        
        if not cliente.get("nome"):
            missing.append("nome")
        if not cliente.get("empresa"):
            missing.append("empresa") 
        if not cliente.get("email"):
            missing.append("email")
            
        return missing
    
    @staticmethod
    def should_collect_data_now(context: Dict[str, Any], user_message: str) -> bool:
        """Decide se deve coletar dados agora"""
        # Se é primeira interação, sempre coleta
        interaction_count = context.get("interaction_count", 0)
        if interaction_count <= 1:
            return True
        
        # Se usuário está reportando problema urgente, não interrompe
        if any(word in user_message.lower() for word in ["erro", "urgente", "parado", "problema", "bug"]):
            return False
        
        # Se faltam dados essenciais e já interagiu um pouco
        missing = ProactiveDataCollector.get_missing_essential_info(context)
        if missing and interaction_count <= 3:
            return True
            
        return False


class LLMProactiveReceptionAgent(LLMBaseAgent):
    """Agente de recepção proativo que coleta dados essenciais no início"""
    
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",  # Mantém ID para compatibilidade
            name="Alex - Assistente Proativo",
            description="Assistente que coleta dados essenciais proativamente",
            llm_service=llm_service
        )
        self.data_collector = ProactiveDataCollector()
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, assistente super amigável da empresa.

PERSONALIDADE:
- Fale SEMPRE como uma pessoa real e natural
- Use linguagem cotidiana de WhatsApp
- Seja caloroso e profissional

COLETA DE DADOS PROATIVA:
- Na PRIMEIRA interação, SEMPRE pergunte o CNPJ da empresa de forma natural
- Exemplo: 'Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Para começarmos, qual o CNPJ da sua empresa?'
- Após saber o CNPJ, pergunte o nome da empresa de forma conversacional
- Depois colete o nome do usuário e o email quando for relevante

IMPORTANTE:
- Colete dados de forma natural e amigável
- Use o nome da empresa e da pessoa após descobrir
- Não faça parecer um formulário
- Seja útil enquanto coleta informações"""
    
    def _get_tools(self) -> List:
        return []
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return True  # Reception agent aceita qualquer intent
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Reception agent sempre pode processar na primeira interação"""
        if session and session.current_agent == self.agent_id:
            return True
        
        if not session or not session.current_agent:
            return True
            
        if not session.message_history:
            return True
        
        message_text = (message.body or "").lower()
        reception_keywords = [
            "oi", "olá", "ola", "hello", "bom dia", "boa tarde", "boa noite",
            "inicio", "começar", "voltar", "menu", "serviço", "serviços"
        ]
        
        return any(keyword in message_text for keyword in reception_keywords)
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem com coleta proativa de dados"""
        try:
            logger.info(f"[ProactiveReception] Processando: {message.body}")
            
            # Detecta intenção de dados
            user_text = (message.body or "").lower()
            intent = None
            if hasattr(self.llm_service, 'classify_intent'):
                intent_result = await self.llm_service.classify_intent(message.body or "", session.session_id)
                intent = intent_result.get("intent", "")
            is_data_intent = (
                (intent == "data_query") or
                any(word in user_text for word in ["dados", "relatório", "relatorios", "kpi", "dashboard", "vendas"])
            )
            # Se intenção for dados, pedir CNPJ e nome da empresa primeiro
            if is_data_intent:
                cliente = session.conversation_context.get("cliente", {})
                # Checa se já tem CNPJ e empresa
                cnpj_ok = bool(cliente.get("cnpj"))
                empresa_ok = bool(cliente.get("empresa"))
                if not cnpj_ok:
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text="Para acessar os dados, preciso primeiro do CNPJ da empresa. Pode informar?",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id,
                        metadata={"step": "cnpj"}
                    )
                if not empresa_ok:
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text="Agora me informe o nome da empresa, por favor.",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id,
                        metadata={"step": "empresa"}
                    )
                # Se já tem ambos, pode seguir para o data_agent
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text="Ótimo! Agora me diga seu nome, por favor.",
                    confidence=0.9,
                    should_continue=True,
                    next_agent="data_agent",
                    metadata={"step": "usuario"}
                )
            
            # Extrai informações automaticamente
            extracted_info = self.data_collector.extract_client_info(
                message.body or "", 
                session.conversation_context
            )
            
            # Atualiza dados do cliente
            if extracted_info:
                if "cliente" not in session.conversation_context:
                    session.conversation_context["cliente"] = {}
                
                session.conversation_context["cliente"].update(extracted_info)
                logger.info(f"[ProactiveReception] Dados extraídos: {extracted_info}")
            
            # Incrementa contador
            session.conversation_context["interaction_count"] = session.conversation_context.get("interaction_count", 0) + 1
            
            # Busca dados existentes
            cliente_info = session.conversation_context.get("cliente", {})
            nome_cliente = cliente_info.get("nome", "").split()[0] if cliente_info.get("nome") else ""
            
            # Verifica o que falta coletar
            missing_info = self.data_collector.get_missing_essential_info(session.conversation_context)
            should_collect = self.data_collector.should_collect_data_now(
                session.conversation_context, 
                message.body or ""
            )
            
            # Prepara contexto
            additional_context = {
                "cliente_nome": nome_cliente,
                "cliente_empresa": cliente_info.get("empresa", ""),
                "has_client_data": bool(cliente_info),
                "missing_data": missing_info,
                "should_collect": should_collect,
                "is_first_interaction": session.conversation_context.get("interaction_count", 0) <= 1
            }
            
            # Modifica o prompt baseado no contexto
            custom_prompt = self.system_prompt
            
            # Se é primeira interação e não tem nome, força pedido de nome
            if additional_context["is_first_interaction"] and "nome" in missing_info:
                custom_prompt += "\n\nIMPORTANTE: Esta é a primeira interação. Apresente-se e pergunte o nome da pessoa de forma natural e amigável!"
            elif nome_cliente and "empresa" in missing_info and should_collect:
                custom_prompt += f"\n\nIMPORTANTE: Você já sabe que o nome é {nome_cliente}. Agora pergunte sobre a empresa de forma natural!"
            elif nome_cliente and cliente_info.get("empresa") and "email" in missing_info:
                custom_prompt += f"\n\nINFO: Nome: {nome_cliente}, Empresa: {cliente_info['empresa']}. Se for relevante, pergunte o email."
            
            # Se tem todos os dados, adiciona ao contexto
            if not missing_info:
                info_parts = []
                if cliente_info.get("nome"):
                    info_parts.append(f"Nome: {cliente_info['nome']}")
                if cliente_info.get("empresa"):
                    info_parts.append(f"Empresa: {cliente_info['empresa']}")
                if cliente_info.get("email"):
                    info_parts.append(f"Email: {cliente_info['email']}")
                
                if info_parts:
                    custom_prompt += f"\n\nCLIENTE ATUAL:\n" + "\n".join(info_parts)
                    custom_prompt += "\n\nUse essas informações para personalizar!"
            
            # Gera resposta
            response_text = await self.llm_service.generate_response(
                prompt=message.body or "",
                system_message=custom_prompt,
                session_id=session.session_id,
                context=additional_context
            )
            
            # Se não conseguiu gerar, usa fallback
            if not response_text or "erro interno" in response_text.lower():
                response_text = self._get_contextual_fallback(
                    message.body or "", 
                    nome_cliente, 
                    missing_info,
                    additional_context["is_first_interaction"]
                )
            
            # Analisa redirecionamento
            user_message_lower = (message.body or "").lower()
            next_agent = self.agent_id
            
            # Só redireciona se já tem dados básicos coletados
            if len(missing_info) <= 1:  # Permite redirecionamento se falta no máximo 1 info
                if any(word in user_message_lower for word in ["relatório", "dados", "vendas", "dashboard"]):
                    next_agent = "data_agent"
                elif any(word in user_message_lower for word in ["erro", "problema", "bug", "não funciona"]):
                    next_agent = "support_agent"
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.9,
                should_continue=True,
                next_agent=next_agent,
                metadata={
                    "has_client_data": bool(cliente_info),
                    "client_name": nome_cliente,
                    "missing_info": missing_info,
                    "extracted_info": extracted_info
                }
            )
            
        except Exception as e:
            logger.error(f"[ProactiveReception] Erro: {e}", exc_info=True)
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Opa! Tive um probleminha técnico. 😅 Mas vamos lá, me diz seu nome pra gente começar!",
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id,
                metadata={"error": str(e)}
            )
    
    def _get_contextual_fallback(self, user_message: str, client_name: str, missing_info: List[str], is_first: bool) -> str:
        """Fallback contextual proativo"""
        message_lower = user_message.lower()
        
        # Primeira interação - sempre pede nome
        if is_first and "nome" in missing_info:
            return random.choice([
                "Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?",
                "Opa! Que bom te ver por aqui! Eu sou o Alex, e você?",
                "Olá! Bem-vindo! 👋 Meu nome é Alex, sou seu assistente. Como posso te chamar?",
                "Oi oi! Sou o Alex, tô aqui pra te ajudar! Qual seu nome?"
            ])
        
        # Se tem nome mas falta empresa
        if client_name and "empresa" in missing_info:
            return random.choice([
                f"Legal, {client_name}! Prazer! De qual empresa você é?",
                f"Ótimo te conhecer, {client_name}! Me conta, você trabalha em qual empresa?",
                f"Que bom, {client_name}! E você tá falando de qual empresa?"
            ])
        
        # Se perguntou sobre serviços
        if any(word in message_lower for word in ["serviço", "serviços", "o que você faz"]):
            if client_name:
                return f"Ah {client_name}, eu faço várias coisas! Relatórios, suporte técnico, agendamentos... Mas antes, de qual empresa você é?"
            else:
                return "Opa! Eu ajudo com relatórios, suporte, agendamentos... Mas primeiro, qual seu nome? Assim fica melhor pra conversar!"
        
        # Fallback genérico proativo
        if "nome" in missing_info:
            return "Oi! Acho que ainda não nos apresentamos direito. Sou o Alex! E você, como se chama?"
        else:
            return f"Oi {client_name}! Como posso te ajudar hoje?"
    
    def get_priority(self) -> int:
        return 10
