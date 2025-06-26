#!/bin/bash

echo "⚡ CORREÇÃO INSTANTÂNEA - 30 SEGUNDOS!"
echo "====================================="

# Comando único que faz tudo
docker exec jarvis-whatsapp-llm python -c "
# Cria arquivo inline
code = '''
from app.agents.llm_reception_agent import LLMReceptionAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession

class LLMProactiveReceptionAgent(LLMReceptionAgent):
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        if \"cliente\" not in session.conversation_context:
            session.conversation_context[\"cliente\"] = {}
        
        cliente = session.conversation_context[\"cliente\"]
        nome = cliente.get(\"nome\", \"\")
        empresa = cliente.get(\"empresa\", \"\")
        msg = (message.body or \"\").strip()
        msg_count = len(session.message_history)
        
        # Sem nome? Pede nome
        if not nome and msg_count <= 2:
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=\"Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?\",
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id
            )
        
        # Recebeu nome? Salva e pede empresa
        if not nome and msg and len(msg.split()) <= 3 and msg.lower() not in [\"oi\", \"olá\", \"ola\"]:
            session.conversation_context[\"cliente\"][\"nome\"] = msg.title()
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=f\"Legal, {msg.title().split()[0]}! Prazer! 😊 De qual empresa você é?\",
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id
            )
        
        # Tem nome mas não empresa? Pede empresa
        if nome and not empresa and msg_count <= 6:
            if msg and len(msg.split()) <= 5:
                session.conversation_context[\"cliente\"][\"empresa\"] = msg.title()
                return AgentResponse(
                    agent_id=self.agent_id,
                    response_text=f\"Perfeito, {nome.split()[0]}! A {msg.title()} é nossa parceira! Como posso ajudar? Relatórios, suporte ou agendamento?\",
                    confidence=0.9,
                    should_continue=True,
                    next_agent=self.agent_id
                )
        
        # Processa normal
        return await super().process_message(message, session)
'''

# Salva arquivo
with open('/app/app/agents/llm_proactive_reception_agent.py', 'w') as f:
    f.write(code)

# Atualiza orchestrator
with open('/app/app/core/langgraph_orchestrator.py', 'r') as f:
    content = f.read()

content = content.replace(
    'from app.agents.llm_reception_agent import LLMReceptionAgent',
    'from app.agents.llm_proactive_reception_agent import LLMProactiveReceptionAgent'
)
content = content.replace(
    'LLMReceptionAgent(self.llm_service)',
    'LLMProactiveReceptionAgent(self.llm_service)'
)

with open('/app/app/core/langgraph_orchestrator.py', 'w') as f:
    f.write(content)

print('✅ Arquivos atualizados!')
"

# Reinicia
docker restart jarvis-whatsapp-llm

echo "⏰ Aguardando reinicialização..."
sleep 25

echo ""
echo "✅ SISTEMA PRONTO!"
echo ""
echo "TESTE AGORA:"
echo "👤 Você: oi"
echo "🤖 Alex: [vai pedir nome]"
echo "👤 Você: felipe" 
echo "🤖 Alex: [vai agradecer e pedir empresa]"
echo "👤 Você: tech solutions"
echo "🤖 Alex: [vai oferecer serviços]"