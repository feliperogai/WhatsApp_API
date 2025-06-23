from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import logging
import redis.asyncio as redis
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

from app.core.queue_manager import QueueManager, Priority
from app.core.rate_limiter import AdaptiveRateLimiter
from app.services.llm_service import OptimizedLLMService
from app.services.message_processor import MessageProcessor
from app.services.twilio_service import TwilioService

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
    "message_processor": None
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Jarvis WhatsApp Service...")
    
    try:
        app_instances["redis"] = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=False
        )
        await app_instances["redis"].ping()
        
        app_instances["queue_manager"] = QueueManager(
            redis_client=app_instances["redis"],
            max_queue_size=int(os.getenv("MAX_QUEUE_SIZE", "1000")),
            max_workers=int(os.getenv("MAX_WORKERS", "3")),
            max_retries=int(os.getenv("MAX_RETRIES", "3"))
        )
        
        app_instances["rate_limiter"] = AdaptiveRateLimiter(
            redis_client=app_instances["redis"],
            global_rate=float(os.getenv("GLOBAL_RATE_LIMIT", "10"))/60,
            global_burst=int(os.getenv("GLOBAL_BURST", "5")),
            user_rate=float(os.getenv("USER_RATE_LIMIT", "3"))/60,
            user_burst=int(os.getenv("USER_BURST", "2"))
        )
        
        ollama_urls = os.getenv("OLLAMA_URLS", "http://localhost:11434").split(",")
        ollama_models = os.getenv("OLLAMA_MODELS", "llama3.1:8b").split(",")
        
        app_instances["llm_service"] = OptimizedLLMService(
            base_urls=ollama_urls,
            models=ollama_models,
            redis_client=app_instances["redis"],
            pool_size=int(os.getenv("LLM_POOL_SIZE", "2")),
            cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
            max_cache_size=int(os.getenv("MAX_CACHE_SIZE", "1000"))
        )
        await app_instances["llm_service"].initialize()
        
        app_instances["twilio_service"] = TwilioService(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            phone_number=os.getenv("TWILIO_PHONE_NUMBER")
        )
        
        app_instances["message_processor"] = MessageProcessor(
            llm_service=app_instances["llm_service"],
            rate_limiter=app_instances["rate_limiter"],
            twilio_service=app_instances["twilio_service"],
            redis_client=app_instances["redis"]
        )
        
        await app_instances["queue_manager"].start_workers(
            app_instances["message_processor"].process_message
        )
        
        logger.info("✅ Jarvis WhatsApp Service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    
    yield
    
    logger.info("Shutting down Jarvis WhatsApp Service...")
    
    if app_instances["queue_manager"]:
        await app_instances["queue_manager"].stop_workers()
    
    if app_instances["llm_service"]:
        await app_instances["llm_service"].close()
    
    if app_instances["redis"]:
        await app_instances["redis"].close()
    
    logger.info("Jarvis WhatsApp Service stopped")

app = FastAPI(
    title="Jarvis WhatsApp Service",
    description="Optimized WhatsApp AI Assistant with Queue Management",
    version="3.0",
    lifespan=lifespan
)

@app.get("/")
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
        <p>Optimized AI Assistant with Queue Management</p>
        
        <div class="status">
            <h2>System Status</h2>
            <div id="metrics">Loading...</div>
        </div>
        
        <h2>API Endpoints</h2>
        <div class="endpoint">POST /webhook/whatsapp - WhatsApp webhook</div>
        <div class="endpoint">GET /health - Health check</div>
        <div class="endpoint">GET /metrics - System metrics</div>
        <div class="endpoint">GET /queue/status - Queue status</div>
        <div class="endpoint">POST /queue/retry/{message_id} - Retry failed message</div>
        
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
                            <div>Success Rate</div>
                            <div class="value">${(data.processor.success_rate * 100).toFixed(1)}%</div>
                        </div>
                        <div class="metric">
                            <div>Avg Response</div>
                            <div class="value">${data.processor.avg_processing_time.toFixed(2)}s</div>
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
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...)
):
    try:
        if not app_instances["twilio_service"]:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        phone_number = app_instances["twilio_service"].extract_phone_number(From)
        
        message_lower = Body.lower()
        if any(urgent in message_lower for urgent in ["urgente", "emergência", "crítico"]):
            priority = Priority.URGENT
        elif any(high in message_lower for high in ["importante", "prioridade"]):
            priority = Priority.HIGH
        else:
            priority = Priority.NORMAL
        
        message_id = await app_instances["queue_manager"].enqueue(
            phone_number=phone_number,
            content=Body,
            priority=priority,
            metadata={"message_sid": MessageSid}
        )
        
        if not message_id:
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>Sistema sobrecarregado. Tente novamente em alguns minutos.</Message></Response>',
                media_type="application/xml"
            )
        
        logger.info(f"Message queued: {message_id} from {phone_number}")
        
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>Erro ao processar mensagem.</Message></Response>',
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    try:
        await app_instances["redis"].ping()
        queue_status = await app_instances["queue_manager"].get_status()
        
        return {
            "status": "healthy",
            "queue": {
                "pending": queue_status["pending"],
                "processing": queue_status["processing"],
                "health": queue_status["queue_health"]
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/metrics")
async def get_metrics():
    try:
        queue_status = await app_instances["queue_manager"].get_status()
        processor_metrics = await app_instances["message_processor"].get_metrics()
        
        return {
            "queue": queue_status,
            "processor": processor_metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/status")
async def get_queue_status():
    try:
        return await app_instances["queue_manager"].get_status()
    except Exception as e:
        logger.error(f"Queue status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/dead-letters")
async def get_dead_letters(limit: int = 10):
    try:
        return await app_instances["queue_manager"].get_dead_letters(limit)
    except Exception as e:
        logger.error(f"Dead letters error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/retry/{message_id}")
async def retry_dead_letter(message_id: str):
    try:
        success = await app_instances["queue_manager"].retry_dead_letter(message_id)
        if success:
            return {"status": "success", "message": "Message requeued"}
        else:
            raise HTTPException(status_code=404, detail="Message not found")
    except Exception as e:
        logger.error(f"Retry error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cache/clear")
async def clear_cache():
    try:
        # Clear LLM cache
        cursor = 0
        cleared = 0
        while True:
            cursor, keys = await app_instances["redis"].scan(
                cursor, 
                match="jarvis:llm_cache:*", 
                count=100
            )
            if keys:
                await app_instances["redis"].delete(*keys)
                cleared += len(keys)
            if cursor == 0:
                break
        
        return {"status": "success", "cleared": cleared}
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )