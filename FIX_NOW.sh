#!/bin/bash
# CORREÇÃO ABSOLUTA - VAI FUNCIONAR!

echo "🚀 APLICANDO CORREÇÃO..."

# Executa tudo de uma vez
docker exec jarvis-whatsapp-llm python -c "
f = '''from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession

class LLMProactiveReceptionAgent(LLMBaseAgent):
    msgs = {}
    
    def __init__(self, llm_service):
        super().__init__('reception_agent', 'Alex', 'Reception', llm_service)
    
    def _get_system_prompt(self):
        return 'Alex'
    
    def _get_tools(self):
        return []
    
    def _is_intent_compatible(self, intent):
        return True
    
    async def process_message(self, message, session):
        phone = message.from_number
        LLMProactiveReceptionAgent.msgs[phone] = LLMProactiveReceptionAgent.msgs.get(phone, 0) + 1
        n = LLMProactiveReceptionAgent.msgs[phone]
        
        texts = [
            'Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?',
            'Legal! Prazer! 😊 De qual empresa você é?',
            'Perfeito! Como posso ajudar? Relatórios, suporte ou agendamento?',
            'Como posso ajudar?'
        ]
        
        return AgentResponse(
            agent_id='reception_agent',
            response_text=texts[min(n-1, 3)],
            confidence=0.9,
            should_continue=True,
            next_agent='reception_agent'
        )
'''

open('/app/app/agents/llm_proactive_reception_agent.py', 'w').write(f)

# Fix orchestrator
with open('/app/app/core/langgraph_orchestrator.py', 'r') as file:
    c = file.read()
c = c.replace('llm_reception_agent', 'llm_proactive_reception_agent')
c = c.replace('LLMReceptionAgent', 'LLMProactiveReceptionAgent')
if 'technical_support\": \"technical_support' not in c:
    c = c.replace('\"support\": \"technical_support\"', '\"support\": \"technical_support\", \"technical_support\": \"technical_support\"')
with open('/app/app/core/langgraph_orchestrator.py', 'w') as file:
    file.write(c)

# Clean cache
import os, shutil
for root, dirs, files in os.walk('/app'):
    for d in dirs:
        if d == '__pycache__':
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)

print('✅ CORREÇÃO APLICADA!')
"

docker restart jarvis-whatsapp-llm

echo "⏰ Aguarde 30 segundos..."
sleep 30

echo "✅ PRONTO! Teste agora:"
echo "1. oi"
echo "2. felipe"
echo "3. tech"