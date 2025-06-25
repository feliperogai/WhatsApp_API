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
from app.services.llm_service import LLMService  # CORREÇÃO: Import correto
from app.services.message_processor import MessageProcessor
from app.services.twilio_service import TwilioService
from app.core.session_manager import SessionManager
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
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        logger.info(f"Connecting to Redis at: {redis_url}")
        
        app_instances["redis"] = redis.from_url(redis_url, decode_responses=False)
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
        
        # LLM Service - com tratamento de erro melhorado
        try:
            app_instances["llm_service"] = LLMService()
            await app_instances["llm_service"].initialize()
            logger.info("✅ LLM Service initialized")
        except Exception as e:
            logger.error(f"⚠️ LLM Service initialization failed: {e}")
            logger.warning("Continuing with fallback responses...")
        
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
        logger.error(f"Failed to start service: {e}", exc_info=True)
        # Não levanta exceção para permitir que o serviço inicie com funcionalidade limitada
    
    yield
    
    # Shutdown
    logger.info("Shutting down Jarvis WhatsApp Service...")
    
    try:
        if app_instances["queue_manager"]:
            await app_instances["queue_manager"].stop_workers()
        
        if app_instances["llm_service"]:
            await app_instances["llm_service"].cleanup()
        
        if app_instances["redis"]:
            await app_instances["redis"].close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Jarvis WhatsApp Service stopped")

app = FastAPI(
    title="Jarvis WhatsApp Service",
    description="WhatsApp AI Assistant with Queue Management and LangGraph",
    version="3.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        # Verifica status dos componentes
        redis_status = "🟢 Online" if app_instances.get("redis") else "🔴 Offline"
        llm_status = "🟢 Online" if app_instances.get("llm_service") and app_instances["llm_service"].is_initialized else "🟡 Fallback Mode"
        orchestrator_status = "🟢 Online" if app_instances.get("orchestrator") else "🔴 Offline"
        
        return HTMLResponse(f"""
        <html>
        <head>
            <title>Jarvis WhatsApp Service</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 20px;
                    background: #1a1a1a;
                    color: #fff;
                }}
                .status {{ 
                    background: #2a2a2a; 
                    padding: 20px; 
                    border-radius: 10px; 
                    margin: 20px 0;
                }}
                .metric {{
                    display: inline-block;
                    margin: 10px 20px 10px 0;
                }}
                .metric .value {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #4CAF50;
                }}
                .endpoint {{
                    background: #333;
                    padding: 10px;
                    margin: 5px 0;
                    border-radius: 5px;
                    font-family: monospace;
                }}
                h1, h2 {{ color: #4CAF50; }}
                a {{ color: #4CAF50; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>🤖 Jarvis WhatsApp Service v3.0</h1>
            <p>AI Assistant with Queue Management and LangGraph</p>
            
            <div class="status">
                <h2>System Status</h2>
                <div class="metric">
                    <div>Redis</div>
                    <div class="value">{redis_status}</div>
                </div>
                <div class="metric">
                    <div>LLM Service</div>
                    <div class="value">{llm_status}</div>
                </div>
                <div class="metric">
                    <div>Orchestrator</div>
                    <div class="value">{orchestrator_status}</div>
                </div>
            </div>
            
            <h2>API Endpoints</h2>
            <div class="endpoint">POST /webhook/whatsapp - WhatsApp webhook</div>
            <div class="endpoint">GET /health - Health check</div>
            <div class="endpoint">GET /metrics - System metrics</div>
            <div class="endpoint">GET /llm/status - LLM status</div>
            
            <p style="margin-top: 30px;">
                <a href="/docs">📚 API Documentation</a> | 
                <a href="/health">🏥 Health Check</a>
            </p>
        </body>
        </html>
        """)
    except Exception as e:
        logger.error(f"Error rendering root page: {e}")
        return HTMLResponse("<h1>Error loading page</h1>")

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
        
        # Verifica se o orchestrator está disponível
        if not app_instances.get("orchestrator"):
            logger.error("Orchestrator not available")
            return Response(
                content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>🤖 Sistema iniciando. Tente novamente em 10 segundos.</Message>
</Response>''',
                media_type="application/xml"
            )
        
        # Verifica se LLM está inicializado
        if not app_instances.get("llm_service") or not app_instances["llm_service"].is_initialized:
            logger.error("LLM Service not initialized")
            return Response(
                content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>🤖 Sistema de IA em manutenção. Tente novamente em breve.</Message>
</Response>''',
                media_type="application/xml"
            )
        
        phone_number = app_instances["twilio_service"].extract_phone_number(From)
        
        # Cria mensagem WhatsApp
        message = WhatsAppMessage(
            message_id=MessageSid,
            from_number=phone_number,
            to_number=app_instances["twilio_service"].phone_number,
            body=Body
        )
        
        # Processa através do orchestrator com timeout MENOR
        try:
            import asyncio
            response = await asyncio.wait_for(
                app_instances["orchestrator"].process_message(message),
                timeout=20.0  # Reduzido de 25 para 20 segundos
            )
            
            response_text = response.response_text
            logger.info(f"✅ Response generated: {response_text[:100]}...")
            
        except asyncio.TimeoutError:
            logger.error("Timeout processing message")
            response_text = "⏱️ Desculpe, estou processando muitas mensagens. Tente novamente!"
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
            # Log mais detalhado do erro
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "phone": phone_number,
                "message": Body[:100]
            }
            logger.error(f"Error details: {json.dumps(error_details)}")
            
            # Mensagem de erro mais específica
            if "connection" in str(e).lower() or "ollama" in str(e).lower():
                response_text = "🤖 Estou com problemas para conectar ao meu cérebro. Nosso time foi notificado!"
            else:
                response_text = "😅 Ops! Algo deu errado. Pode tentar de novo?"
        
        # Retorna resposta TwiML
        return Response(
            content=f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>''',
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Critical webhook error: {e}", exc_info=True)
        
        # Log crítico
        logger.critical(f"WEBHOOK FAILED COMPLETELY: {type(e).__name__} - {str(e)}")
        
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>🤖 Desculpe, ocorreu um erro crítico. Por favor, tente novamente em alguns minutos.</Message>
</Response>''',
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Check Redis
        try:
            if app_instances.get("redis"):
                await app_instances["redis"].ping()
                health_data["components"]["redis"] = "connected"
        except:
            health_data["components"]["redis"] = "disconnected"
            health_data["status"] = "degraded"
        
        # Check LLM
        if app_instances.get("llm_service"):
            llm_status = await app_instances["llm_service"].get_service_status()
            health_data["components"]["llm"] = llm_status.get("status", "unknown")
        else:
            health_data["components"]["llm"] = "not_initialized"
        
        # Check sessions
        if app_instances.get("session_manager"):
            active_sessions = await app_instances["session_manager"].get_active_sessions_count()
            health_data["components"]["sessions"] = active_sessions
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/llm/status")
async def get_llm_status():
    """Endpoint específico para status do LLM"""
    try:
        if not app_instances.get("llm_service"):
            return {"status": "not_initialized", "error": "LLM service not available"}
            
        return await app_instances["llm_service"].get_service_status()
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return {"status": "error", "error": str(e)}

@app.post("/llm/test")
async def test_llm(data: Dict[str, Any]):
    """Testa LLM diretamente"""
    try:
        if not app_instances.get("llm_service"):
            return {"error": "LLM service not available"}
            
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
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )