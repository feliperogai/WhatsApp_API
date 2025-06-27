from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import traceback

# Importações do sistema
from app.services.llm_service import LLMService
from app.services.twilio_service import TwilioService
from app.core.session_manager import SessionManager
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.models.message import WhatsAppMessage

load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Instâncias globais
llm_service: Optional[LLMService] = None
twilio_service: Optional[TwilioService] = None
session_manager: Optional[SessionManager] = None
orchestrator: Optional[LangGraphOrchestrator] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    global llm_service, twilio_service, session_manager, orchestrator
    
    logger.info("🚀 Iniciando Jarvis WhatsApp LLM Agent Orchestrator...")
    
    try:
        # Inicializa serviços
        logger.info("📡 Inicializando serviços...")
        
        # LLM Service
        llm_service = LLMService()
        await llm_service.initialize()
        
        # Twilio Service
        twilio_service = TwilioService()
        
        # Session Manager
        session_manager = SessionManager()
        await session_manager.initialize()
        
        # Orchestrator
        orchestrator = LangGraphOrchestrator(session_manager, llm_service)
        
        logger.info("✅ Todos os serviços inicializados com sucesso!")
        
        # Testa conexão
        status = await orchestrator.get_workflow_status()
        logger.info(f"📊 Status do sistema: {status}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar serviços: {e}")
        logger.error(traceback.format_exc())
    
    yield
    
    # Cleanup
    logger.info("🛑 Encerrando Jarvis WhatsApp...")
    if llm_service:
        await llm_service.cleanup()

app = FastAPI(
    title="Jarvis WhatsApp LLM Agent Orchestrator",
    description="Sistema inteligente de agentes com coleta ordenada de dados",
    version="2.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Dashboard com status do sistema"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jarvis WhatsApp - Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #1a1a1a;
                color: #ffffff;
                margin: 0;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .container {
                background-color: #2d2d2d;
                border-radius: 10px;
                padding: 40px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                max-width: 800px;
                width: 100%;
            }
            h1 {
                color: #4CAF50;
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            .subtitle {
                text-align: center;
                color: #888;
                margin-bottom: 30px;
            }
            .status {
                background-color: #3d3d3d;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .status-item {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #555;
            }
            .status-item:last-child {
                border-bottom: none;
            }
            .status-label {
                color: #aaa;
            }
            .status-value {
                font-weight: bold;
            }
            .online { color: #4CAF50; }
            .offline { color: #f44336; }
            .feature {
                background-color: #3d3d3d;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #4CAF50;
            }
            .agents {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin-top: 20px;
            }
            .agent-card {
                background-color: #3d3d3d;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
            }
            .agent-icon {
                font-size: 2em;
                margin-bottom: 10px;
            }
            .flow {
                background-color: #3d3d3d;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
                text-align: center;
            }
            .flow-step {
                display: inline-block;
                margin: 0 10px;
                padding: 10px 20px;
                background-color: #4CAF50;
                border-radius: 20px;
                color: white;
            }
            .arrow {
                display: inline-block;
                margin: 0 5px;
                color: #4CAF50;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Jarvis WhatsApp</h1>
            <p class="subtitle">Sistema Inteligente de Agentes com LLM</p>
            
            <div class="status">
                <h2>📊 Status do Sistema</h2>
                <div class="status-item">
                    <span class="status-label">LLM Service:</span>
                    <span class="status-value online">✅ Online</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Twilio:</span>
                    <span class="status-value online">✅ Configurado</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Orchestrator:</span>
                    <span class="status-value online">✅ Ativo</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Sessões Ativas:</span>
                    <span class="status-value">0</span>
                </div>
            </div>
            
            <h2>🎯 Agentes Disponíveis</h2>
            <div class="agents">
                <div class="agent-card">
                    <div class="agent-icon">👋</div>
                    <h3>Reception Agent</h3>
                    <p>Recebe usuários e direciona</p>
                </div>
                <div class="agent-card">
                    <div class="agent-icon">📊</div>
                    <h3>Data Agent</h3>
                    <p>Coleta dados e gera relatórios</p>
                </div>
                <div class="agent-card">
                    <div class="agent-icon">🔧</div>
                    <h3>Support Agent</h3>
                    <p>Suporte técnico inteligente</p>
                </div>
                <div class="agent-card">
                    <div class="agent-icon">🧠</div>
                    <h3>Classification Agent</h3>
                    <p>Classifica intenções</p>
                </div>
            </div>
            
            <div class="flow">
                <h2>📋 Fluxo de Coleta de Dados</h2>
                <div style="margin-top: 20px;">
                    <span class="flow-step">CNPJ</span>
                    <span class="arrow">→</span>
                    <span class="flow-step">Empresa</span>
                    <span class="arrow">→</span>
                    <span class="flow-step">Nome</span>
                    <span class="arrow">→</span>
                    <span class="flow-step">Email</span>
                    <span class="arrow">→</span>
                    <span class="flow-step">Cargo</span>
                </div>
                <p style="margin-top: 20px; color: #888;">
                    O sistema coleta dados nesta ordem exata. Não é possível pular etapas.
                </p>
            </div>
            
            <div class="feature">
                <h3>✨ Recursos Principais</h3>
                <ul>
                    <li>🤖 LLM integrado (Ollama/OpenAI)</li>
                    <li>🔄 Orquestração inteligente com LangGraph</li>
                    <li>📱 Integração WhatsApp via Twilio</li>
                    <li>💾 Persistência de sessões</li>
                    <li>🔐 Validação completa de CNPJ</li>
                    <li>📊 Relatórios dinâmicos</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    """Webhook principal do Twilio para WhatsApp"""
    try:
        # Parse form data do Twilio
        form_data = await request.form()
        
        # Extrai dados da mensagem
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        
        # Extrai número limpo
        if from_number.startswith("whatsapp:"):
            from_number = from_number[9:]
        
        logger.info(f"📱 Mensagem recebida de {from_number}: {body}")
        
        # Cria mensagem
        message = WhatsAppMessage(
            message_id=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body
        )
        
        # Processa através do orchestrator
        if orchestrator:
            response = await orchestrator.process_message(message)
            
            # Cria resposta TwiML
            twiml_response = twilio_service.create_webhook_response(response.response_text)
            
            logger.info(f"✅ Resposta enviada: {response.response_text[:100]}...")
            
            return Response(
                content=twiml_response,
                media_type="application/xml"
            )
        else:
            logger.error("❌ Orchestrator não inicializado")
            fallback_response = twilio_service.create_webhook_response(
                "Desculpe, estou temporariamente indisponível. Tente novamente em alguns segundos."
            )
            return Response(
                content=fallback_response,
                media_type="application/xml"
            )
            
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        logger.error(traceback.format_exc())
        
        error_response = twilio_service.create_webhook_response(
            "Ops! Ocorreu um erro. Por favor, tente novamente."
        )
        return Response(
            content=error_response,
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "llm": llm_service is not None and llm_service.is_initialized,
                "twilio": twilio_service is not None and twilio_service.is_configured,
                "orchestrator": orchestrator is not None,
                "session_manager": session_manager is not None
            }
        }
        
        # Verifica se todos os serviços estão ok
        all_healthy = all(status["services"].values())
        
        if not all_healthy:
            status["status"] = "degraded"
            
        return status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/status")
async def get_status():
    """Status detalhado do sistema"""
    try:
        status = {
            "system": "online",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0"
        }
        
        # Status do LLM
        if llm_service:
            status["llm"] = await llm_service.get_service_status()
        
        # Status do Orchestrator
        if orchestrator:
            status["orchestrator"] = await orchestrator.get_workflow_status()
        
        # Status das sessões
        if session_manager:
            status["sessions"] = {
                "active_count": await session_manager.get_active_sessions_count()
            }
        
        # Status do Twilio
        if twilio_service:
            status["twilio"] = twilio_service.get_service_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return {
            "system": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/test/message")
async def test_message(
    phone: str = Form(...),
    message: str = Form(...)
):
    """Endpoint de teste para simular mensagens"""
    try:
        # Cria mensagem de teste
        test_message = WhatsAppMessage(
            message_id=f"test_{datetime.now().timestamp()}",
            from_number=phone,
            to_number="system",
            body=message
        )
        
        # Processa
        if orchestrator:
            response = await orchestrator.process_message(test_message)
            
            return {
                "success": True,
                "response": response.response_text,
                "agent": response.agent_id,
                "metadata": response.metadata
            }
        else:
            return {
                "success": False,
                "error": "Orchestrator não inicializado"
            }
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/sessions/{phone}")
async def get_session(phone: str):
    """Obtém dados da sessão de um usuário"""
    try:
        if session_manager:
            session = await session_manager.get_session(phone)
            
            if session:
                return {
                    "exists": True,
                    "session_id": session.session_id,
                    "current_agent": session.current_agent,
                    "context": session.conversation_context,
                    "message_count": len(session.message_history),
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat()
                }
            else:
                return {
                    "exists": False,
                    "phone": phone
                }
        else:
            return {
                "error": "Session manager não inicializado"
            }
            
    except Exception as e:
        logger.error(f"Session error: {e}")
        return {
            "error": str(e)
        }

@app.delete("/sessions/{phone}")
async def delete_session(phone: str):
    """Deleta sessão de um usuário"""
    try:
        if session_manager:
            await session_manager.delete_session(phone)
            return {
                "success": True,
                "message": f"Sessão de {phone} deletada"
            }
        else:
            return {
                "success": False,
                "error": "Session manager não inicializado"
            }
            
    except Exception as e:
        logger.error(f"Delete session error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/llm/status")
async def llm_status():
    """Status específico do LLM"""
    try:
        if llm_service:
            return await llm_service.get_service_status()
        else:
            return {"error": "LLM service não inicializado"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/llm/test")
async def test_llm(prompt: str = Query(...)):
    """Testa o LLM diretamente"""
    try:
        if llm_service:
            response = await llm_service.generate_response(
                prompt=prompt,
                system_message="Você é um assistente útil. Responda de forma breve."
            )
            
            return {
                "success": True,
                "prompt": prompt,
                "response": response
            }
        else:
            return {
                "success": False,
                "error": "LLM service não inicializado"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Endpoint específico para testar a coleta ordenada
@app.get("/test/data-collection-flow")
async def test_data_collection():
    """Mostra o fluxo de coleta de dados"""
    return {
        "collection_order": [
            {"step": 1, "field": "CNPJ", "validation": "Formato XX.XXX.XXX/XXXX-XX com dígitos verificadores válidos"},
            {"step": 2, "field": "Empresa", "validation": "Nome com pelo menos 3 caracteres"},
            {"step": 3, "field": "Nome", "validation": "Nome completo (nome e sobrenome)"},
            {"step": 4, "field": "Email", "validation": "Formato válido de email"},
            {"step": 5, "field": "Cargo", "validation": "Cargo com pelo menos 3 caracteres"}
        ],
        "rules": [
            "Não é possível pular etapas",
            "CNPJ é validado com algoritmo completo",
            "Só mostra dados após coletar todos os campos",
            "Se tentar burlar a ordem, o sistema insiste no campo correto"
        ],
        "example_flow": {
            "user": "Quero ver relatório",
            "bot": "📋 Antes de mostrar os dados, preciso do CNPJ da empresa. Pode informar?",
            "user": "Meu nome é João",
            "bot": "Entendi seu nome, mas primeiro preciso do CNPJ da empresa para liberar o acesso. Qual é o CNPJ?"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)