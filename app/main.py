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
                <p><strong>Status:</strong> Funcionando com LLM</p>
                <p><strong>Ollama:</strong> http://192.168.15.31:11435</p>
            </div>
            
            <h3>🔗 Endpoints Disponíveis:</h3>
            <div class="endpoint"><strong>POST</strong> /webhook/whatsapp - Webhook do Twilio (LLM Integrado)</div>
            <div class="endpoint"><strong>GET</strong> /webhook/test - Teste do webhook</div>
            <div class="endpoint"><strong>GET</strong> /health - Status do sistema</div>
            <div class="endpoint"><strong>GET</strong> /status - Status detalhado</div>
            <div class="endpoint"><strong>GET</strong> /llm/status - Status do LLM</div>
            <div class="endpoint"><strong>POST</strong> /llm/test - Teste direto do LLM</div>
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
    """Webhook do WhatsApp - Integrado com LLM"""
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
        
        # Monta dados do webhook
        webhook_data = {
            'From': From,
            'To': To,
            'Body': Body,
            'MessageSid': MessageSid,
            'AccountSid': AccountSid,
            'MediaUrl0': MediaUrl0,
            'NumMedia': NumMedia
        }
        
        # IMPORTANTE: Usa o WhatsApp Service com LLM
        if whatsapp_service:
            logger.info("Processando mensagem com LLM...")
            twiml_response = await whatsapp_service.process_incoming_webhook(webhook_data)
            logger.info("Resposta LLM gerada com sucesso")
            return Response(
                content=twiml_response,
                media_type="application/xml"
            )
        else:
            logger.error("WhatsApp service não inicializado")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>Sistema temporariamente indisponível</Message></Response>',
                media_type="application/xml"
            )
        
    except Exception as e:
        logger.error(f"Erro no webhook: {str(e)}", exc_info=True)
        # Em caso de erro, retorna mensagem de erro amigável
        error_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>🤖 Ops! Tive um problema temporário. Por favor, tente novamente em alguns instantes.</Message>
</Response>'''
        return Response(
            content=error_response,
            media_type="application/xml"
        )

@app.get("/webhook/test")
async def webhook_test():
    """Endpoint de teste para verificar se webhook está acessível"""
    return {
        "status": "ok",
        "message": "Webhook endpoint está funcionando",
        "timestamp": datetime.now().isoformat(),
        "llm_integrated": True
    }

@app.get("/health")
async def health_check():
    """Health check do sistema"""
    try:
        health_status = {
            "status": "healthy", 
            "service": "jarvis-llm-orchestrator",
            "version": "2.0.0",
            "webhook": "ready",
            "timestamp": datetime.now().isoformat()
        }
        
        # Verifica status do LLM se disponível
        if whatsapp_service and hasattr(whatsapp_service, 'llm_service'):
            try:
                llm_status = await whatsapp_service.llm_service.get_service_status()
                health_status["llm"] = llm_status.get("status", "unknown")
            except:
                health_status["llm"] = "error"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/status")
async def detailed_status():
    """Status detalhado do sistema"""
    try:
        if whatsapp_service:
            return await whatsapp_service.get_service_status()
        else:
            return {
                "status": "initializing",
                "message": "Service is starting up",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/llm/status")
async def llm_status():
    """Status específico do LLM"""
    try:
        if whatsapp_service and whatsapp_service.llm_service:
            llm_status = await whatsapp_service.llm_service.get_service_status()
            return llm_status
        else:
            return {"status": "not_initialized", "message": "LLM service not ready"}
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/llm/test")
async def test_llm(data: Dict[str, Any]):
    """Teste direto do LLM"""
    try:
        prompt = data.get("prompt", "Olá, teste do LLM")
        
        if not whatsapp_service or not whatsapp_service.llm_service:
            raise HTTPException(status_code=503, detail="LLM service not available")
        
        # Gera resposta usando LLM
        response = await whatsapp_service.llm_service.generate_response(
            prompt=prompt,
            system_message="Você é o Jarvis, um assistente inteligente. Responda de forma concisa e amigável.",
            session_id="test_session"
        )
        
        return {
            "prompt": prompt,
            "response": response,
            "model": whatsapp_service.llm_service.model,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send")
async def send_message(data: Dict[str, Any]):
    """Envia mensagem via WhatsApp"""
    try:
        phone_number = data.get("phone_number")
        message = data.get("message")
        media_url = data.get("media_url")
        
        if not phone_number or not message:
            raise HTTPException(status_code=400, detail="phone_number and message are required")
        
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="WhatsApp service not available")
        
        success = await whatsapp_service.send_message(phone_number, message, media_url)
        
        if success:
            return {"status": "sent", "to": phone_number, "message": message}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset-session")
async def reset_session(data: Dict[str, Any]):
    """Reseta sessão de um usuário"""
    try:
        phone_number = data.get("phone_number")
        
        if not phone_number:
            raise HTTPException(status_code=400, detail="phone_number is required")
        
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="WhatsApp service not available")
        
        await whatsapp_service.reset_user_session(phone_number)
        
        return {"status": "success", "message": f"Session reset for {phone_number}"}
        
    except Exception as e:
        logger.error(f"Reset session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/{phone_number}")
async def analyze_conversation(phone_number: str):
    """Analisa conversa de um usuário usando LLM"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="WhatsApp service not available")
        
        analysis = await whatsapp_service.analyze_conversation(phone_number)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suggestions/{phone_number}")
async def get_suggestions(phone_number: str, context: str = Query("general")):
    """Obtém sugestões inteligentes para próxima interação"""
    try:
        if not whatsapp_service or not whatsapp_service.llm_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        # Gera sugestões usando LLM
        prompt = f"""Baseado no contexto '{context}' para o usuário {phone_number}, 
        sugira 3 ações ou perguntas relevantes para melhorar a experiência."""
        
        suggestions = await whatsapp_service.llm_service.generate_response(
            prompt=prompt,
            system_message="Você é um especialista em customer experience. Forneça sugestões práticas e relevantes.",
            session_id=f"suggestions_{phone_number}"
        )
        
        return {
            "phone_number": phone_number,
            "context": context,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )