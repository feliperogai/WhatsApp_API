import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        # Configuração fixa para seu setup
        self.ollama_url = "http://192.168.15.31:11435"
        self.model = "llama3.1:8b"
        self.session = None
        self.memories = {}  # Store conversation memories per session
        
    async def initialize(self):
        """Inicializa conexão LLM"""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        
        try:
            # Testa conexão com a configuração exata
            await self._test_ollama_connection()
            logger.info(f"✅ Ollama conectado: {self.ollama_url} - Modelo: {self.model}")
            
        except Exception as e:
            logger.error(f"❌ Erro conectando Ollama: {e}")
            raise
    
    async def _test_ollama_connection(self):
        """Testa conexão com Ollama usando configuração exata"""
        url = f"{self.ollama_url}/api/chat"
        test_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "teste"}]
        }
        
        async with self.session.post(url, json=test_payload) as response:
            if response.status != 200:
                raise Exception(f"Ollama connection failed: {response.status}")
            result = await response.json()
            if "message" not in result:
                raise Exception("Invalid response format from Ollama")
    
    def get_memory(self, session_id: str) -> List[Dict]:
        """Obtém ou cria memória para sessão"""
        if session_id not in self.memories:
            self.memories[session_id] = []
        return self.memories[session_id]
    
    async def generate_response(
        self, 
        prompt: str, 
        system_message: str = None,
        session_id: str = None,
        context: Dict[str, Any] = None
    ) -> str:
        """Gera resposta usando Ollama com sua configuração"""
        
        try:
            messages = []
            
            # Adiciona mensagem do sistema
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # Adiciona contexto da sessão (últimas 5 mensagens)
            if session_id and session_id in self.memories:
                memory = self.memories[session_id]
                for msg in memory[-5:]:  # Últimas 5 mensagens
                    messages.append(msg)
            
            # Adiciona contexto adicional
            if context:
                context_str = f"Contexto: {json.dumps(context, indent=2, ensure_ascii=False)}"
                messages.append({"role": "system", "content": context_str})
            
            # Adiciona prompt atual
            messages.append({"role": "user", "content": prompt})
            
            # Chama Ollama com configuração exata
            url = f"{self.ollama_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                
                result = await response.json()
                content = result["message"]["content"]
                
                # Salva na memória
                if session_id:
                    memory = self.get_memory(session_id)
                    memory.append({"role": "user", "content": prompt})
                    memory.append({"role": "assistant", "content": content})
                    
                    # Mantém apenas últimas 10 mensagens por sessão
                    if len(memory) > 10:
                        self.memories[session_id] = memory[-10:]
                
                return content.strip()
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Desculpe, estou com dificuldades técnicas no momento. Tente novamente em alguns instantes."
    
    async def classify_intent(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Classifica intenção da mensagem"""
        
        system_prompt = """Você é um classificador de intenções para um assistente virtual.

Analise a mensagem do usuário e classifique em uma das categorias:

1. **reception** - Saudações, apresentações, início de conversa
2. **data_query** - Consultas de dados, relatórios, dashboards, KPIs
3. **technical_support** - Problemas técnicos, erros, bugs, suporte
4. **scheduling** - Agendamentos, reuniões, calendário
5. **general_chat** - Conversa geral, agradecimentos, despedidas

Responda APENAS em formato JSON simples:
{"intent": "categoria", "confidence": 0.95, "reasoning": "explicação breve"}"""

        try:
            response = await self.generate_response(
                f"Classifique esta mensagem: '{message}'",
                system_prompt,
                session_id
            )
            
            # Extrai JSON da resposta
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = response[start:end]
                return json.loads(json_str)
                
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
        
        # Fallback
        return {
            "intent": "general_chat",
            "confidence": 0.1,
            "reasoning": "Classificação automática falhou"
        }
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Status do serviço LLM"""
        status = {
            "ollama_url": self.ollama_url,
            "model": self.model,
            "status": "offline",
            "active_sessions": len(self.memories),
            "total_requests": 0
        }
        
        # Testa Ollama
        try:
            await self._test_ollama_connection()
            status["status"] = "online"
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    async def cleanup(self):
        """Limpa recursos"""
        if self.session:
            await self.session.close()
        
        # Limpa memórias antigas
        self.memories.clear()
        
    def reset_session_memory(self, session_id: str):
        """Reseta memória de uma sessão específica"""
        if session_id in self.memories:
            del self.memories[session_id]
            logger.info(f"Memory reset for session: {session_id}")