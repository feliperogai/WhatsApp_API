from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
import re
import logging

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class LLMOnboardingAgent(LLMBaseAgent):
    """Agente responsável por coletar informações do usuário - VERSÃO DIRETA"""
    
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="onboarding_agent",
            name="Agente de Cadastro Direto",
            description="Coleta informações essenciais do usuário imediatamente",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é Alex, assistente que precisa coletar dados do cliente IMEDIATAMENTE.

OBJETIVO: Coletar rapidamente:
1. Nome completo
2. Nome da empresa  
3. CNPJ
4. O que precisa/problema

REGRAS IMPORTANTES:
- Na PRIMEIRA interação, já peça o nome
- Seja direto mas educado
- Uma informação por vez
- Confirme antes de prosseguir
- Se a pessoa fornecer várias infos, agradeça e confirme

FLUXO DIRETO:
User: "oi"
You: "Oi! Sou o Alex, vou te ajudar! 😊 Para começar, qual é o seu nome completo?"

User: "João Silva"  
You: "Prazer, João! E qual é o nome da sua empresa?"

User: "TechCorp Ltda"
You: "Ótimo! Agora preciso do CNPJ da TechCorp Ltda, por favor."

User: "12.345.678/0001-90"
You: "Perfeito! Por último, me conta o que a TechCorp está precisando? Como posso ajudar vocês?"

IMPORTANTE:
- NÃO faça conversa fiada
- NÃO pergunte "tudo bem?" ou similares
- Vá DIRETO para coleta de dados
- Seja eficiente mas cordial"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return True  # Sempre pode processar durante onboarding
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """SEMPRE processa se onboarding não está completo"""
        if not session:
            return True
            
        onboarding_state = session.conversation_context.get("onboarding_state", {})
        
        # Se não tem estado ou não completou, processa
        if not onboarding_state or not onboarding_state.get("completed", False):
            return True
        
        return False
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem coletando informações"""
        try:
            # Inicializa estado do onboarding se não existe
            if "onboarding_state" not in session.conversation_context:
                logger.info("[Onboarding] Iniciando coleta de dados para novo usuário")
                session.conversation_context["onboarding_state"] = {
                    "fields": {
                        "nome": {"collected": False, "value": None},
                        "nome_empresa": {"collected": False, "value": None},
                        "cnpj": {"collected": False, "value": None},
                        "necessidade": {"collected": False, "value": None}
                    },
                    "completed": False,
                    "current_field": "nome"
                }
            
            onboarding_state = session.conversation_context["onboarding_state"]
            
            # Extrai informações da mensagem atual
            extracted_info = self._extract_information(message.body or "", onboarding_state["current_field"])
            
            # Atualiza campos coletados
            for field, value in extracted_info.items():
                if field in onboarding_state["fields"] and value:
                    onboarding_state["fields"][field]["collected"] = True
                    onboarding_state["fields"][field]["value"] = value
                    logger.info(f"[Onboarding] Campo '{field}' coletado: {value}")
            
            # Verifica se todas as informações foram coletadas
            all_collected = all(
                field_data["collected"] 
                for field_data in onboarding_state["fields"].values()
            )
            
            if all_collected:
                # Marca como completo
                onboarding_state["completed"] = True
                
                # Salva dados do cliente
                session.conversation_context["cliente"] = {
                    "nome": onboarding_state["fields"]["nome"]["value"],
                    "empresa": onboarding_state["fields"]["nome_empresa"]["value"],
                    "cnpj": onboarding_state["fields"]["cnpj"]["value"],
                    "necessidade": onboarding_state["fields"]["necessidade"]["value"]
                }
                
                logger.info(f"[Onboarding] Coleta completa! Dados: {session.conversation_context['cliente']}")
                
                response_text = f"""Excelente! Já tenho todos os seus dados:

✅ **{onboarding_state["fields"]["nome"]["value"]}**
🏢 **{onboarding_state["fields"]["nome_empresa"]["value"]}**
📄 CNPJ: {onboarding_state["fields"]["cnpj"]["value"]}

Entendi que vocês precisam: {onboarding_state["fields"]["necessidade"]["value"]}

Vou te ajudar com isso agora mesmo! Um momento..."""
                
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text=response_text,
                    confidence=1.0,
                    should_continue=True,
                    next_agent="reception_agent",
                    metadata={"onboarding_completed": True}
                )
            
            # Determina próximo campo a coletar
            next_field = self._get_next_field_to_collect(onboarding_state["fields"])
            onboarding_state["current_field"] = next_field
            
            # Gera resposta baseada no campo atual
            response_text = self._generate_field_question(next_field, onboarding_state["fields"])
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.95,
                should_continue=True,
                next_agent=self.agent_id,  # Continua no onboarding
                metadata={
                    "fields_collected": sum(1 for f in onboarding_state["fields"].values() if f["collected"]),
                    "current_field": next_field
                }
            )
            
        except Exception as e:
            logger.error(f"Erro no onboarding: {e}", exc_info=True)
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Ops, tive um probleminha. Vamos continuar? Me diga seu nome completo, por favor.",
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id
            )
    
    def _generate_field_question(self, field: str, fields: Dict) -> str:
        """Gera pergunta direta para o campo"""
        
        # Se é a primeira mensagem (nenhum campo coletado)
        if not any(f["collected"] for f in fields.values()):
            return "Oi! Sou o Alex, vou te ajudar! 😊 Para começar, qual é o seu nome completo?"
        
        # Perguntas específicas por campo
        if field == "nome":
            return "Para começar, qual é o seu nome completo?"
        
        elif field == "nome_empresa":
            nome = fields["nome"]["value"]
            if nome:
                primeiro_nome = nome.split()[0]
                return f"Prazer, {primeiro_nome}! E qual é o nome da sua empresa?"
            return "Legal! E qual é o nome da sua empresa?"
        
        elif field == "cnpj":
            empresa = fields["nome_empresa"]["value"]
            if empresa:
                return f"Ótimo! Agora preciso do CNPJ da {empresa}, por favor."
            return "Ótimo! Agora preciso do CNPJ da empresa, por favor."
        
        elif field == "necessidade":
            empresa = fields["nome_empresa"]["value"] or "empresa"
            return f"Perfeito! Por último, me conta o que a {empresa} está precisando? Como posso ajudar vocês?"
        
        return "Pode me passar essa informação?"
    
    def _extract_information(self, text: str, current_field: str) -> Dict[str, str]:
        """Extrai informações do texto com contexto do campo atual"""
        extracted = {}
        text_lower = text.lower()
        
        # Se estamos esperando nome e não tem outros padrões, assume que é o nome
        if current_field == "nome" and len(text.split()) <= 5:
            # Verifica se não é uma saudação comum
            greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", 
                        "opa", "opa!", "e ai", "eae", "to bem", "tudo bem", "td bem"]
            if text_lower not in greetings and not any(g in text_lower for g in greetings):
                extracted["nome"] = text.strip().title()
        
        # Se estamos esperando empresa e não é CNPJ
        elif current_field == "nome_empresa":
            # Verifica se não é CNPJ
            if not re.search(r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}', text):
                # Remove palavras comuns que não são nome de empresa
                if len(text.split()) <= 6 and not any(char.isdigit() for char in text[:5]):
                    extracted["nome_empresa"] = text.strip()
        
        # Sempre tenta extrair CNPJ se encontrar o padrão
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}'
        cnpj_match = re.search(cnpj_pattern, text)
        if cnpj_match:
            extracted["cnpj"] = self._format_cnpj(cnpj_match.group())
        
        # Se estamos esperando necessidade
        if current_field == "necessidade" and len(text.split()) > 3:
            extracted["necessidade"] = text.strip()
        
        return extracted
    
    def _get_next_field_to_collect(self, fields: Dict) -> str:
        """Determina próximo campo a coletar"""
        priority_order = ["nome", "nome_empresa", "cnpj", "necessidade"]
        
        for field in priority_order:
            if not fields[field]["collected"]:
                return field
        
        return None
    
    def _format_cnpj(self, cnpj: str) -> str:
        """Formata CNPJ"""
        numbers = re.sub(r'[^0-9]', '', cnpj)
        if len(numbers) == 14:
            return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"
        return cnpj
    
    def get_priority(self) -> int:
        return 20  # Máxima prioridade - sempre processa primeiro