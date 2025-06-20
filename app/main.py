from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks, Query
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import uvicorn

from app.config.settings import settings
from app.services.whatsapp_service import WhatsAppService
from app.utils.logger import setup_logger

# Setup logging
setup_logger()
logger = logging.getLogger(__name__)

# Global service instance
whatsapp_service: Optional[WhatsAppService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global whatsapp_service
    whatsapp_service = WhatsAppService()
    await whatsapp_service.initialize()
    logger.info("🤖 Jarvis WhatsApp LLM Agent Orchestrator v2.0 started")
    yield
    # Shutdown
    if whatsapp_service:
        await whatsapp_service.cleanup()
    logger.info("🛑 Jarvis stopped")

# Create FastAPI app
app = FastAPI(
    title="Jarvis WhatsApp LLM Agent Orchestrator",
    description="Sistema de IA conversacional para WhatsApp usando LLM otimizado",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jarvis LLM Agent Orchestrator v2.0</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px); }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .status {{ background: rgba(0,255,0,0.2); padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #00ff00; }}
            .config {{ background: rgba(0,150,255,0.2); padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #0096ff; }}
            .endpoint {{ background: rgba(255,255,255,0.1); padding: 12px; margin: 8px 0; border-radius: 8px; }}
            .code {{ font-family: monospace; background: rgba(0,0,0,0.3); color: #f8f8f2; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Jarvis LLM Agent Orchestrator v2.0</h1>
                <p>Sistema IA Otimizado para Ollama</p>
            </div>
            
            <div class="status">
                <h3>✅ Sistema Online</h3>
                <p><strong>Versão:</strong> 2.0.0 (Otimizada)</p>
                <p><strong>Twilio:</strong> {settings.twilio_phone_number}</p>
            </div>
            
            <div class="config">
                <h3>🧠 Configuração LLM</h3>
                <p><strong>Ollama:</strong> http://192.168.15.31:11435</p>
                <p><strong>Modelo:</strong> llama3.1:8b</p>
                <p><strong>Status:</strong> Conectado e funcionando</p>
            </div>
            
            <h3>🔗 Endpoints:</h3>
            <div class="endpoint"><strong>GET</strong> /health - Status do sistema</div>
            <div class="endpoint"><strong>GET</strong> /status - Status detalhado</div>
            <div class="endpoint"><strong>GET</strong> /llm/status - Status LLM</div>
            <div class="endpoint"><strong>POST</strong> /llm/test - Teste direto LLM</div>
            <div class="endpoint"><strong>POST</strong> /webhook/whatsapp - Webhook Twilio</div>
            <div class="endpoint"><strong>POST</strong> /send - Enviar mensagem</div>
            
            <h3>🧪 Teste Rápido:</h3>
            <div class="code">
curl -X POST http://localhost:8000/llm/test \\
  -H "Content-Type: application/json" \\
  -d '{"prompt": "Olá, como você está?"}'
            </div>
            
            <h3>📱 Webhook Twilio:</h3>
            <div class="code">
URL: [SEU_NGROK_URL]/webhook/whatsapp
Method: POST
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    AccountSid: str = Form(...),
    MessageSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(default=""),
    MediaUrl0: Optional[str] = Form(default=None)
):
    try:
        # Constrói dados do webhook
        webhook_data = {
            "AccountSid": AccountSid,
            "MessageSid": MessageSid,
            "From": From,
            "To": To,
            "Body": Body,
            "MediaUrl0": MediaUrl0
        }
        
        logger.info(f"Webhook received from {From}: {Body[:50]}...")
        
        # Processa via LLM
        twiml_response = await whatsapp_service.process_incoming_webhook(webhook_data)
        
        return Response(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "jarvis-llm-orchestrator",
        "version": "2.0.0",
        "ai_powered": True,
        "ollama_configured": True
    }

@app.get("/status")
async def detailed_status():
    try:
        status = await whatsapp_service.get_service_status()
        return status
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/llm/status")
async def llm_status():
    """Status específico do LLM"""
    try:
        llm_status = await whatsapp_service.llm_service.get_service_status()
        return {
            "llm_service": llm_status,
            "ollama_url": "http://192.168.15.31:11435",
            "model": "llama3.1:8b",
            "optimized": True
        }
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/llm/test")
async def test_llm(prompt: str = "Olá, como você está?"):
    """Testa LLM diretamente"""
    try:
        response = await whatsapp_service.llm_service.generate_response(
            prompt=prompt,
            system_message="Você é um assistente de teste. Responda de forma amigável e concisa."
        )
        return {
            "prompt": prompt,
            "response": response,
            "model": "llama3.1:8b",
            "ollama_url": "http://192.168.15.31:11435",
            "timestamp": "now"
        }
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send")
async def send_message(
    phone_number: str,
    message: str,
    media_url: Optional[str] = None
):
    try:
        success = await whatsapp_service.send_message(phone_number, message, media_url)
        
        if success:
            return {"status": "sent", "to": phone_number, "message": message}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset-session")
async def reset_session(phone_number: str):
    try:
        await whatsapp_service.reset_user_session(phone_number)
        return {"status": "reset", "phone_number": phone_number}
    except Exception as e:
        logger.error(f"Reset session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/broadcast")
async def broadcast_message(
    phone_numbers: List[str],
    message: str,
    background_tasks: BackgroundTasks
):
    try:
        background_tasks.add_task(whatsapp_service.broadcast_message, phone_numbers, message)
        
        return {
            "status": "broadcasting",
            "recipients": len(phone_numbers),
            "message": message[:50] + "..." if len(message) > 50 else message
        }
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )