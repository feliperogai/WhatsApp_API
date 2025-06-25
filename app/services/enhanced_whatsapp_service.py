import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from app.services.twilio_service import TwilioService
from app.models.message import WhatsAppMessage, MessageType, MessageStatus
from app.core.langgraph_orchestrator import LangGraphOrchestrator
from app.core.session_manager import SessionManager
from app.services.llm_service import LLMService
from app.services.message_queue import PriorityMessageQueue, QueueMessage, MessageStatus as QueueStatus
from app.services.metrics_service import metrics_service
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class EnhancedWhatsAppService:
    """Serviço WhatsApp aprimorado com sistema de fila"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.twilio_service = TwilioService()
        self.llm_service = LLMService()
        self.orchestrator = None
        self.message_queue = None
        self.redis_client = None
        
        # Configurações
        self.max_concurrent_llm = 3  # Máximo de requisições LLM simultâneas
        self.queue_check_interval = 1  # Intervalo para verificar fila (segundos)
        
        # Controle de processamento
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_llm)
        self.is_processing = False
        self.processing_task = None
    
    async def initialize(self):
        """Inicializa todos os serviços"""
        try:
            # Inicializa Redis
            from app.config.settings import settings
            self.redis_client = redis.from_url(settings.redis_url)
            await self.redis_client.ping()
            
            # Inicializa serviços base
            await self.session_manager.initialize()
            await self.llm_service.initialize()
            
            # Inicializa orquestrador LangGraph
            self.orchestrator = LangGraphOrchestrator(self.session_manager, self.llm_service)
            
            # Inicializa sistema de fila
            self.message_queue = PriorityMessageQueue(self.redis_client)
            await self.message_queue.start_workers(self._process_queued_message)
            
            # Inicia processamento da fila
            self.is_processing = True
            self.processing_task = asyncio.create_task(self._process_queue_loop())
            
            # Inicia limpeza de mensagens antigas
            asyncio.create_task(self._cleanup_old_messages())
            
            logger.info("Enhanced WhatsApp service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Enhanced WhatsApp service: {e}")
            raise
    
    async def process_incoming_webhook(self, webhook_data: Dict[str, Any]) -> str:
        """Processa webhook adicionando mensagem na fila"""
        try:
            # Valida webhook
            if not await self.twilio_service.validate_webhook(webhook_data):
                logger.warning("Invalid webhook received")
                return self.twilio_service.create_webhook_response("Erro de validação")
            
            # Extrai dados
            from_number = self.twilio_service.extract_phone_number(webhook_data.get('From', ''))
            message_body = webhook_data.get('Body', '')
            message_sid = webhook_data.get('MessageSid', '')
            
            # Registra métrica
            metrics_service.record_conversation_event("webhook_received", from_number)
            
            # Verifica se usuário não está spamming
            if await self._is_user_rate_limited(from_number):
                logger.warning(f"User {from_number} is rate limited")
                return self.twilio_service.create_webhook_response(
                    "⚠️ Você enviou muitas mensagens. Por favor, aguarde um momento."
                )
            
            # Adiciona mensagem na fila com metadados
            metadata = {
                "message_sid": message_sid,
                "webhook_data": webhook_data,
                "received_at": datetime.now().isoformat()
            }
            
            success = await self.message_queue.enqueue_with_rules(
                phone_number=from_number,
                content=message_body,
                metadata=metadata
            )
            
            if success:
                # Resposta imediata de confirmação
                queue_status = await self.message_queue.get_queue_status()
                position = queue_status.get("pending", 0)
                
                if position > 5:
                    response = f"📨 Mensagem recebida! Você é o {position}º na fila. Aguarde..."
                else:
                    response = "📨 Mensagem recebida! Processando..."
                
                logger.info(f"Message from {from_number} queued successfully")
            else:
                response = "❌ Sistema sobrecarregado. Tente novamente em alguns minutos."
                logger.error(f"Failed to queue message from {from_number}")
            
            return self.twilio_service.create_webhook_response(response)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            error_response = "🤖 Ops! Erro temporário. Tente novamente."
            return self.twilio_service.create_webhook_response(error_response)
    
    async def _process_queued_message(self, queue_message: QueueMessage):
        """Processa mensagem da fila usando LLM"""
        async with self.processing_semaphore:
            try:
                start_time = datetime.now()
                phone_number = queue_message.phone_number
                
                # Registra início do processamento
                metrics_service.record_conversation_event("processing_start", phone_number)
                
                # Cria objeto de mensagem WhatsApp
                message = WhatsAppMessage(
                    message_id=queue_message.metadata.get("message_sid", queue_message.id),
                    from_number=phone_number,
                    to_number=self.twilio_service.phone_number,
                    body=queue_message.content,
                    message_type=MessageType.TEXT,
                    status=MessageStatus.PROCESSING
                )
                
                # Processa através do orchestrator
                logger.info(f"Processing message {queue_message.id} through LLM...")
                response = await self.orchestrator.process_message(message)
                
                # Calcula tempo de processamento
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Registra métricas
                metrics_service.record_llm_request(
                    response_time=processing_time,
                    confidence=response.confidence,
                    success=True,
                    model=self.llm_service.model
                )
                
                # Envia resposta via WhatsApp
                success = await self.send_message(
                    phone_number,
                    response.response_text,
                    response.metadata.get("media_url")
                )
                
                if success:
                    logger.info(f"Message {queue_message.id} processed successfully in {processing_time:.2f}s")
                    metrics_service.record_conversation_event("processing_complete", phone_number)
                else:
                    raise Exception("Failed to send WhatsApp response")
                
            except Exception as e:
                logger.error(f"Error processing queued message {queue_message.id}: {e}")
                metrics_service.record_conversation_event("processing_error", phone_number)
                
                # Envia mensagem de erro ao usuário
                await self.send_message(
                    phone_number,
                    "❌ Desculpe, ocorreu um erro ao processar sua mensagem. Nossa equipe foi notificada."
                )
                
                raise  # Re-raise para o sistema de retry
    
    async def _process_queue_loop(self):
        """Loop principal de processamento da fila"""
        logger.info("Queue processing loop started")
        
        while self.is_processing:
            try:
                # Verifica status da fila
                status = await self.message_queue.get_queue_status()
                
                # Log de status a cada 30 segundos
                if int(datetime.now().timestamp()) % 30 == 0:
                    logger.info(f"Queue status: {status}")
                
                # Aguarda próximo ciclo
                await asyncio.sleep(self.queue_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("Queue processing loop stopped")
    
    async def _is_user_rate_limited(self, phone_number: str) -> bool:
        """Verifica se usuário está no limite de rate"""
        try:
            # Chave para rate limiting por usuário
            rate_key = f"rate_limit:{phone_number}"
            
            # Incrementa contador
            count = await self.redis_client.incr(rate_key)
            
            # Define TTL se for primeira mensagem
            if count == 1:
                await self.redis_client.expire(rate_key, 60)  # 1 minuto
            
            # Limite: 10 mensagens por minuto
            return count > 10
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    async def _cleanup_old_messages(self):
        """Limpa mensagens antigas da fila"""
        while self.is_processing:
            try:
                # Processa dead letter queue a cada hora
                await asyncio.sleep(3600)
                
                dead_letters = await self.message_queue.process_dead_letter_queue()
                
                if dead_letters:
                    logger.info(f"Found {len(dead_letters)} messages in dead letter queue")
                    
                    # Notifica administradores sobre mensagens falhadas
                    for msg in dead_letters[:5]:  # Primeiras 5 mensagens
                        logger.error(f"Dead letter: {msg.phone_number} - {msg.error}")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    async def send_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> bool:
        """Envia mensagem via Twilio com retry"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                success = await self.twilio_service.send_message(to_number, message, media_url)
                
                if success:
                    metrics_service.record_conversation_event("message_sent", to_number)
                    return True
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed to send message: {e}")
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        metrics_service.record_conversation_event("message_send_failed", to_number)
        return False
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Status completo do serviço com informações da fila"""
        try:
            base_status = {
                "status": "healthy",
                "service_type": "enhanced-queue-based",
                "timestamp": datetime.now().isoformat()
            }
            
            # Status da fila
            queue_status = await self.message_queue.get_queue_status()
            
            # Status dos componentes
            llm_status = await self.llm_service.get_service_status()
            active_sessions = await self.session_manager.get_active_sessions_count()
            
            return {
                **base_status,
                "queue": queue_status,
                "components": {
                    "session_manager": {
                        "active_sessions": active_sessions,
                        "status": "online"
                    },
                    "llm_service": llm_status,
                    "processing": {
                        "concurrent_limit": self.max_concurrent_llm,
                        "semaphore_available": self.processing_semaphore._value
                    }
                },
                "performance": {
                    "queue_processing": self.is_processing,
                    "workers_active": queue_status.get("workers", {}).get("active", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def process_priority_message(self, phone_number: str, message: str, priority: int = 10):
        """Processa mensagem com prioridade alta (para casos especiais)"""
        try:
            queue_message = QueueMessage(
                id=f"priority_{datetime.now().timestamp()}",
                phone_number=phone_number,
                content=message,
                priority=priority,
                metadata={"is_priority": True}
            )
            
            # Adiciona na fila com alta prioridade
            success = await self.message_queue.enqueue(queue_message)
            
            if success:
                logger.info(f"Priority message for {phone_number} queued")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing priority message: {e}")
            return False
    
    async def get_user_queue_position(self, phone_number: str) -> Optional[int]:
        """Obtém posição do usuário na fila"""
        try:
            # Implementar lógica para encontrar posição na fila
            # Por enquanto, retorna estimativa baseada no total
            status = await self.message_queue.get_queue_status()
            return status.get("pending", 0)
            
        except Exception as e:
            logger.error(f"Error getting queue position: {e}")
            return None
    
    async def cleanup(self):
        """Limpa recursos"""
        logger.info("Cleaning up Enhanced WhatsApp service...")
        
        self.is_processing = False
        
        # Para workers da fila
        if self.message_queue:
            await self.message_queue.stop_workers()
        
        # Cancela task de processamento
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # Limpa outros serviços
        if self.llm_service:
            await self.llm_service.cleanup()
        
        # Fecha Redis
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Enhanced WhatsApp service cleaned up")