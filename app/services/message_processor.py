import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.core.queue_manager import QueueItem
from app.core.rate_limiter import AdaptiveRateLimiter
from app.services.twilio_service import TwilioService
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.models.message import WhatsAppMessage

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(
        self,
        orchestrator: LangGraphOrchestrator,
        twilio_service: TwilioService,
        rate_limiter: AdaptiveRateLimiter
    ):
        self.orchestrator = orchestrator
        self.twilio_service = twilio_service
        self.rate_limiter = rate_limiter
        
        self.metrics_key = "jarvis:processor:metrics"
    
    async def process_queued_message(self, item: QueueItem):
        """Processa mensagem da fila usando o orchestrator"""
        start_time = datetime.now()
        
        try:
            # Aguarda rate limiter
            await self.rate_limiter.wait_and_acquire(item.phone_number, item.priority)
            
            # Cria mensagem WhatsApp
            message = WhatsAppMessage(
                message_id=item.metadata.get("message_sid", item.id),
                from_number=item.phone_number,
                to_number=self.twilio_service.phone_number,
                body=item.content
            )
            
            # Processa através do orchestrator com circuit breaker
            response = await self.rate_limiter.check_circuit_breaker(
                self.orchestrator.process_message,
                message
            )
            
            logger.info(f"Response generated: {response.response_text[:100]}...")
            
            # Envia resposta via WhatsApp
            success = await self.twilio_service.send_message(
                item.phone_number,
                response.response_text
            )
            
            if not success:
                raise Exception("Failed to send WhatsApp message")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            await self.rate_limiter.record_performance(processing_time, True)
            await self._record_metrics("success", processing_time, response.agent_id)
            
            logger.info(f"✅ Message processed successfully in {processing_time:.2f}s")
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            
            await self.rate_limiter.record_performance(processing_time, False)
            await self._record_metrics("error", processing_time)
            
            logger.error(f"❌ Error processing message: {e}")
            
            # Tenta enviar mensagem de erro
            try:
                error_message = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
                await self.twilio_service.send_message(item.phone_number, error_message)
            except:
                pass
            
            raise
    
    async def _record_metrics(self, status: str, processing_time: float, agent_id: str = None):
        """Registra métricas no Redis"""
        try:
            # Por enquanto, apenas log
            logger.info(f"Metrics: status={status}, time={processing_time:.2f}s, agent={agent_id}")
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do processador"""
        return {
            "status": "active",
            "rate_limiter": self.rate_limiter.get_current_rate()
        }