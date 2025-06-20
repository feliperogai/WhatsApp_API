import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.metrics_service import metrics_service

logger = logging.getLogger(__name__)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware para coletar métricas automaticamente"""
    
    def __init__(self, app, collect_detailed_metrics: bool = True):
        super().__init__(app)
        self.collect_detailed_metrics = collect_detailed_metrics
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Ignora endpoints de métricas para evitar recursão
        if request.url.path in ["/metrics", "/health"]:
            return await call_next(request)
        
        start_time = time.time()
        
        # Coleta informações da requisição
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        
        try:
            # Executa a requisição
            response = await call_next(request)
            
            # Calcula tempo de resposta
            processing_time = time.time() - start_time
            
            # Registra métricas básicas
            if self.collect_detailed_metrics:
                self._record_request_metrics(
                    method, path, response.status_code, processing_time, user_agent
                )
            
            # Adiciona headers de métricas
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}"
            response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Registra erro
            if self.collect_detailed_metrics:
                self._record_error_metrics(method, path, str(e), processing_time)
            
            logger.error(f"Request error on {method} {path}: {e}")
            raise
    
    def _record_request_metrics(
        self, 
        method: str, 
        path: str, 
        status_code: int, 
        processing_time: float, 
        user_agent: str
    ):
        """Registra métricas de requisição"""
        
        # Registra evento geral
        event_type = f"http_{method.lower()}"
        metrics_service.record_conversation_event(event_type)
        
        # Registra tempos de resposta por endpoint
        if path.startswith("/webhook/whatsapp"):
            metrics_service.record_conversation_event("webhook_received")
        elif path.startswith("/send"):
            metrics_service.record_conversation_event("message_sent")
        elif path.startswith("/analyze"):
            metrics_service.record_conversation_event("conversation_analyzed")
        elif path.startswith("/llm"):
            metrics_service.record_conversation_event("llm_direct_request")
        
        # Registra status codes
        if 200 <= status_code < 300:
            metrics_service.record_conversation_event("http_success")
        elif 400 <= status_code < 500:
            metrics_service.record_conversation_event("http_client_error")
        elif 500 <= status_code < 600:
            metrics_service.record_conversation_event("http_server_error")
    
    def _record_error_metrics(
        self, 
        method: str, 
        path: str, 
        error: str, 
        processing_time: float
    ):
        """Registra métricas de erro"""
        metrics_service.record_conversation_event("http_exception")
        logger.warning(f"HTTP Exception: {method} {path} - {error} ({processing_time:.3f}s)")

class LLMMetricsCollector:
    """Coletor de métricas específicas para LLM"""
    
    @staticmethod
    def record_llm_interaction(
        agent_id: str,
        agent_name: str,
        llm_response_time: float,
        agent_processing_time: float,
        confidence: float,
        tokens_used: int = 0,
        success: bool = True,
        model_name: str = "unknown"
    ):
        """Registra uma interação completa LLM + Agente"""
        
        # Registra métricas LLM
        metrics_service.record_llm_request(
            response_time=llm_response_time,
            confidence=confidence,
            tokens=tokens_used,
            success=success,
            model=model_name
        )
        
        # Registra métricas do agente
        metrics_service.record_agent_activation(
            agent_id=agent_id,
            agent_name=agent_name,
            processing_time=agent_processing_time,
            success=success
        )
        
        logger.debug(
            f"LLM interaction recorded: {agent_id} "
            f"(LLM: {llm_response_time:.2f}s, Agent: {agent_processing_time:.2f}s, "
            f"Confidence: {confidence:.2f})"
        )
    
    @staticmethod
    def record_conversation_flow(phone_number: str, flow_step: str):
        """Registra fluxo de conversa"""
        metrics_service.record_conversation_event(f"flow_{flow_step}", phone_number)
    
    @staticmethod
    def record_session_event(phone_number: str, event: str):
        """Registra eventos de sessão"""
        valid_events = ["session_start", "session_end", "session_reset", "session_timeout"]
        
        if event in valid_events:
            metrics_service.record_conversation_event(event, phone_number)
        else:
            logger.warning(f"Invalid session event: {event}")

# Instância global do coletor
llm_metrics = LLMMetricsCollector()

# Endpoint para métricas Prometheus
async def get_prometheus_metrics(request: Request) -> PlainTextResponse:
    """Endpoint para métricas no formato Prometheus"""
    try:
        metrics_text = metrics_service.get_prometheus_metrics()
        return PlainTextResponse(
            content=metrics_text,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        return PlainTextResponse(
            content="# Error generating metrics\n",
            status_code=500
        )

# Endpoint para métricas detalhadas JSON
async def get_detailed_metrics(request: Request) -> dict:
    """Endpoint para métricas detalhadas em JSON"""
    try:
        return metrics_service.get_metrics_summary()
    except Exception as e:
        logger.error(f"Error generating detailed metrics: {e}")
        return {"error": str(e)}

# Endpoint para métricas de um agente específico
async def get_agent_metrics(agent_id: str) -> dict:
    """Endpoint para métricas de um agente específico"""
    try:
        agent_stats = metrics_service.get_detailed_agent_stats(agent_id)
        if agent_stats:
            return agent_stats
        else:
            return {"error": f"Agent {agent_id} not found"}
    except Exception as e:
        logger.error(f"Error getting agent metrics for {agent_id}: {e}")
        return {"error": str(e)}