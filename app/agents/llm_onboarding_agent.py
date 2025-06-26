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
    """Agente responsável por coletar informações do usuário"""
    
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="onboarding_agent",
            name="Agente de Cadastro",
            description="Coleta informações essenciais do usuário de forma conversacional",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self) -> str:
        return """Você é Alex, um assistente amigável que precisa coletar algumas informações básicas.

PERSONALIDADE:
- Seja caloroso, educado e profissional
- Use linguagem natural e conversacional
- Demonstre interesse genuíno pelo cliente
- Evite ser robótico ou muito formal

OBJETIVO:
Coletar de forma natural e conversacional:
1. Nome completo da pessoa
2. Nome da empresa
3. CNPJ da empresa
4. O que a pessoa precisa/qual problema quer resolver

IMPORTANTE:
- Colete UMA informação por vez
- Confirme o que foi informado antes de prosseguir
- Se a pessoa fornecer múltiplas informações de uma vez, agradeça e confirme todas
- Seja flexível - se a pessoa já fornecer várias informações, não peça novamente
- Use contexto para determinar qual informação pedir próxima
- Ao final, resuma tudo e confirme se está correto

EXEMPLOS DE FLUXO:
User: "oi"
You: "Oi! Seja muito bem-vindo(a)! Eu sou o Alex, vou te ajudar hoje. 😊 Para começar e te atender melhor, pode me dizer seu nome?"

User: "João Silva"
You: "Prazer, João! Ótimo ter você aqui. E qual é o nome da sua empresa?"

User: "TechCorp Ltda"
You: "Legal, João! A TechCorp Ltda parece interessante! Para completar o cadastro, poderia me passar o CNPJ da empresa?"

User: "12.345.678/0001-90"
You: "Perfeito! CNPJ anotado. Agora me conta, João, o que a TechCorp está precisando? Como posso ajudar vocês?"

NUNCA:
- Peça informações que já foram fornecidas
- Use termos como "formulário", "cadastro", "registro"
- Seja impaciente ou apressado
- Use formatação de lista para pedir informações"""
    
    def _get_tools(self) -> List[BaseTool]:
        return []
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Onboarding agent sempre pode lidar se há informações pendentes
        return True
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Verifica se pode processar - sempre TRUE se faltam informações"""
        # Carrega estado do onboarding da sessão
        onboarding_state = session.conversation_context.get("onboarding_state", {})
        
        # Se não tem estado, cria
        if not onboarding_state:
            return True
        
        # Se já completou onboarding, não processa
        if onboarding_state.get("completed", False):
            return False
        
        # Se falta alguma informação, processa
        return True
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem coletando informações"""
        try:
            # Inicializa ou carrega estado do onboarding
            if "onboarding_state" not in session.conversation_context:
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
                
                response_text = f"""Perfeito! Deixa eu confirmar os dados:

👤 **{onboarding_state["fields"]["nome"]["value"]}**
🏢 **{onboarding_state["fields"]["nome_empresa"]["value"]}**
📄 CNPJ: {onboarding_state["fields"]["cnpj"]["value"]}
💼 Necessidade: {onboarding_state["fields"]["necessidade"]["value"]}

Tudo certinho? Agora posso te ajudar com:
• 📊 Relatórios e dados da empresa
• 🔧 Suporte técnico
• 📅 Agendamentos

O que você gostaria de fazer primeiro?"""
                
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
            
            # Constrói contexto para o LLM
            context_info = {
                "collected_fields": {},
                "pending_fields": [],
                "current_field_to_collect": next_field,
                "user_just_provided": list(extracted_info.keys())
            }
            
            # Adiciona campos coletados ao contexto
            for field, data in onboarding_state["fields"].items():
                if data["collected"]:
                    context_info["collected_fields"][field] = data["value"]
                else:
                    context_info["pending_fields"].append(field)
            
            # Adiciona contexto específico
            additional_context = {
                "onboarding_context": context_info,
                "user_message": message.body,
                "conversation_stage": "collecting_" + next_field
            }
            
            # Gera resposta via LLM
            response_text = await self.llm_service.generate_response(
                prompt=message.body or "",
                system_message=self.system_prompt + f"\n\nCONTEXTO ATUAL:\n{str(context_info)}",
                session_id=session.session_id,
                context=additional_context
            )
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.95,
                should_continue=True,
                next_agent=self.agent_id,  # Continua no onboarding
                metadata={
                    "fields_collected": len(context_info["collected_fields"]),
                    "fields_pending": len(context_info["pending_fields"])
                }
            )
            
        except Exception as e:
            logger.error(f"Erro no onboarding: {e}")
            return self._create_error_response(str(e))
    
    def _extract_information(self, text: str, current_field: str) -> Dict[str, str]:
        """Extrai informações do texto com contexto do campo atual"""
        extracted = {}
        text_lower = text.lower()
        
        # Se estamos esperando nome e não tem outros padrões, assume que é o nome
        if current_field == "nome" and len(text.split()) <= 4:
            # Verifica se não é uma saudação comum
            greetings = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "opa", "opa!", "e ai", "eae"]
            if text_lower not in greetings:
                extracted["nome"] = text.title()
        
        # Tenta extrair CNPJ
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}'
        cnpj_match = re.search(cnpj_pattern, text)
        if cnpj_match:
            extracted["cnpj"] = self._format_cnpj(cnpj_match.group())
        
        # Tenta identificar nome de empresa
        if current_field == "nome_empresa" and "cnpj" not in extracted:
            # Se não tem padrões específicos de empresa, assume que é o nome da empresa
            if len(text.split()) <= 5 and not any(char.isdigit() for char in text):
                extracted["nome_empresa"] = text.strip()
        else:
            # Padrões específicos de empresa
            company_patterns = [
                r'([A-Za-z\s]+(?:LTDA|ltda|Ltda|SA|sa|S\.A\.|MEI|mei|EIRELI|eireli|EPP|epp|ME|me))',
                r'empresa\s+([A-Za-z\s]+)',
                r'([A-Za-z]+(?:Corp|corp|Tech|tech|Solutions|solutions|Services|services))'
            ]
            
            for pattern in company_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    extracted["nome_empresa"] = match.group(1).strip()
                    break
        
        # Se estamos esperando necessidade e a mensagem tem mais de 5 palavras
        if current_field == "necessidade" and len(text.split()) > 5:
            extracted["necessidade"] = text
        
        # Se tem @ pode ser email com nome
        if '@' in text and current_field == "nome":
            email_match = re.search(r'([a-zA-Z]+)\.?([a-zA-Z]+)?@', text)
            if email_match:
                nome = email_match.group(1)
                if email_match.group(2):
                    nome += f" {email_match.group(2)}"
                extracted["nome"] = nome.title()
        
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
        return 15  # Máxima prioridade para onboarding