from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import uvicorn
from datetime import datetime

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
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jarvis LLM Agent Orchestrator v2.0</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .container { max-width: 1000px; margin: 0 auto; background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px); }
            .header { text-align: center; margin-bottom: 30px; }
            .status { background: rgba(0,255,0,0.2); padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #00ff00; }
            .endpoint { background: rgba(255,255,255,0.1); padding: 12px; margin: 8px 0; border-radius: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Jarvis LLM Agent Orchestrator v2.0</h1>
                <p>Sistema IA Otimizado para WhatsApp</p>
            </div>
            
            <div class="status">
                <h3>✅ Sistema Online</h3>
                <p><strong>Webhook:</strong> /webhook/whatsapp</p>
                <p><strong>Status:</strong> Funcionando</p>
            </div>
            
            <h3>🔗 Endpoints Disponíveis:</h3>
            <div class="endpoint"><strong>POST</strong> /webhook/whatsapp - Webhook do Twilio</div>
            <div class="endpoint"><strong>GET</strong> /webhook/test - Teste do webhook</div>
            <div class="endpoint"><strong>GET</strong> /health - Status do sistema</div>
            <div class="endpoint"><strong>POST</strong> /send - Enviar mensagem</div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(None),
    To: str = Form(None),
    Body: str = Form(""),
    AccountSid: str = Form(None),
    MessageSid: str = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    NumMedia: str = Form("0")
):
    """Webhook do WhatsApp - Versão Funcional"""
    try:
        # Log para debug
        logger.info(f"=== WEBHOOK RECEBIDO ===")
        logger.info(f"From: {From}")
        logger.info(f"Body: {Body}")
        logger.info(f"MessageSid: {MessageSid}")
        
        # Validação básica
        if not From or not MessageSid:
            logger.error("Webhook sem campos obrigatórios")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                media_type="application/xml"
            )
        
        # Por enquanto, resposta simples para testar
        if Body.lower() in ['oi', 'olá', 'ola', 'hello', 'hi']:
            response_text = "👋 Olá! Eu sou o Jarvis, seu assistente inteligente. Como posso ajudar?"
        elif Body.lower() in ['teste', 'test']:
            response_text = "✅ Webhook funcionando perfeitamente!"
        else:
            response_text = f"🤖 Recebi sua mensagem: '{Body}'. Em breve terei respostas mais inteligentes!"
        
        # Monta resposta TwiML
        twiml_response = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>'''
        
        logger.info(f"Respondendo com: {response_text[:50]}...")
        
        return Response(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}", exc_info=True)
        # Em caso de erro, retorna TwiML vazio para não dar erro no Twilio
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )

@app.get("/webhook/test")
async def webhook_test():
    """Endpoint de teste para verificar se webhook está acessível"""
    return {
        "status": "ok",
        "message": "Webhook endpoint está funcionando",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "jarvis-llm-orchestrator",
        "version": "2.0.0",
        "webhook": "ready"
    }

@app.get("/status")
async def detailed_status():
    try:
        return {
            "status": "operational",
            "webhook": "configured",
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "webhook": "/webhook/whatsapp",
                "health": "/health",
                "test": "/webhook/test"
            }
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/llm/status")
async def llm_status():
    """Status do LLM"""
    try:
        if whatsapp_service and whatsapp_service.llm_service:
            llm_status = await whatsapp_service.llm_service.get_service_status()
            return llm_status
        else:
            return {"status": "not_initialized"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/send")
async def send_message(data: Dict[str, Any]):
    """Envia mensagem via WhatsApp"""
    try:
        phone_number = data.get("phone_number")
        message = data.get("message")
        media_url = data.get("media_url")
        
        if not phone_number or not message:
            raise HTTPException(status_code=400, detail="phone_number and message are required")
        
        success = await whatsapp_service.send_message(phone_number, message, media_url)
        
        if success:
            return {"status": "sent", "to": phone_number, "message": message}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )