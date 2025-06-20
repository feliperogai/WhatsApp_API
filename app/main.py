from fastapi import FastAPI, Request, HTTPException, Form, BackgroundTasks, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import uvicorn
from datetime import datetime

from app.config.settings import settings
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from app.services.queue_endpoints import router as queue_router, set_whatsapp_service
from app.utils.logger import setup_logger

# Setup logging
setup_logger()
logger = logging.getLogger(__name__)

# Global service instance
whatsapp_service: Optional[EnhancedWhatsAppService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global whatsapp_service
    logger.info("🚀 Iniciando Jarvis WhatsApp LLM com Sistema de Queue...")
    
    try:
        # Inicializa serviço aprimorado
        whatsapp_service = EnhancedWhatsAppService()
        await whatsapp_service.initialize()
        
        # Define referência para os endpoints de queue
        set_whatsapp_service(whatsapp_service)
        
        logger.info("✅ Jarvis WhatsApp LLM Agent Orchestrator v2.0 (Queue Edition) started")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Parando Jarvis...")
    if whatsapp_service:
        await whatsapp_service.cleanup()
    logger.info("🛑 Jarvis stopped")

# Create FastAPI app
app = FastAPI(
    title="Jarvis WhatsApp LLM Agent Orchestrator - Queue Edition",
    description="Sistema de IA conversacional para WhatsApp com Queue Management",
    version="2.1.0",
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

# Include queue router
app.include_router(queue_router)

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jarvis LLM Agent Orchestrator v2.1 - Queue Edition</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                margin: 40px; 
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                color: white; 
                min-height: 100vh;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: rgba(255,255,255,0.1); 
                padding: 40px; 
                border-radius: 20px; 
                backdrop-filter: blur(10px); 
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            }
            .header { 
                text-align: center; 
                margin-bottom: 40px; 
                padding-bottom: 30px;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .header h1 {
                font-size: 3em;
                margin-bottom: 10px;
                background: linear-gradient(45deg, #00ff88, #00d4ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            .status-card {
                background: rgba(255,255,255,0.1);
                padding: 25px;
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.2);
                transition: all 0.3s ease;
            }
            .status-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 5px 20px rgba(0,255,136,0.3);
            }
            .status { 
                background: rgba(0,255,0,0.2); 
                padding: 20px; 
                border-radius: 15px; 
                margin: 20px 0; 
                border-left: 5px solid #00ff00;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 0.8; }
                50% { opacity: 1; }
                100% { opacity: 0.8; }
            }
            .endpoint { 
                background: rgba(255,255,255,0.05); 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.1);
                transition: all 0.2s ease;
            }
            .endpoint:hover {
                background: rgba(255,255,255,0.1);
                transform: translateX(5px);
            }
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.8em;
                margin-left: 10px;
                background: linear-gradient(45deg, #667eea, #764ba2);
            }
            .new-badge {
                background: linear-gradient(45deg, #f093fb, #f5576c);
                animation: glow 2s ease-in-out infinite;
            }
            @keyframes glow {
                0%, 100% { box-shadow: 0 0 5px rgba(245, 87, 108, 0.5); }
                50% { box-shadow: 0 0 20px rgba(245, 87, 108, 0.8); }
            }
            .monitor-link {
                display: inline-block;
                margin-top: 20px;
                padding: 15px 30px;
                background: linear-gradient(45deg, #00ff88, #00d4ff);
                color: #1e3c72;
                text-decoration: none;
                border-radius: 30px;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .monitor-link:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 30px rgba(0,255,136,0.5);
            }
            .feature-list {
                list-style: none;
                padding: 0;
            }
            .feature-list li {
                padding: 10px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            .feature-list li:before {
                content: "✨ ";
                color: #00ff88;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Jarvis LLM Agent Orchestrator v2.1</h1>
                <p style="font-size: 1.3em;">Sistema IA Otimizado com Queue Management</p>
                <p style="opacity: 0.8;">Processamento inteligente de mensagens com fila de prioridades</p>
            </div>
            
            <div class="status">
                <h3>✅ Sistema Online - Queue Edition</h3>
                <p><strong>🔗 Webhook:</strong> /webhook/whatsapp</p>
                <p><strong>⚡ Status:</strong> Funcionando com Queue + LLM</p>
                <p><strong>🧠 Ollama:</strong> http://192.168.15.31:11435</p>
                <p><strong>📊 Queue:</strong> Redis-based Priority Queue</p>
            </div>
            
            <div class="status-grid">
                <div class="status-card">
                    <h3>🎯 Recursos Queue</h3>
                    <ul class="feature-list">
                        <li>Fila de prioridades inteligente</li>
                        <li>Rate limiting para LLM local</li>
                        <li>Circuit breaker protection</li>
                        <li>Dead letter queue</li>
                        <li>Retry automático com backoff</li>
                        <li>Cache de respostas LLM</li>
                    </ul>
                </div>
                
                <div class="status-card">
                    <h3>📈 Performance</h3>
                    <ul class="feature-list">
                        <li>Max 5 requisições LLM/minuto</li>
                        <li>3 workers simultâneos</li>
                        <li>Limite 10 msgs/usuário</li>
                        <li>Cache com TTL 1 hora</li>
                        <li>WebSocket para real-time</li>
                    </ul>
                </div>
            </div>
            
            <h3>🔗 Endpoints Disponíveis:</h3>
            
            <h4>📋 Queue Management <span class="badge new-badge">NEW</span></h4>
            <div class="endpoint"><strong>GET</strong> /queue/dashboard - Dashboard visual da fila</div>
            <div class="endpoint"><strong>GET</strong> /queue/status - Status detalhado da fila</div>
            <div class="endpoint"><strong>GET</strong> /queue/messages/pending - Mensagens pendentes</div>
            <div class="endpoint"><strong>GET</strong> /queue/messages/processing - Mensagens em processamento</div>
            <div class="endpoint"><strong>GET</strong> /queue/messages/dead-letter - Dead letter queue</div>
            <div class="endpoint"><strong>POST</strong> /queue/messages/priority - Enviar mensagem prioritária</div>
            <div class="endpoint"><strong>WS</strong> /queue/ws - WebSocket para updates real-time</div>
            
            <h4>🤖 Core Endpoints</h4>
            <div class="endpoint"><strong>POST</strong> /webhook/whatsapp - Webhook do Twilio (Queue-enabled)</div>
            <div class="endpoint"><strong>GET</strong> /health - Status do sistema</div>
            <div class="endpoint"><strong>GET</strong> /status - Status detalhado com queue info</div>
            <div class="endpoint"><strong>GET</strong> /llm/status - Status do LLM</div>
            <div class="endpoint"><strong>POST</strong> /llm/test - Teste direto do LLM</div>
            <div class="endpoint"><strong>POST</strong> /send - Enviar mensagem</div>
            
            <div style="text-align: center; margin-top: 40px;">
                <a href="/queue/dashboard" class="monitor-link">
                    📊 Abrir Queue Dashboard
                </a>
            </div>
            
            <div style="margin-top: 40px; padding-top: 30px; border-top: 1px solid rgba(255,255,255,0.2); text-align: center; opacity: 0.7;">
                <p>Powered by LangChain + LangGraph + Ollama + Redis Queue</p>
                <p>Version 2.1.0 - Queue Management Edition</p>
            </div>
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
    """Webhook do WhatsApp - Com Sistema de Queue"""
    try:
        logger.info(f"=== WEBHOOK RECEBIDO (QUEUE) ===")
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
        
        # Processa via sistema de queue
        if whatsapp_service:
            logger.info("Adicionando mensagem na fila...")
            twiml_response = await whatsapp_service.process_incoming_webhook(webhook_data)
            logger.info("Mensagem adicionada à fila com sucesso")
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
        error_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>🤖 Sistema em manutenção. Tente novamente em instantes.</Message>
</Response>'''
        return Response(
            content=error_response,
            media_type="application/xml"
        )

@app.get("/health")
async def health_check():
    """Health check do sistema com info da queue"""
    try:
        health_status = {
            "status": "healthy", 
            "service": "jarvis-llm-queue",
            "version": "2.1.0",
            "webhook": "ready",
            "timestamp": datetime.now().isoformat()
        }
        
        # Status da queue
        if whatsapp_service and whatsapp_service.message_queue:
            queue_status = await whatsapp_service.message_queue.get_queue_status()
            health_status["queue"] = {
                "pending": queue_status.get("pending", 0),
                "processing": queue_status.get("processing", 0),
                "healthy": queue_status.get("circuit_breaker", {}).get("state") != "open"
            }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/status")
async def detailed_status():
    """Status detalhado do sistema com queue info"""
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
    """Status específico do LLM com rate limiting info"""
    try:
        if whatsapp_service and whatsapp_service.llm_service:
            llm_status = await whatsapp_service.llm_service.get_service_status()
            
            # Adiciona info de rate limiting
            if whatsapp_service.message_queue:
                rate_limiter = whatsapp_service.message_queue.rate_limiter
                llm_status["rate_limiting"] = {
                    "current_requests": len(rate_limiter.requests),
                    "max_requests_per_minute": rate_limiter.max_requests,
                    "available": rate_limiter.max_requests - len(rate_limiter.requests)
                }
            
            return llm_status
        else:
            return {"status": "not_initialized", "message": "LLM service not ready"}
    except Exception as e:
        logger.error(f"LLM status error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/llm/test")
async def test_llm(data: Dict[str, Any]):
    """Teste direto do LLM (bypassa queue para testes)"""
    try:
        prompt = data.get("prompt", "Olá, teste do LLM")
        use_queue = data.get("use_queue", False)
        
        if not whatsapp_service or not whatsapp_service.llm_service:
            raise HTTPException(status_code=503, detail="LLM service not available")
        
        if use_queue:
            # Adiciona na fila como teste
            success = await whatsapp_service.process_priority_message(
                phone_number="test_user",
                message=prompt,
                priority=10
            )
            return {
                "status": "queued" if success else "failed",
                "prompt": prompt,
                "message": "Test message added to queue" if success else "Failed to queue"
            }
        else:
            # Teste direto (sem queue)
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
    """Envia mensagem via WhatsApp (com opção de prioridade)"""
    try:
        phone_number = data.get("phone_number")
        message = data.get("message")
        media_url = data.get("media_url")
        use_queue = data.get("use_queue", False)
        priority = data.get("priority", 5)
        
        if not phone_number or not message:
            raise HTTPException(status_code=400, detail="phone_number and message are required")
        
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="WhatsApp service not available")
        
        if use_queue:
            # Adiciona na fila
            success = await whatsapp_service.process_priority_message(
                phone_number, message, priority
            )
            return {
                "status": "queued" if success else "failed",
                "to": phone_number,
                "priority": priority
            }
        else:
            # Envio direto
            success = await whatsapp_service.send_message(phone_number, message, media_url)
            
            if success:
                return {"status": "sent", "to": phone_number, "message": message}
            else:
                raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/position/{phone_number}")
async def get_queue_position(phone_number: str):
    """Obtém posição do usuário na fila"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        position = await whatsapp_service.get_user_queue_position(phone_number)
        
        return {
            "phone_number": phone_number,
            "position": position,
            "estimated_wait": f"{(position or 0) * 2} minutos"  # Estimativa simples
        }
        
    except Exception as e:
        logger.error(f"Queue position error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )