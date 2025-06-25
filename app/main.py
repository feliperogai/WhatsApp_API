from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import logging
import redis.asyncio as redis
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
from datetime import datetime
import traceback
import json

from app.core.queue_manager import QueueManager, Priority
from app.core.rate_limiter import AdaptiveRateLimiter
from app.services.llm_service import LLMService
from app.services.message_processor import MessageProcessor
from app.services.twilio_service import TwilioService
from app.core.session_manager import SessionManager
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.models.message import WhatsAppMessage

load_dotenv()

# Garante que o diretório de logs existe
os.makedirs('logs', exist_ok=True)

# Configuração de logging mais detalhada
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "False").lower() == "true" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/jarvis.log', mode='a')
    ]
)
# Força encoding UTF-8 no StreamHandler para evitar UnicodeEncodeError
for handler in logging.getLogger().handlers:
    if hasattr(handler.stream, 'reconfigure'):
        try:
            handler.stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
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
    logger.info("🚀 Starting Jarvis WhatsApp Service...")
    
    try:
        # Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        logger.info(f"📡 Connecting to Redis at: {redis_url}")
        
        app_instances["redis"] = redis.from_url(redis_url, decode_responses=False)
        await app_instances["redis"].ping()
        logger.info("✅ Redis connected successfully")
        
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
        
        # LLM Service - com melhor tratamento de erro
        llm_initialized = False
        try:
            app_instances["llm_service"] = LLMService()
            await app_instances["llm_service"].initialize()
            llm_initialized = app_instances["llm_service"].is_initialized
            
            if llm_initialized:
                logger.info("✅ LLM Service initialized successfully")
                # Testa LLM imediatamente
                test_response = await app_instances["llm_service"].generate_response(
                    "teste", "Responda apenas: OK"
                )
                logger.info(f"🧪 LLM test response: {test_response}")
            else:
                logger.warning("⚠️ LLM Service initialized but not connected to Ollama")
        except Exception as e:
            logger.error(f"❌ LLM Service initialization failed: {e}")
            logger.warning("⚠️ Continuing with fallback responses only...")
        
        # Twilio Service
        try:
            app_instances["twilio_service"] = TwilioService()
            logger.info("✅ Twilio Service initialized")
        except Exception as e:
            logger.error(f"❌ Twilio Service initialization failed: {e}")
            raise
        
        # LangGraph Orchestrator - só inicializa se LLM estiver OK
        if app_instances["llm_service"]:
            try:
                app_instances["orchestrator"] = LangGraphOrchestrator(
                    app_instances["session_manager"],
                    app_instances["llm_service"]
                )
                logger.info("✅ LangGraph Orchestrator initialized")
            except Exception as e:
                logger.error(f"❌ Orchestrator initialization failed: {e}")
        
        # Message Processor
        if app_instances["orchestrator"]:
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
        logger.info(f"📊 LLM Status: {'Connected' if llm_initialized else 'Fallback Mode'}")
        
    except Exception as e:
        logger.error(f"❌ Critical error during startup: {e}", exc_info=True)
        # Permite que o serviço inicie mesmo com erros parciais
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Jarvis WhatsApp Service...")
    
    try:
        if app_instances["queue_manager"]:
            await app_instances["queue_manager"].stop_workers()
        
        if app_instances["llm_service"]:
            await app_instances["llm_service"].cleanup()
        
        if app_instances["redis"]:
            await app_instances["redis"].close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("✅ Jarvis WhatsApp Service stopped")

app = FastAPI(
    title="Jarvis WhatsApp Service",
    description="WhatsApp AI Assistant with Queue Management and LangGraph",
    version="3.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        # Status detalhado dos componentes
        redis_status = "🟢 Online" if app_instances.get("redis") else "🔴 Offline"
        
        llm_status = "🔴 Offline"
        llm_details = ""
        if app_instances.get("llm_service"):
            if app_instances["llm_service"].is_initialized:
                llm_status = "🟢 Online"
                status = await app_instances["llm_service"].get_service_status()
                llm_details = f"""
                <div class="metric">
                    <div>Ollama URL</div>
                    <div class="value" style="font-size: 1em;">{status.get('ollama_url', 'N/A')}</div>
                </div>
                <div class="metric">
                    <div>Model</div>
                    <div class="value" style="font-size: 1em;">{status.get('model', 'N/A')}</div>
                </div>
                """
            else:
                llm_status = "🟡 Fallback Mode"
        
        orchestrator_status = "🟢 Online" if app_instances.get("orchestrator") else "🔴 Offline"
        twilio_status = "🟢 Online" if app_instances.get("twilio_service") else "🔴 Offline"
        
        # Estatísticas
        active_sessions = 0
        if app_instances.get("session_manager"):
            active_sessions = await app_instances["session_manager"].get_active_sessions_count()
        
        return HTMLResponse(f"""
        <html>
        <head>
            <title>Jarvis WhatsApp Service</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    max-width: 1200px; 
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
                    padding: 15px;
                    background: #333;
                    border-radius: 8px;
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
                .warning {{
                    background: #ff9800;
                    color: #000;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
                .debug-info {{
                    background: #444;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                    font-family: monospace;
                    font-size: 0.9em;
                }}
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
                <div class="metric">
                    <div>Twilio</div>
                    <div class="value">{twilio_status}</div>
                </div>
                <div class="metric">
                    <div>Active Sessions</div>
                    <div class="value">{active_sessions}</div>
                </div>
                {llm_details}
            </div>
            
            <h2>API Endpoints</h2>
            <div class="endpoint">POST /webhook/whatsapp - WhatsApp webhook</div>
            <div class="endpoint">GET /health - Health check</div>
            <div class="endpoint">GET /status - Detailed system status</div>
            <div class="endpoint">GET /llm/status - LLM service status</div>
            <div class="endpoint">POST /llm/test - Test LLM directly</div>
            <div class="endpoint">GET /debug/test-webhook - Test webhook response</div>
            
            <h2>Quick Tests</h2>
            <p>
                <a href="/health">🏥 Health Check</a> | 
                <a href="/status">📊 Full Status</a> |
                <a href="/llm/status">🧠 LLM Status</a> |
                <a href="/debug/test-webhook">🧪 Test Webhook</a> |
                <a href="/docs">📚 API Docs</a>
            </p>
            
            <div class="debug-info">
                <h3>Debug Information</h3>
                <p>Timestamp: {datetime.now().isoformat()}</p>
                <p>Environment: {os.getenv('ENVIRONMENT', 'development')}</p>
                <p>Log Level: {os.getenv('LOG_LEVEL', 'INFO')}</p>
            </div>
        </body>
        </html>
        """)
    except Exception as e:
        logger.error(f"Error rendering root page: {e}")
        return HTMLResponse("<h1>Error loading page</h1>")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(None),
    Body: str = Form(None),
    MessageSid: str = Form(None)
):
    """
    Webhook principal para processar mensagens do WhatsApp
    TODAS as mensagens são processadas pelo LLM para conversas naturais
    """
    # Log detalhado da requisição recebida
    try:
        data = await request.form()
        logger.info(f"[Webhook] Dados recebidos (form): {dict(data)}")
    except Exception as e:
        logger.warning(f"[Webhook] Não foi possível ler como form: {e}")
        try:
            data = await request.json()
            logger.info(f"[Webhook] Dados recebidos (json): {data}")
        except Exception as e2:
            logger.error(f"[Webhook] Não foi possível ler como json: {e2}")
            data = {}
    # Se algum campo obrigatório não veio, retorna erro detalhado
    missing = []
    for field in ["From", "Body", "MessageSid"]:
        if locals().get(field) is None:
            missing.append(field)
    if missing:
        logger.error(f"[Webhook] Campos obrigatórios ausentes: {missing}")
        return JSONResponse(status_code=422, content={"error": "Campos obrigatórios ausentes", "missing": missing, "received": dict(data)})
    
    # Loga status do LLMService
    llm_service = app_instances.get("llm_service")
    if llm_service:
        status = await llm_service.get_service_status()
        logger.info(f"[Webhook] LLMService status: {status}")
    else:
        logger.warning("[Webhook] LLMService não está disponível na instância global!")

    # Tenta reinicializar o LLMService se não estiver inicializado
    if llm_service and not llm_service.is_initialized:
        logger.warning("[Webhook] LLMService não inicializado, tentando reinicializar...")
        try:
            await llm_service.initialize()
            status = await llm_service.get_service_status()
            logger.info(f"[Webhook] LLMService status após tentativa de init: {status}")
        except Exception as e:
            logger.error(f"[Webhook] Falha ao reinicializar LLMService: {e}")

    # Se ainda não inicializado, retorna fallback informando o motivo
    if not llm_service or not llm_service.is_initialized:
        logger.warning("⚠️ LLM ainda não inicializado após tentativa de recovery. Usando fallback.")
        reason = getattr(llm_service, "connection_error", "Motivo desconhecido")
        response_text = f"Desculpe, estou temporariamente fora do ar para respostas inteligentes. Motivo: {reason}. Tente novamente em alguns minutos ou digite 'menu'."
        xml_response = app_instances["twilio_service"].create_webhook_response(response_text)
        return Response(
            content=xml_response,
            media_type="application/xml"
        )
    
    try:
        # Log detalhado da requisição
        logger.info("="*60)
        logger.info(f"📱 MENSAGEM RECEBIDA | From: {From} | Body: {Body} | MessageSid: {MessageSid}")
        logger.info("="*60)
        
        # Verifica componentes essenciais
        if not app_instances.get("orchestrator"):
            logger.error("❌ Orchestrator not available")
            xml_response = app_instances["twilio_service"].create_webhook_response(
                "🤖 Sistema em manutenção. Por favor, tente novamente em alguns minutos."
            )
            return Response(
                content=xml_response,
                media_type="application/xml"
            )
        
        # IMPORTANTE: TODAS as mensagens vão para o orchestrator/LLM
        # Sem respostas hardcoded!
        
        # Extrai número de telefone
        phone_number = app_instances["twilio_service"].extract_phone_number(From)
        logger.info(f"📞 Extracted phone: {phone_number}")
        
        # Cria mensagem WhatsApp
        message = WhatsAppMessage(
            message_id=MessageSid,
            from_number=phone_number,
            to_number=app_instances["twilio_service"].phone_number,
            body=Body
        )
        
        # Processa através do orchestrator com timeout adequado
        try:
            import asyncio
            logger.info("🔄 Processing message through AI orchestrator...")
            
            response = await asyncio.wait_for(
                app_instances["orchestrator"].process_message(message),
                timeout=25.0
            )
            
            response_text = response.response_text
            logger.info(f"✅ Response generated by {response.agent_id}")
            logger.info(f"📝 Response preview: {response_text[:100]}...")
            
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout processing message")
            response_text = "Opa, demorei demais pensando aqui! 😅 Pode repetir? Prometo ser mais rápido!"
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Respostas de erro mais naturais e variadas
            error_responses = [
                "Eita, bugou aqui! 🐛 Me dá um segundinho que já volto!",
                "Ops, travei! 😵 Tenta de novo? Prometo que vou funcionar!",
                "Xiii, deu ruim aqui! Mas calma, já tô voltando! 🔧",
                "Poxa, tive um probleminha técnico. Pode repetir? 🙏"
            ]
            import random
            response_text = random.choice(error_responses)
        
        # Retorna resposta TwiML
        twiml_response = app_instances["twilio_service"].create_webhook_response(response_text)
        
        logger.info(f"📤 MENSAGEM ENVIADA | To: {From} | Body: {response_text}")
        return Response(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.critical(f"💥 CRITICAL WEBHOOK ERROR: {type(e).__name__} - {str(e)}")
        logger.critical(traceback.format_exc())
        
        # Erro crítico mais humano
        error_text = "🆘 Erro crítico no sistema. Por favor, tente novamente mais tarde."
        xml_response = app_instances["twilio_service"].create_webhook_response(error_text)
        logger.info(f"📤 MENSAGEM ENVIADA | To: {From} | Body: {error_text}")
        return Response(
            content=xml_response,
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint com informações detalhadas"""
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
                health_data["components"]["redis"] = {
                    "status": "connected",
                    "healthy": True
                }
        except Exception as e:
            health_data["components"]["redis"] = {
                "status": "disconnected",
                "healthy": False,
                "error": str(e)
            }
            health_data["status"] = "degraded"
        
        # Check LLM
        if app_instances.get("llm_service"):
            llm_status = await app_instances["llm_service"].get_service_status()
            health_data["components"]["llm"] = llm_status
            if llm_status.get("status") != "online":
                health_data["status"] = "degraded"
        else:
            health_data["components"]["llm"] = {
                "status": "not_initialized",
                "healthy": False
            }
        
        # Check Sessions
        if app_instances.get("session_manager"):
            active_sessions = await app_instances["session_manager"].get_active_sessions_count()
            health_data["components"]["sessions"] = {
                "active": active_sessions,
                "healthy": True
            }
        
        # Check Orchestrator
        if app_instances.get("orchestrator"):
            health_data["components"]["orchestrator"] = {
                "status": "online",
                "healthy": True
            }
        else:
            health_data["components"]["orchestrator"] = {
                "status": "offline",
                "healthy": False
            }
            health_data["status"] = "degraded"
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/status")
async def get_detailed_status():
    """Status detalhado do sistema"""
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "version": "3.0",
            "components": {}
        }
        
        # Redis status
        if app_instances.get("redis"):
            try:
                await app_instances["redis"].ping()
                info = await app_instances["redis"].info()
                status["components"]["redis"] = {
                    "status": "connected",
                    "version": info.get("redis_version", "unknown"),
                    "memory_used": info.get("used_memory_human", "unknown")
                }
            except Exception as e:
                status["components"]["redis"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # LLM status detalhado
        if app_instances.get("llm_service"):
            status["components"]["llm"] = await app_instances["llm_service"].get_service_status()
        
        # Session manager status
        if app_instances.get("session_manager"):
            active = await app_instances["session_manager"].get_active_sessions_count()
            status["components"]["sessions"] = {
                "active_sessions": active,
                "status": "online"
            }
        
        # Queue status
        if app_instances.get("queue_manager"):
            queue_status = await app_instances["queue_manager"].get_status()
            status["components"]["queue"] = queue_status
        
        # Orchestrator status
        if app_instances.get("orchestrator"):
            orch_status = await app_instances["orchestrator"].get_workflow_status()
            status["components"]["orchestrator"] = orch_status
        
        return status
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/llm/status")
async def get_llm_status():
    """Status específico do LLM com teste de conectividade"""
    try:
        if not app_instances.get("llm_service"):
            return {
                "status": "not_initialized",
                "error": "LLM service not available",
                "timestamp": datetime.now().isoformat()
            }
        
        # Status básico
        status = await app_instances["llm_service"].get_service_status()
        
        # Testa conectividade
        try:
            test_response = await app_instances["llm_service"].generate_response(
                "ping", "Responda apenas: pong"
            )
            status["connectivity_test"] = {
                "success": True,
                "response": test_response,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            status["connectivity_test"] = {
                "success": False,
                "error": str(e)
            }
        
        return status
        
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return {"status": "error", "error": str(e)}

@app.post("/llm/test")
async def test_llm(data: Dict[str, Any]):
    """Testa LLM diretamente com resposta detalhada"""
    try:
        if not app_instances.get("llm_service"):
            return {
                "error": "LLM service not available",
                "fallback_active": True
            }
        
        prompt = data.get("prompt", "Olá")
        system_message = data.get("system_message", "Você é um assistente de teste. Responda brevemente.")
        
        start_time = datetime.now()
        
        try:
            response = await app_instances["llm_service"].generate_response(
                prompt=prompt,
                system_message=system_message
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            return {
                "prompt": prompt,
                "response": response,
                "elapsed_seconds": elapsed,
                "timestamp": datetime.now().isoformat(),
                "llm_status": "online",
                "model": app_instances["llm_service"].model
            }
            
        except Exception as e:
            # Usa fallback
            fallback_response = app_instances["llm_service"]._get_fallback_response(prompt)
            
            return {
                "prompt": prompt,
                "response": fallback_response,
                "error": str(e),
                "fallback_used": True,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        return {"error": str(e)}

@app.get("/debug/test-webhook")
async def test_webhook_debug():
    """Endpoint de debug para testar o webhook"""
    try:
        # Simula uma mensagem de teste
        test_message = WhatsAppMessage(
            message_id="DEBUG_TEST_" + str(datetime.now().timestamp()),
            from_number="+5511999999999",
            to_number="+14155238886",
            body="Teste de debug"
        )
        
        if not app_instances.get("orchestrator"):
            return {
                "error": "Orchestrator not available",
                "components": {
                    "llm_service": app_instances.get("llm_service") is not None,
                    "session_manager": app_instances.get("session_manager") is not None
                }
            }
        
        # Tenta processar
        try:
            response = await app_instances["orchestrator"].process_message(test_message)
            
            return {
                "success": True,
                "response": {
                    "agent_id": response.agent_id,
                    "text": response.response_text,
                    "confidence": response.confidence,
                    "metadata": response.metadata
                },
                "session_id": response.metadata.get("session_id"),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
            
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/debug/test-session")
async def test_session_creation():
    """Testa criação de sessão"""
    try:
        if not app_instances.get("session_manager"):
            return {"error": "Session manager not available"}
        
        phone = "+5511999999999"
        session = await app_instances["session_manager"].get_or_create_session(phone)
        
        return {
            "session_id": session.session_id,
            "phone_number": session.phone_number,
            "current_agent": session.current_agent,
            "message_count": len(session.message_history),
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat()
        }
        
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="debug" if os.getenv("DEBUG", "False").lower() == "true" else "info"
    )