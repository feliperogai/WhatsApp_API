main_py = ""
from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
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
    logger.info("🚀 Jarvis WhatsApp Agent Orchestrator started")
    yield
    # Shutdown
    logger.info("🛑 Jarvis WhatsApp Agent Orchestrator stopped")

# Create FastAPI app
app = FastAPI(
    title="Jarvis WhatsApp Agent Orchestrator",
    description="Sistema de orquestração de agentes IA para WhatsApp via Twilio",
    version="1.0.0",
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
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jarvis WhatsApp Agent Orchestrator</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40; background: #f5f5f5; }
            .container { max-width: 800; margin: 0 auto; background: white; padding: 30; border-radius: 10; box-shadow: 0 2 10 rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30; }
            .status { background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 10px 0; }
            .endpoint { background: #f0f0f0; padding: 10px; margin: 5px 0; border-radius: 5px; }
            .code { font-family: monospace; background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Jarvis WhatsApp Agent Orchestrator</h1>
                <p>Sistema de IA com orquestração de 4 agentes especialistas</p>
            </div>
            
            <div class="status">
                <h3>✅ Sistema Online</h3>
                <p><strong>Ambiente:</strong> {settings.environment}</p>
                <p><strong>Versão:</strong> 1.0.0</p>
                <p><strong>Twilio Phone:</strong> {settings.twilio_phone_number}</p>
            </div>
            
            <h3>🔗 Endpoints Disponíveis:</h3>
            <div class="endpoint"><strong>POST</strong> /webhook/whatsapp - Webhook do Twilio</div>
            <div class="endpoint"><strong>GET</strong> /health - Status do sistema</div>
            <div class="endpoint"><strong>GET</strong> /status - Status detalhado</div>
            <div class="endpoint"><strong>POST</strong> /send - Enviar mensagem manual</div>
            <div class="endpoint"><strong>POST</strong> /reset-session - Resetar sessão de usuário</div>
            
            <h3>🤖 Agentes Ativos:</h3>
            <ul>
                <li><strong>Reception Agent:</strong> Recepção e triagem inicial</li>
                <li><strong>Classification Agent:</strong> IA para classificação de intenções</li>
                <li><strong>Data Agent:</strong> Consultas e relatórios de dados</li>
                <li><strong>Support Agent:</strong> Suporte técnico especializado</li>
            </ul>
            
            <h3>⚙️ Configuração Webhook Twilio:</h3>
            <div class="code">
URL: {settings.webhook_base_url}/webhook/whatsapp
Method: POST
            </div>
            
            <h3>📱 Teste via WhatsApp:</h3>
            <p>Envie uma mensagem para: <strong>{settings.twilio_phone_number}</strong></p>
            <p>Comandos de teste: "olá", "relatório de vendas", "problema técnico", "agendar reunião"</p>
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
        
        # Processa mensagem
        twiml_response = await whatsapp_service.process_incoming_webhook(webhook_data)
        
        return Response(content=twiml_response, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "jarvis-whatsapp-orchestrator"}

@app.get("/status")
async def detailed_status():
    try:
        status = await whatsapp_service.get_service_status()
        return status
    except Exception as e:
        logger.error(f"Status check error: {e}")
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
    phone_numbers: list[str],
    message: str,
    background_tasks: BackgroundTasks
):
    try:
        # Executa broadcast em background
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