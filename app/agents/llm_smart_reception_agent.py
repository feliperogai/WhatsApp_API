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
                    palavras = nome.split()
                    if (len(palavras) <= 5 and 
                        not any(word in nome.lower() for word in ["oi", "olá", "bom", "boa", "tchau", "obrigado"]) and
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
        
        # Extrai CNPJ
        cnpj_pattern = r'\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}'
        cnpj_match = re.search(cnpj_pattern, text)
        if cnpj_match and not context.get("cliente", {}).get("cnpj"):
            cnpj = SmartDataCollector._format_cnpj(cnpj_match.group())
            extracted["cnpj"] = cnpj
            logger.info(f"CNPJ extraído: {cnpj}")
        
        # Extrai email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match and not context.get("cliente", {}).get("email"):
            email = email_match.group().lower()
            extracted["email"] = email
            logger.info(f"Email extraído: {email}")
        
        # Extrai telefone adicional
        phone_pattern = r'(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}-?\d{4}'
        phone_match = re.search(phone_pattern, text)
        if phone_match and not context.get("cliente", {}).get("telefone_adicional"):
            phone = phone_match.group()
            extracted["telefone_adicional"] = phone
            logger.info(f"Telefone extraído: {phone}")
        
        return extracted
    
    @staticmethod
    def _format_cnpj(cnpj: str) -> str:
        """Formata CNPJ"""
        numbers = re.sub(r'[^0-9]', '', cnpj)
        if len(numbers) == 14:
            return f"{numbers[:2]}.{numbers[2:5]}.{numbers[5:8]}/{numbers[8:12]}-{numbers[12:]}"
        return cnpj
    
    @staticmethod
    def get_missing_info(context: Dict[str, Any]) -> List[str]:
        """Retorna lista de informações que ainda faltam"""
        cliente = context.get("cliente", {})
        missing = []
        
        # Apenas informações essenciais
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
        if any(word in current_message.lower() for word in ["erro", "urgente", "parado", "problema", "bug", "não funciona"]):
            return None
        
        missing = SmartDataCollector.get_missing_info(context)
        if not missing:
            return None
        
        # Verifica contexto apropriado para pedir informações
        interaction_count = context.get("interaction_count", 0)
        last_request = context.get("last_info_request", -5)
        
        # Espera pelo menos 3 interações entre pedidos
        if interaction_count - last_request >= 3:
            # Pede apenas uma informação por vez
            return missing[0]
        
        return None


class LLMSmartReceptionAgent(LLMBaseAgent):
    """Agente de recepção inteligente com coleta de dados integrada"""
    
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",  # Mantém o ID original para compatibilidade
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
- Na PRIMEIRA interação, SEMPRE pergunte primeiro o nome da empresa, depois o CNPJ
- Exemplo: 'Oi! Para começarmos, qual o nome da sua empresa?'
- Depois: 'E qual o CNPJ da empresa?'
- Só depois de empresa e CNPJ, pergunte o nome do usuário
- NUNCA force a coleta de dados do usuário antes da empresa
- NUNCA faça um questionário ou lista de perguntas
- Peça informações apenas quando for relevante para o contexto
- Exemplo: Se vai enviar um relatório, aí sim pergunte o email naturalmente

SERVIÇOS DISPONÍVEIS:
✅ Relatórios e análises de dados empresariais
✅ Suporte técnico e resolução de problemas  
✅ Agendamentos e reuniões
✅ Informações sobre a empresa e serviços

IMPORTANTE:
- Priorize SEMPRE resolver o problema do cliente PRIMEIRO
- Colete dados de forma natural durante a conversa
- Se o cliente perguntar sobre serviços, explique de forma conversacional
- Mantenha o foco no que o cliente precisa agora"""
    
    def _is_intent_compatible(self, intent: str) -> bool:
        # Reception agent pode lidar com qualquer intent inicial
        return intent in ["reception", "general_chat", ""] or intent is None
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        """Determina se pode processar esta mensagem"""
        # Sempre processa se é o agente atual
        if session and session.current_agent == self.agent_id:
            return True
        
        # Se não há agente definido ou é primeira mensagem
        if not session or not session.current_agent:
            return True
            
        # Se não há histórico, é primeira interação
        if not session.message_history:
            return True
        
        # Palavras que indicam voltar ao início ou conversa geral
        message_text = (message.body or "").lower()
        reception_keywords = [
            "oi", "olá", "ola", "hello", "hey", "opa", "eae", "e ai",
            "bom dia", "boa tarde", "boa noite", "fala", "salve",
            "inicio", "começar", "voltar", "menu", "principal",
            "tchau", "até", "obrigado", "valeu", "flw",
            "serviço", "serviços", "o que você faz", "o que faz",
            "como funciona", "me explica", "queria saber"
        ]
        
        return any(keyword in message_text for keyword in reception_keywords)
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        """Processa mensagem com coleta inteligente de dados"""
        try:
            # Log inicial
            logger.info(f"[SmartReception] Processando mensagem: {message.body}")
            
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
                logger.info(f"[SmartReception] Dados extraídos: {extracted_info}")
            
            # Incrementa contador de interações
            session.conversation_context["interaction_count"] = session.conversation_context.get("interaction_count", 0) + 1
            
            # Busca dados existentes do cliente
            cliente_info = session.conversation_context.get("cliente", {})
            nome_cliente = cliente_info.get("nome", "").split()[0] if cliente_info.get("nome") else ""
            
            # Adiciona contexto do cliente
            additional_context = {
                "cliente_nome": nome_cliente,
                "cliente_empresa": cliente_info.get("empresa", ""),
                "has_client_data": bool(cliente_info),
                "missing_data": self.data_collector.get_missing_info(session.conversation_context)
            }
            
            # Modifica o prompt se tem dados do cliente
            custom_prompt = self.system_prompt
            if cliente_info:
                info_parts = []
                if cliente_info.get("nome"):
                    info_parts.append(f"Nome: {cliente_info['nome']}")
                if cliente_info.get("empresa"):
                    info_parts.append(f"Empresa: {cliente_info['empresa']}")
                if cliente_info.get("email"):
                    info_parts.append(f"Email: {cliente_info['email']}")
                
                if info_parts:
                    custom_prompt += f"\n\nINFORMAÇÕES DO CLIENTE:\n" + "\n".join(info_parts)
                    custom_prompt += "\n\nUse essas informações para personalizar o atendimento!"
            
            # Gera resposta via LLM
            response_text = await self.llm_service.generate_response(
                prompt=message.body or "",
                system_message=custom_prompt,
                session_id=session.session_id,
                context=additional_context
            )
            
            # Se não conseguiu gerar resposta, usa fallback
            if not response_text or "erro interno" in response_text.lower():
                response_text = self._get_contextual_fallback(message.body or "", nome_cliente)
            
            # Analisa intenção do usuário
            user_message_lower = (message.body or "").lower()
            
            # Redirecionamento baseado em palavras-chave
            next_agent = self.agent_id
            if any(word in user_message_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi", "métrica"]):
                logger.info("[SmartReception] Detectado interesse em dados - redirecionando")
                next_agent = "data_agent"
            elif any(word in user_message_lower for word in ["erro", "problema", "bug", "não funciona", "travou", "lento"]):
                logger.info("[SmartReception] Detectado problema técnico - redirecionando")
                next_agent = "support_agent"
            elif any(word in user_message_lower for word in ["marcar", "agendar", "reunião", "horário", "calendário"]):
                logger.info("[SmartReception] Detectado interesse em agendamento - redirecionando")
                next_agent = "scheduling_agent"
            
            # Verifica se deve pedir alguma informação (só em momentos apropriados)
            missing_info = self.data_collector.should_ask_for_info(
                session.conversation_context,
                message.body or ""
            )
            
            # Só adiciona pedido se a conversa está fluindo bem e não está redirecionando
            if missing_info and next_agent == self.agent_id:
                info_request = self._create_natural_info_request(missing_info, session.conversation_context)
                if info_request:
                    response_text += f"\n\n{info_request}"
                    session.conversation_context["last_info_request"] = session.conversation_context.get("interaction_count", 0)
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.9,
                should_continue=True,
                next_agent=next_agent,
                metadata={
                    "has_client_data": bool(cliente_info),
                    "client_name": nome_cliente,
                    "extracted_info": extracted_info
                }
            )
            
        except Exception as e:
            logger.error(f"[SmartReception] Erro: {e}", exc_info=True)
            nome = session.conversation_context.get("cliente", {}).get("nome", "").split()[0]
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=self._get_contextual_fallback(message.body or "", nome),
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id,
                metadata={"error": str(e)}
            )
    
    def _create_natural_info_request(self, missing_info: str, context: Dict[str, Any]) -> str:
        """Cria pedido natural de informação baseado no contexto, priorizando empresa e CNPJ"""
        cliente_nome = context.get("cliente", {}).get("nome", "").split()[0]
        empresa = context.get("cliente", {}).get("empresa", "")
        cnpj = context.get("cliente", {}).get("cnpj", "")
        requests = {
            "nome da empresa": [
                "Oi! Para começarmos, qual o nome da sua empresa?",
                "Qual o nome da empresa, por favor?",
                "Me diz o nome da empresa para eu te ajudar melhor."
            ],
            "CNPJ": [
                f"Legal! Agora, qual o CNPJ da empresa?",
                f"E qual o CNPJ da empresa {empresa if empresa else ''}?",
                "Me passa o CNPJ da empresa, por favor."
            ],
            "nome completo": [
                "Agora preciso do seu nome. Como você se chama?",
                "Qual é o seu nome?",
                "Me diz seu nome, por favor."
            ],
            "email de contato": [
                f"Ótimo{', ' + cliente_nome if cliente_nome else ''}! Se precisar te enviar algo, qual email posso usar?",
                "Caso eu precise enviar relatórios ou documentos, qual seu melhor email?",
                f"Ah{', ' + cliente_nome if cliente_nome else ''}, qual email você prefere para contato?",
            ]
        }
        # Decide qual pedir
        if not empresa:
            return random.choice(requests["nome da empresa"])
        if not cnpj:
            return random.choice(requests["CNPJ"])
        if missing_info == "nome completo":
            return random.choice(requests["nome completo"])
        if missing_info == "email de contato":
            return random.choice(requests["email de contato"])
        return "Pode me informar: " + missing_info
    
    def _get_contextual_fallback(self, user_message: str, client_name: str = "") -> str:
        """Retorna resposta de fallback contextual"""
        message_lower = user_message.lower()
        
        # Adiciona o nome se disponível
        name_prefix = f"{client_name}, " if client_name else ""
        
        if any(word in message_lower for word in ["serviço", "serviços", "o que você faz"]):
            return random.choice([
                f"{name_prefix}eu faço várias coisas legais! Consigo puxar relatórios e dados da empresa, ajudo quando algo dá problema no sistema, organizo reuniões e agenda... É tipo um canivete suíço digital! 😄 O que você precisa?",
                f"Boa pergunta{', ' + client_name if client_name else ''}! Eu ajudo com um monte de coisa: dados e relatórios da empresa, problemas técnicos, agendamentos... Basicamente tô aqui pra facilitar seu trabalho! O que você tá precisando hoje?",
            ])
        else:
            return random.choice([
                f"Opa{', ' + client_name if client_name else ''}, acho que tive uma travadinha aqui! 😅 Pode repetir? Prometo prestar atenção dessa vez!",
                f"Eita{', ' + client_name if client_name else ''}, me perdi! Pode falar de novo? Às vezes eu me confundo mesmo! 🤭",
            ])
    
    def get_priority(self) -> int:
        return 10  # Alta prioridade para recepção