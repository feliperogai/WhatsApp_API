agent_2_py = ""
from app.agents.base_agent import BaseAgent
from app.models.message import WhatsAppMessage, AgentResponse
from app.models.session import UserSession
import re
from typing import Dict, List

class ClassificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="classification_agent",
            name="Agente de Classificação IA",
            description="Agente de IA para classificação inteligente de intenções"
        )
        
        self.intent_patterns = {
            "data_query": [
                r"\b(relatório|dashboard|vendas|receita|dados|métricas|kpi)\b",
                r"\b(quanto|quantos|qual.*total|performance)\b",
                r"\b(análise|analítico|estatística)\b"
            ],
            "technical_support": [
                r"\b(erro|problema|bug|não funciona|falha)\b",
                r"\b(ajuda|suporte|assistência)\b",
                r"\b(configurar|instalar|setup)\b"
            ],
            "scheduling": [
                r"\b(agendar|reunião|encontro|compromisso)\b",
                r"\b(calendário|agenda|horário)\b",
                r"\b(marcar|remarcar|cancelar)\b"
            ],
            "general_chat": [
                r"\b(como vai|tudo bem|conversar)\b",
                r"\b(obrigado|obrigada|valeu)\b"
            ]
        }
    
    async def can_handle(self, message: WhatsAppMessage, session: UserSession) -> bool:
        return session.current_agent == self.agent_id
    
    def classify_intent(self, text: str) -> Dict[str, float]:
        """Classifica a intenção usando patterns regex (pode ser substituído por ML)"""
        scores = {}
        text_lower = text.lower()
        
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 0.3
            scores[intent] = min(score, 1.0)
        
        return scores
    
    async def process_message(self, message: WhatsAppMessage, session: UserSession) -> AgentResponse:
        if not message.body:
            return AgentResponse(
                agent_id=self.agent_id,
                response_text="Desculpe, não consegui processar sua mensagem. Pode tentar novamente?",
                confidence=0.1,
                next_agent="reception_agent"
            )
        
        # Classificação de intenção
        intent_scores = self.classify_intent(message.body)
        best_intent = max(intent_scores.items(), key=lambda x: x[1]) if intent_scores else ("general_chat", 0.0)
        
        intent, confidence = best_intent
        
        # Roteamento baseado na intenção
        if intent == "data_query" and confidence > 0.5:
            response_text = "🔍 Identifiquei que você precisa de dados ou relatórios. Vou conectar com nosso analista de dados!"
            next_agent = "data_agent"
        elif intent == "technical_support" and confidence > 0.5:
            response_text = "🔧 Identifiquei um problema técnico. Conectando com o suporte especializado!"
            next_agent = "support_agent"
        elif intent == "scheduling" and confidence > 0.5:
            response_text = "📅 Vou te ajudar com agendamentos!"
            next_agent = "scheduling_agent"
        else:
            # IA mais avançada poderia ser implementada aqui
            response_text = f'''🤔 Analisando sua mensagem: "{message.body[:50]}..."

Baseado no contexto, posso te conectar com:
1️⃣ Dados e Relatórios
2️⃣ Suporte Técnico  
3️⃣ Agendamentos
4️⃣ Conversa Geral

Digite o número da opção ou me explique melhor o que precisa.'''
            next_agent = self.agent_id  # Continua neste agente
            confidence = 0.6
        
        # Salva classificação no contexto
        session.update_context("last_intent", intent)
        session.update_context("intent_confidence", confidence)
        
        return AgentResponse(
            agent_id=self.agent_id,
            response_text=response_text,
            confidence=confidence,
            should_continue=True,
            next_agent=next_agent,
            metadata={"classified_intent": intent, "all_scores": intent_scores}
        )
    
    def get_priority(self) -> int:
        return 8
