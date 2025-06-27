import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re

from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class SmartDataCollector:
    """Coletor inteligente de dados do cliente integrado ao fluxo natural"""
    
    @staticmethod
    def extract_client_info(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai informações do cliente de forma inteligente do texto"""
        extracted = {}
        text_lower = text.lower()
        
        # Extrai nome (heurísticas melhoradas)
        if not context.get("cliente", {}).get("nome"):
            # Padrões comuns de apresentação
            name_patterns = [
                r"(?:meu nome é|me chamo|sou o?a?|aqui é o?a?)\s+([A-Za-zÀ-ÿ\s]+)",
                r"(?:é o?a?)\s+([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.)",
                r"^([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*)\s*(?:,|\.|\!)",
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    nome = match.group(1).strip().title()
                    # Valida se parece um nome real
                    if len(nome.split()) <= 5 and not any(word in nome.lower() for word in ["oi", "olá", "bom", "boa"]):
                        extracted["nome"] = nome
                        break
        
        # Extrai empresa
        if not context.get("cliente", {}).get("empresa"):
            empresa_patterns = [
                r"(?:empresa|trabalho na|sou da|represento a?)\s+([A-Za-zÀ-ÿ0-9\s&\-\.]+)",
                r"(?:da|na)\s+([A-Z][A-Za-zÀ-ÿ0-9\s&\-\.]+(?:LTDA|ME|SA|S\.A\.|Ltd|Inc)?)",
            ]
            
            for pattern in empresa_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    empresa = match.group(1).strip()
                    if len(empresa) > 2:
                        extracted["empresa"] = empresa
                        break
        
        # Extrai CNPJ
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}'
        cnpj_match = re.search(cnpj_pattern, text)
        if cnpj_match and not context.get("cliente", {}).get("cnpj"):
            extracted["cnpj"] = SmartDataCollector._format_cnpj(cnpj_match.group())
        
        # Extrai email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match and not context.get("cliente", {}).get("email"):
            extracted["email"] = email_match.group()
        
        # Extrai telefone adicional
        phone_pattern = r'(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}-?\d{4}'
        phone_match = re.search(phone_pattern, text)
        if phone_match and not context.get("cliente", {}).get("telefone_adicional"):
            extracted["telefone_adicional"] = phone_match.group()
        
        return extracted
    
    @staticmethod
    def _format_cnpj(cnpj: str) -> str:
        """Formata CNPJ"""
        numbers = re.sub(r'[^0-9]', '', cnpj)
        if len(numbers) == 14:
            return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"
        return cnpj
    
    @staticmethod
    def get_missing_info(context: Dict[str, Any]) -> list:
        """Retorna lista de informações que ainda faltam"""
        cliente = context.get("cliente", {})
        missing = []
        
        essential_fields = {
            "nome": "nome completo",
            "empresa": "nome da empresa",
            "email": "email de contato"
        }
        
        for field, description in essential_fields.items():
            if not cliente.get(field):
                missing.append(description)
        
        return missing
    
    @staticmethod
    def should_ask_for_info(context: Dict[str, Any], current_message: str) -> Optional[str]:
        """Decide se deve pedir alguma informação faltante"""
        # Não interrompe se o usuário está fazendo uma pergunta específica
        if any(word in current_message.lower() for word in ["?", "como", "quanto", "quando", "onde", "qual"]):
            return None
        
        # Não interrompe se está relatando problema urgente
        if any(word in current_message.lower() for word in ["erro", "urgente", "parado", "problema", "bug"]):
            return None
        
        missing = SmartDataCollector.get_missing_info(context)
        
        # Se faltam informações essenciais e é um bom momento
        if missing and len(missing) <= 2:  # Pede no máximo 2 infos por vez
            # Só pede em momentos apropriados (após resolver algo ou em pausas naturais)
            interaction_count = context.get("interaction_count", 0)
            last_request = context.get("last_info_request", 0)
            
            # Evita pedir muito frequentemente
            if interaction_count - last_request >= 3:
                return missing[0]  # Pede uma info por vez
        
        return None


# class LLMSmartReceptionAgent(LLMBaseAgent):
#     """Agente de recepção inteligente com coleta de dados integrada"""
#     def __init__(self, llm_service: LLMService):
#         super().__init__(
#             agent_id="smart_reception_agent",
#             name="Alex - Assistente Inteligente",
#             description="Assistente que conversa naturalmente e coleta dados quando apropriado",
#             llm_service=llm_service
#         )
#         self.data_collector = SmartDataCollector()
#     def _get_system_prompt(self) -> str:
#         return "(Prompt desabilitado para forçar fluxo do LLMReceptionAgent)"
#     async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
#         return AgentResponse(
#             agent_id=self.agent_id,
#             response_text="(Desabilitado)",
#             confidence=0.0,
#             should_continue=True,
#             next_agent="reception_agent"
#         )


# Atualização do Orchestrator para usar o novo sistema
def update_orchestrator_route_logic():
    """Atualiza a lógica de roteamento do orchestrator"""
    return '''
    def _route_to_agent(self, state: ConversationState) -> str:
        """Determina para qual agente rotear - INTELIGENTE"""
        # NÃO força mais onboarding obrigatório
        # Usa classificação de intenção natural
        
        routing = state.get("routing_decision", "reception")
        routing_map = {
            "reception": "reception",
            "classification": "classification",
            "data": "data_analysis", 
            "support": "technical_support"
        }
        
        # Só usa onboarding se explicitamente necessário
        # Por exemplo, se o cliente pedir para se cadastrar
        
        return routing_map.get(routing, "reception")
    '''

# Script para aplicar as mudanças
def get_update_script():
    return '''#!/bin/bash
# Script para atualizar o sistema de coleta de dados

echo "🔧 Atualizando sistema de coleta de dados..."

# 1. Backup do arquivo atual
cp app/agents/llm_reception_agent.py app/agents/llm_reception_agent.py.backup

# 2. Cria o novo Smart Reception Agent
cat > app/agents/llm_smart_reception_agent.py << 'EOF'
# Conteúdo do SmartDataCollector e LLMSmartReceptionAgent aqui
EOF

# 3. Atualiza o orchestrator para usar o novo agente
sed -i 's/LLMReceptionAgent/LLMSmartReceptionAgent/g' app/core/langgraph_orchestrator.py
sed -i 's/from app.agents.llm_reception_agent/from app.agents.llm_smart_reception_agent/g' app/core/langgraph_orchestrator.py

# 4. Remove a lógica forçada de onboarding
# Edita a função _route_to_agent no orchestrator

echo "✅ Sistema atualizado!"
echo "🚀 Reinicie o serviço: docker-compose restart jarvis-whatsapp"
'''