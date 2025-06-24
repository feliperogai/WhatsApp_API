from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import logging
import redis.asyncio as redis
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv
from datetime import datetime

from app.core.queue_manager import QueueManager, Priority
from app.core.rate_limiter import AdaptiveRateLimiter
from app.core.llm_pool import OptimizedLLMService
from app.services.message_processor import MessageProcessor
from app.services.twilio_service import TwilioService
from app.core.session_manager import SessionManager
from app.services.llm_service import LLMService
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.models.message import WhatsAppMessage

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
app_instances = {
    "redis": None,
    "queue_manager": None,
    "rate_limiter": None,
    "llm_service": None,
    "twilio_service": None,
    "message_processor": None,
    "session_manager": None,
    "orchestrator": None
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Jarvis WhatsApp Service...")
    
    try:
        # Redis connection
        app_instances["redis"] = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=False
        )
        await app_instances["redis"].ping()
        logger.info("✅ Redis connected")
        
        # Session Manager
        app_instances["session_manager"] = SessionManager()
        await app_instances["session_manager"].initialize()
        logger.info("✅ Session Manager initialized")
        
        # Queue Manager
        app_instances["queue_manager"] = QueueManager(
            redis_client=app_instances["redis"],
            max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "1000")),
            max_workers=int(os.getenv("MAX_WORKERS", "3")),
            max_retries=int(os.getenv("MAX_RETRIES", "3"))
        )
        
        # Rate Limiter
        app_instances["rate_limiter"] = AdaptiveRateLimiter(
            redis_client=app_instances["redis"],
            global_rate=float(os.getenv("GLOBAL_RATE_LIMIT", "10"))/60,
            global_burst=int(os.getenv("GLOBAL_BURST", "5")),
            user_rate=float(os.getenv("USER_RATE_LIMIT", "3"))/60,
            user_burst=int(os.getenv("USER_BURST", "2"))
        )
        
        # LLM Service
        app_instances["llm_service"] = LLMService()
        await app_instances["llm_service"].initialize()
        logger.info("✅ LLM Service initialized")
        
        # Twilio Service
        app_instances["twilio_service"] = TwilioService()
        logger.info("✅ Twilio Service initialized")
        
        # LangGraph Orchestrator
        app_instances["orchestrator"] = LangGraphOrchestrator(
            app_instances["session_manager"],
            app_instances["llm_service"]
        )
        logger.info("✅ LangGraph Orchestrator initialized")
        
        # Message Processor
        app_instances["message_processor"] = MessageProcessor(
            orchestrator=app_instances["orchestrator"],
            twilio_service=app_instances["twilio_service"],
            rate_limiter=app_instances["rate_limiter"]
        )
        
        # Start queue workers
        await app_instances["queue_manager"].start_workers(
            app_instances["message_processor"].process_queued_message
        )
        logger.info("✅ Queue workers started")
        
        logger.info("✅ Jarvis WhatsApp Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Jarvis WhatsApp Service...")
    
    if app_instances["queue_manager"]:
        await app_instances["queue_manager"].stop_workers()
    
    if app_instances["llm_service"]:
        await app_instances["llm_service"].cleanup()
    
    if app_instances["redis"]:
        await app_instances["redis"].close()
    
    logger.info("Jarvis WhatsApp Service stopped")

app = FastAPI(
    title="Jarvis WhatsApp Service",
    description="WhatsApp AI Assistant with Queue Management and LangGraph",
    version="3.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse("""
    <html>
    <head>
        <title>Jarvis WhatsApp Service</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 800px; 
                margin: 0 auto; 
                padding: 20px;
                background: #1a1a1a;
                color: #fff;
            }
            .status { 
                background: #2a2a2a; 
                padding: 20px; 
                border-radius: 10px; 
                margin: 20px 0;
            }
            .metric {
                display: inline-block;
                margin: 10px 20px 10px 0;
            }
            .metric .value {
                font-size: 2em;
                font-weight: bold;
                color: #4CAF50;
            }
            .endpoint {
                background: #333;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
                font-family: monospace;
            }
            h1, h2 { color: #4CAF50; }
            a { color: #4CAF50; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🤖 Jarvis WhatsApp Service v3.0</h1>
        <p>AI Assistant with Queue Management and LangGraph</p>
        
        <div class="status">
            <h2>System Status</h2>
            <div id="metrics">Loading...</div>
        </div>
        
        <h2>API Endpoints</h2>
        <div class="endpoint">POST /webhook/whatsapp - WhatsApp webhook</div>
        <div class="endpoint">GET /health - Health check</div>
        <div class="endpoint">GET /metrics - System metrics</div>
        <div class="endpoint">GET /llm/status - LLM status</div>
        
        <script>
            async function updateMetrics() {
                try {
                    const response = await fetch('/metrics');
                    const data = await response.json();
                    
                    document.getElementById('metrics').innerHTML = `
                        <div class="metric">
                            <div>Queue</div>
                            <div class="value">${data.queue.pending}</div>
                        </div>
                        <div class="metric">
                            <div>Processing</div>
                            <div class="value">${data.queue.processing}</div>
                        </div>
                        <div class="metric">
                            <div>LLM Status</div>
                            <div class="value">${data.llm_status || 'N/A'}</div>
                        </div>
                        <div class="metric">
                            <div>Active Sessions</div>
                            <div class="value">${data.active_sessions || 0}</div>
                        </div>
                    `;
                } catch (e) {
                    console.error('Failed to update metrics:', e);
                }
            }
            
            updateMetrics();
            setInterval(updateMetrics, 5000);
        </script>
    </body>
    </html>
    """)

@app.post("/webhook/whatsapp")
async def whatsapp_webhook_sync(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...)
):
    """
    Webhook para processar mensagens do WhatsApp
    """
    try:
        logger.info(f"📱 Webhook received from {From}: {Body[:50]}...")
        
        if not app_instances["orchestrator"]:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        phone_number = app_instances["twilio_service"].extract_phone_number(From)
        
        # Cria mensagem WhatsApp
        message = WhatsAppMessage(
            message_id=MessageSid,
            from_number=phone_number,
            to_number=app_instances["twilio_service"].phone_number,
            body=Body
        )
        
        # Processa através do orchestrator
        try:
            response = await app_instances["orchestrator"].process_message(message)
            
            # IMPORTANTE: Usa response_text do AgentResponse, não o JSON de classificação
            response_text = response.response_text
            
            logger.info(f"✅ Agent {response.agent_id} generated response: {response_text[:100]}...")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            response_text = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
        
        # Retorna resposta TwiML formatada
        return Response(
            content=f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>''',
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Desculpe, ocorreu um erro. Por favor, tente novamente em alguns instantes.</Message>
</Response>''',
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    try:
        # Check Redis
        await app_instances["redis"].ping()
        
        # Check LLM
        llm_status = await app_instances["llm_service"].get_service_status()
        
        # Check sessions
        active_sessions = await app_instances["session_manager"].get_active_sessions_count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "redis": "connected",
                "llm": llm_status.get("status", "unknown"),
                "sessions": active_sessions,
                "orchestrator": "active" if app_instances["orchestrator"] else "inactive"
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/metrics")
async def get_metrics():
    try:
        queue_status = await app_instances["queue_manager"].get_status()
        llm_status = await app_instances["llm_service"].get_service_status()
        active_sessions = await app_instances["session_manager"].get_active_sessions_count()
        
        return {
            "queue": queue_status,
            "llm_status": llm_status.get("status", "unknown"),
            "active_sessions": active_sessions,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/llm/status")
async def get_llm_status():
    """Endpoint específico para status do LLM"""
    try:
        return await app_instances["llm_service"].get_service_status()
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/llm/test")
async def test_llm(data: Dict[str, Any]):
    """Testa LLM diretamente"""
    try:
        prompt = data.get("prompt", "Olá")
        
        response = await app_instances["llm_service"].generate_response(
            prompt=prompt,
            system_message="Você é um assistente de teste. Responda brevemente."
        )
        
        return {
            "prompt": prompt,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{phone_number}")
async def analyze_conversation(phone_number: str):
    """Analisa conversa de um usuário"""
    try:
        session = await app_instances["session_manager"].get_session(phone_number)
        
        if not session:
            return {"error": "No session found for this number"}
        
        return {
            "phone_number": phone_number,
            "session_id": session.session_id,
            "current_agent": session.current_agent,
            "message_count": len(session.message_history),
            "context": session.conversation_context,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.updated_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suggestions/{phone_number}")
async def get_suggestions(phone_number: str, context: Optional[str] = None):
    """Obtém sugestões inteligentes para o usuário"""
    try:
        session = await app_instances["session_manager"].get_session(phone_number)
        
        if not session:
            return {"suggestions": ["Olá", "Menu", "Ajuda"]}
        
        # Gera sugestões baseadas no contexto
        prompt = f"""
        Baseado no contexto da conversa, sugira 3 próximas mensagens que o usuário poderia enviar.
        Contexto: {context or 'conversa geral'}
        Agente atual: {session.current_agent or 'reception'}
        
        Responda APENAS com uma lista JSON de 3 strings curtas.
        """
        
        suggestions_response = await app_instances["llm_service"].generate_response(
            prompt=prompt,
            system_message="Você é um assistente que sugere próximas mensagens.",
            temperature=0.5
        )
        
        try:
            # Tenta extrair JSON
            import json
            suggestions = json.loads(suggestions_response)
        except:
            # Fallback para sugestões padrão
            suggestions = ["Ver dados", "Preciso de ajuda", "Voltar ao menu"]
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        return {"suggestions": ["Menu", "Ajuda", "Sair"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )