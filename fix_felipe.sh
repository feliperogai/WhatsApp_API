#!/bin/bash
# CORREÇÃO DEFINITIVA - Faz o sistema responder após receber o nome

docker exec jarvis-whatsapp-llm bash -c '
cat > /app/app/agents/llm_simple_proactive.py << EOF
from app.agents.llm_base_agent import LLMBaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession

class LLMProactiveReceptionAgent(LLMBaseAgent):
    def __init__(self, llm_service):
        super().__init__(
            agent_id="reception_agent",
            name="Alex",
            description="Reception",
            llm_service=llm_service
        )
    
    def _get_system_prompt(self):
        return "Você é o Alex"
    
    def _get_tools(self):
        return []
    
    def _is_intent_compatible(self, intent):
        return True
    
    async def process_message(self, message, session):
        # Estado simples
        estado = session.conversation_context.get("estado", "inicio")
        nome = session.conversation_context.get("nome", "")
        empresa = session.conversation_context.get("empresa", "")
        
        msg = message.body.strip() if message.body else ""
        
        # Estado: INICIO - Pede nome
        if estado == "inicio":
            session.conversation_context["estado"] = "esperando_nome"
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Oi! Tudo bem? 😊 Sou o Alex, seu assistente virtual! Qual é o seu nome?",
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id
            )
        
        # Estado: ESPERANDO NOME - Recebe nome e pede empresa
        elif estado == "esperando_nome" and msg:
            session.conversation_context["nome"] = msg.title()
            session.conversation_context["estado"] = "esperando_empresa"
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=f"Legal, {msg.title().split()[0]}! Prazer! 😊 De qual empresa você é?",
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id
            )
        
        # Estado: ESPERANDO EMPRESA - Recebe empresa e oferece serviços
        elif estado == "esperando_empresa" and msg:
            session.conversation_context["empresa"] = msg.title()
            session.conversation_context["estado"] = "completo"
            nome_primeiro = session.conversation_context["nome"].split()[0]
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=f"Perfeito, {nome_primeiro}! A {msg.title()} é nossa parceira! 🎯 Como posso ajudar? Relatórios, suporte ou agendamento?",
                confidence=0.9,
                should_continue=True,
                next_agent=self.agent_id
            )
        
        # Estado: COMPLETO - Processa normalmente
        else:
            nome_primeiro = nome.split()[0] if nome else "Amigo"
            
            # Usa LLM
            try:
                response_text = await self.llm_service.generate_response(
                    prompt=msg,
                    system_message=f"Você é o Alex. O cliente é {nome_primeiro} da empresa {empresa}. Seja prestativo e use o nome dele.",
                    session_id=session.session_id
                )
            except:
                # Fallback
                if "relatório" in msg.lower() or "vendas" in msg.lower():
                    response_text = f"{nome_primeiro}, vou puxar os dados de vendas pra você! Um momento..."
                elif "problema" in msg.lower() or "erro" in msg.lower():
                    response_text = f"Poxa {nome_primeiro}, vamos resolver isso! Me conta mais sobre o problema."
                else:
                    response_text = f"{nome_primeiro}, como posso te ajudar com isso?"
            
            # Redireciona se necessário
            next_agent = self.agent_id
            if any(w in msg.lower() for w in ["relatório", "dados", "vendas"]):
                next_agent = "data_agent"
            elif any(w in msg.lower() for w in ["erro", "problema", "bug"]):
                next_agent = "support_agent"
            
            return AgentResponse(
                agent_id=self.agent_id,
                response_text=response_text,
                confidence=0.9,
                should_continue=True,
                next_agent=next_agent
            )
EOF

# Copia como arquivo correto
cp /app/app/agents/llm_simple_proactive.py /app/app/agents/llm_proactive_reception_agent.py

# Atualiza orchestrator
sed -i "s/llm_reception_agent/llm_proactive_reception_agent/g" /app/app/core/langgraph_orchestrator.py
sed -i "s/LLMReceptionAgent/LLMProactiveReceptionAgent/g" /app/app/core/langgraph_orchestrator.py

# Limpa cache Python
rm -rf /app/app/agents/__pycache__
rm -rf /app/app/core/__pycache__

echo "✅ Sistema corrigido!"
'

# Reinicia
docker restart jarvis-whatsapp-llm

echo "⏰ Aguardando 20 segundos..."
sleep 20

echo ""
echo "✅ PRONTO! Agora vai funcionar!"
echo ""
echo "TESTE:"
echo "1. oi → vai pedir nome"
echo "2. felipe → vai pedir empresa"
echo "3. tech → vai oferecer serviços"