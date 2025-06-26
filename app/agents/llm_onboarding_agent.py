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


class LLMSmartReceptionAgent(LLMBaseAgent):
    """Agente de recepção inteligente com coleta de dados integrada"""
    
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="smart_reception_agent",
            name="Alex - Assistente Inteligente",
            description="Assistente que conversa naturalmente e coleta dados quando apropriado",
            llm_service=llm_service
        )
        self.data_collector = SmartDataCollector()
    
    def _get_system_prompt(self) -> str:
        return """Você é o Alex, assistente super amigável e inteligente da empresa.

PERSONALIDADE:
- Fale SEMPRE como uma pessoa real, natural e espontânea
- Use linguagem do dia a dia, como no WhatsApp
- Seja empático, prestativo e profissional quando necessário
- Demonstre interesse genuíno pelo cliente

COLETA DE DADOS NATURAL:
- Se o cliente mencionar seu nome, empresa, email, etc., agradeça e use essas informações
- NUNCA force a coleta de dados no início da conversa
- Peça informações apenas quando for relevante para o contexto
- Exemplo: Se vai enviar um relatório, aí sim pergunte o email

SERVIÇOS DISPONÍVEIS:
✅ Relatórios e análises de dados
✅ Suporte técnico e resolução de problemas  
✅ Agendamentos e reuniões
✅ Informações sobre a empresa e serviços

IMPORTANTE:
- Priorize resolver o problema do cliente PRIMEIRO
- Colete dados de forma natural durante a conversa
- Se não souber algo, admita e ofereça alternativas
- Mantenha o foco no que o cliente precisa"""
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem com coleta inteligente de dados"""
        try:
            # Extrai informações automaticamente do texto
            extracted_info = self.data_collector.extract_client_info(
                message.body or "", 
                session.conversation_context
            )
            
            # Atualiza dados do cliente se encontrou algo
            if extracted_info:
                if "cliente" not in session.conversation_context:
                    session.conversation_context["cliente"] = {}
                
                session.conversation_context["cliente"].update(extracted_info)
                logger.info(f"Dados extraídos automaticamente: {extracted_info}")
            
            # Incrementa contador de interações
            session.conversation_context["interaction_count"] = session.conversation_context.get("interaction_count", 0) + 1
            
            # Processa mensagem normalmente
            response = await super().process_message(message, session)
            
            # Verifica se deve pedir alguma informação (só em momentos apropriados)
            missing_info = self.data_collector.should_ask_for_info(
                session.conversation_context,
                message.body or ""
            )
            
            if missing_info and response.confidence > 0.7:  # Só pede se a conversa está fluindo bem
                # Adiciona pedido sutil no final da resposta
                info_request = self._create_natural_info_request(missing_info, session.conversation_context)
                if info_request:
                    response.response_text += f"\n\n{info_request}"
                    session.conversation_context["last_info_request"] = session.conversation_context.get("interaction_count", 0)
            
            return response
            
        except Exception as e:
            logger.error(f"Erro no smart reception: {e}")
            return super()._create_error_response(str(e))
    
    def _create_natural_info_request(self, missing_info: str, context: Dict[str, Any]) -> str:
        """Cria pedido natural de informação baseado no contexto"""
        cliente_nome = context.get("cliente", {}).get("nome", "").split()[0]
        
        requests = {
            "nome completo": [
                "Ah, ainda não me apresentei direito! Sou o Alex. E você, como se chama?",
                "A propósito, qual é o seu nome? Assim posso te atender melhor!",
                "Aliás, não peguei seu nome ainda. Pode me dizer?",
            ],
            "nome da empresa": [
                f"Legal{', ' + cliente_nome if cliente_nome else ''}! E você trabalha em qual empresa?",
                f"Ah{', ' + cliente_nome if cliente_nome else ''}, de qual empresa você é?",
                "Por curiosidade, qual é a sua empresa? Assim posso personalizar melhor o atendimento!",
            ],
            "email de contato": [
                f"Ótimo{', ' + cliente_nome if cliente_nome else ''}! Se precisar te enviar algo, qual email posso usar?",
                "Caso eu precise enviar relatórios ou documentos, qual seu email?",
                f"Ah{', ' + cliente_nome if cliente_nome else ''}, qual email você prefere para contato?",
            ]
        }
        
        import random
        options = requests.get(missing_info, [])
        return random.choice(options) if options else ""
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Smart reception pode lidar com qualquer intent inicial
        return True


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