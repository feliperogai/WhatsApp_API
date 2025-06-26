#!/bin/bash

echo "🔧 CORREÇÃO FINAL - Windows"
echo "=========================="

# 1. Corrige o erro de roteamento no orchestrator
echo "1. Corrigindo erro de roteamento..."
docker exec jarvis-whatsapp-llm python -c "
import re

# Lê o orchestrator
with open('/app/app/core/langgraph_orchestrator.py', 'r') as f:
    content = f.read()

# Corrige o mapeamento de rotas
old_routing = '''routing_map = {
            \"reception\": \"reception\",
            \"classification\": \"classification\",
            \"data\": \"data_analysis\", 
            \"support\": \"technical_support\"
        }'''

new_routing = '''routing_map = {
            \"reception\": \"reception\",
            \"classification\": \"classification\",
            \"data\": \"data_analysis\", 
            \"support\": \"technical_support\",
            \"technical_support\": \"technical_support\",
            \"data_analysis\": \"data_analysis\",
            \"data_query\": \"data_analysis\",
            \"general_chat\": \"reception\"
        }'''

content = content.replace(old_routing, new_routing)

# Adiciona tratamento de erro no roteamento
if '_route_to_agent' in content and 'try:' not in content.split('_route_to_agent')[1].split('def')[0]:
    content = re.sub(
        r'(def _route_to_agent\(self, state: ConversationState\) -> str:)',
        r'\1\n        try:',
        content
    )
    content = re.sub(
        r'(return routing_map\.get\(routing, \"reception\"\))',
        r'    \1\n        except Exception as e:\n            logger.error(f\"Routing error: {e}\")\n            return \"reception\"',
        content
    )

# Salva
with open('/app/app/core/langgraph_orchestrator.py', 'w') as f:
    f.write(content)

print('✅ Orchestrator corrigido!')
"

# 2. Cria agente proativo que funciona
echo -e "\n2. Criando agente proativo funcional..."
docker exec jarvis-whatsapp-llm bash -c 'cat > /app/app/agents/llm_proactive_reception_agent.py << '\''EOF'\''
import logging
from typing import List, Dict, Any
from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class LLMProactiveReceptionAgent(LLMBaseAgent):
    def __init__(self, llm_service: LLMService):
        super().__init__(
            agent_id="reception_agent",
            name="Alex",
            description="Reception Agent",
            llm_service=llm_service
        )
        
    def _get_system_prompt(self) -> str:
        return "Você é o Alex, assistente amigável"
    
    def _get_tools(self) -> List:
        return []
    
    def _is_intent_compatible(self, intent: str) -> bool:
        return True
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        try:
            # Garante que existe contexto de cliente
            if "cliente" not in session.conversation_context:
                session.conversation_context["cliente"] = {}
            
            cliente = session.conversation_context["cliente"]
            nome = cliente.get("nome", "")
            empresa = cliente.get("empresa", "")
            
            # Contador de mensagens
            msg_count = len(session.message_history)
            user_msg = (message.body or "").strip()
            
            logger.info(f"[Proactive] Estado: nome={nome}, empresa={empresa}, msg={user_msg}")
            
            # FLUXO PRINCIPAL
            
            # 1. Primeira interação - pede nome
            if not nome and msg_count <= 2:
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text="Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?",
                    confidence=0.9,
                    should_continue=True,
                    next_agent=self.agent_id
                )
            
            # 2. Recebeu possível nome
            if not nome and user_msg:
                # Verifica se não é saudação
                saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]
                if user_msg.lower() not in saudacoes and len(user_msg.split()) <= 4:
                    nome = user_msg.title()
                    session.conversation_context["cliente"]["nome"] = nome
                    logger.info(f"[Proactive] Nome coletado: {nome}")
                    
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text=f"Legal, {nome.split()[0]}! Prazer em te conhecer! 😊 De qual empresa você é?",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id
                    )
            
            # 3. Tem nome mas não empresa
            if nome and not empresa:
                if user_msg and len(user_msg.split()) <= 5:
                    empresa = user_msg.title()
                    session.conversation_context["cliente"]["empresa"] = empresa
                    logger.info(f"[Proactive] Empresa coletada: {empresa}")
                    
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text=f"Perfeito, {nome.split()[0]}! A {empresa} é nossa parceira! 🎯 Como posso te ajudar hoje? Precisa de relatórios, suporte técnico ou quer marcar algo?",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id
                    )
                else:
                    # Ainda esperando empresa
                    return AgentResponse(
                        agent_id=self.agent_id,
                        response_text=f"{nome.split()[0]}, qual é o nome da sua empresa?",
                        confidence=0.9,
                        should_continue=True,
                        next_agent=self.agent_id
                    )
            
            # 4. Tem tudo - processa normalmente
            if nome:
                primeiro_nome = nome.split()[0]
                
                # Usa LLM com contexto
                try:
                    prompt_personalizado = f"Cliente: {primeiro_nome} da {empresa}\nMensagem: {user_msg}"
                    response_text = await self.llm_service.generate_response(
                        prompt=prompt_personalizado,
                        system_message=f"Você é o Alex. Sempre use o nome {primeiro_nome} na resposta. Seja amigável e prestativo.",
                        session_id=session.session_id
                    )
                except:
                    # Fallback
                    if "relatório" in user_msg.lower() or "vendas" in user_msg.lower():
                        response_text = f"{primeiro_nome}, vou puxar os dados pra você! Um momento..."
                    elif "problema" in user_msg.lower() or "erro" in user_msg.lower():
                        response_text = f"Poxa {primeiro_nome}, vamos resolver isso! Me conta mais detalhes."
                    else:
                        response_text = f"{primeiro_nome}, claro! Como posso ajudar com isso?"
                
                # Determina próximo agente
                next_agent = self.agent_id
                msg_lower = user_msg.lower()
                if any(w in msg_lower for w in ["relatório", "dados", "vendas", "dashboard"]):
                    next_agent = "data_agent"
                elif any(w in msg_lower for w in ["erro", "problema", "bug", "suporte"]):
                    next_agent = "support_agent"
                
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text=response_text,
                    confidence=0.9,
                    should_continue=True,
                    next_agent=next_agent
                )
            
            # Fallback geral
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Oi! Parece que me perdi. Vamos começar de novo? Qual é o seu nome?",
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id
            )
            
        except Exception as e:
            logger.error(f"[Proactive] Erro: {e}")
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Ops, tive um probleminha! Mas vamos lá, qual é o seu nome?",
                confidence=0.7,
                should_continue=True,
                next_agent=self.agent_id
            )
EOF'

# 3. Atualiza imports
echo -e "\n3. Atualizando imports..."
docker exec jarvis-whatsapp-llm sed -i 's/from app.agents.llm_reception_agent import LLMReceptionAgent/from app.agents.llm_proactive_reception_agent import LLMProactiveReceptionAgent/g' /app/app/core/langgraph_orchestrator.py
docker exec jarvis-whatsapp-llm sed -i 's/LLMReceptionAgent(self.llm_service)/LLMProactiveReceptionAgent(self.llm_service)/g' /app/app/core/langgraph_orchestrator.py

# 4. Limpa cache
echo -e "\n4. Limpando cache Python..."
docker exec jarvis-whatsapp-llm rm -rf /app/app/__pycache__
docker exec jarvis-whatsapp-llm rm -rf /app/app/*/__pycache__
docker exec jarvis-whatsapp-llm rm -rf /app/app/*/*/__pycache__

# 5. Reinicia
echo -e "\n5. Reiniciando serviço..."
docker restart jarvis-whatsapp-llm

echo ""
echo "⏰ Aguardando 30 segundos para inicializar..."
for i in {30..1}; do
    echo -ne "\r$i segundos... "
    sleep 1
done
echo -e "\r✅ Pronto!      "

# 6. Teste
echo -e "\n6. Testando sistema..."
response=$(curl -s -X POST "http://localhost:8000/webhook/whatsapp" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "From=whatsapp:+5511999999999" \
    -d "Body=oi" \
    -d "MessageSid=test_final" 2>/dev/null || echo "ERRO")

if [[ "$response" != "ERRO" ]]; then
    message=$(echo "$response" | grep -oP '(?<=<Message>).*?(?=</Message>)' || echo "")
    if [[ "$message" == *"nome"* ]]; then
        echo "✅ SUCESSO! Sistema funcionando!"
        echo "   Resposta: $message"
    else
        echo "⚠️ Sistema respondeu mas não pediu nome"
        echo "   Resposta: $message"
    fi
else
    echo "❌ Erro ao conectar"
fi

echo ""
echo "🎯 TESTE COMPLETO NO WHATSAPP:"
echo "1. Envie: oi"
echo "2. Envie: felipe"
echo "3. Envie: tech solutions"
echo ""
echo "✨ Agora DEVE funcionar perfeitamente!"