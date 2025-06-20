import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
from collections import deque
import time

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """Prioridades de mensagem"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10

class MessageStatus(Enum):
    """Status da mensagem na fila"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"

@dataclass
class QueueMessage:
    """Mensagem na fila"""
    id: str
    phone_number: str
    content: str
    priority: int = MessagePriority.NORMAL.value
    created_at: datetime = None
    attempts: int = 0
    max_attempts: int = 3
    status: str = MessageStatus.PENDING.value
    metadata: Dict[str, Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

class RateLimiter:
    """Rate limiter para controlar requisições ao LLM"""
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Tenta adquirir permissão para fazer requisição"""
        async with self._lock:
            now = time.time()
            
            # Remove requisições antigas
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()
            
            # Verifica se pode fazer requisição
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    async def wait_if_needed(self):
        """Espera se necessário antes de fazer requisição"""
        while not await self.acquire():
            # Calcula tempo de espera
            if self.requests:
                oldest = self.requests[0]
                wait_time = (oldest + self.window_seconds) - time.time()
                if wait_time > 0:
                    logger.info(f"Rate limit atingido, aguardando {wait_time:.1f}s")
                    await asyncio.sleep(wait_time + 0.1)
            else:
                await asyncio.sleep(1)

class CircuitBreaker:
    """Circuit breaker para proteger o LLM"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Executa função com proteção de circuit breaker"""
        async with self._lock:
            if self.state == "open":
                if self.last_failure_time and \
                   (datetime.now() - self.last_failure_time).seconds > self.recovery_timeout:
                    self.state = "half-open"
                    logger.info("Circuit breaker: transição para half-open")
                else:
                    raise Exception("Circuit breaker está aberto")
            
            try:
                result = await func(*args, **kwargs)
                
                if self.state == "half-open":
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info("Circuit breaker: recuperado, voltando para closed")
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = datetime.now()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.error(f"Circuit breaker: aberto após {self.failure_count} falhas")
                
                raise e

class MessageQueue:
    """Sistema de fila de mensagens com Redis"""
    
    def __init__(self, redis_client: redis.Redis, queue_name: str = "jarvis_messages"):
        self.redis = redis_client
        self.queue_name = queue_name
        self.processing_queue = f"{queue_name}:processing"
        self.dead_letter_queue = f"{queue_name}:dead_letter"
        self.metrics_key = f"{queue_name}:metrics"
        
        # Rate limiter: 5 requisições por minuto para LLM local
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        # Workers
        self.workers: List[asyncio.Task] = []
        self.max_workers = 3
        self.is_running = False
    
    async def enqueue(self, message: QueueMessage) -> bool:
        """Adiciona mensagem na fila"""
        try:
            # Serializa mensagem
            message_data = json.dumps(message.to_dict())
            
            # Adiciona na fila com prioridade
            score = -message.priority  # Negativo para maior prioridade primeiro
            await self.redis.zadd(self.queue_name, {message_data: score})
            
            # Atualiza métricas
            await self._increment_metric("messages_enqueued")
            
            logger.info(f"Mensagem {message.id} adicionada à fila")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar mensagem à fila: {e}")
            return False
    
    async def dequeue(self) -> Optional[QueueMessage]:
        """Remove mensagem da fila para processamento"""
        try:
            # Pega mensagem com maior prioridade
            result = await self.redis.zpopmax(self.queue_name)
            
            if not result:
                return None
            
            message_data, score = result[0]
            message = QueueMessage.from_dict(json.loads(message_data))
            
            # Move para fila de processamento
            message.status = MessageStatus.PROCESSING.value
            await self.redis.hset(
                self.processing_queue,
                message.id,
                json.dumps(message.to_dict())
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Erro ao remover mensagem da fila: {e}")
            return None
    
    async def complete_message(self, message_id: str):
        """Marca mensagem como completa"""
        try:
            # Remove da fila de processamento
            await self.redis.hdel(self.processing_queue, message_id)
            
            # Atualiza métricas
            await self._increment_metric("messages_completed")
            
            logger.info(f"Mensagem {message_id} completada")
            
        except Exception as e:
            logger.error(f"Erro ao completar mensagem: {e}")
    
    async def retry_message(self, message: QueueMessage, error: str):
        """Recoloca mensagem na fila para retry"""
        try:
            message.attempts += 1
            message.error = error
            message.status = MessageStatus.RETRYING.value
            
            # Remove da fila de processamento
            await self.redis.hdel(self.processing_queue, message.id)
            
            if message.attempts >= message.max_attempts:
                # Move para dead letter
                await self._move_to_dead_letter(message)
            else:
                # Recoloca na fila com delay
                delay_seconds = message.attempts * 10  # Backoff exponencial
                message.priority = MessagePriority.LOW.value  # Reduz prioridade
                
                await asyncio.sleep(delay_seconds)
                await self.enqueue(message)
                
                logger.warning(f"Mensagem {message.id} recolocada na fila (tentativa {message.attempts})")
            
        except Exception as e:
            logger.error(f"Erro ao fazer retry da mensagem: {e}")
    
    async def _move_to_dead_letter(self, message: QueueMessage):
        """Move mensagem para dead letter queue"""
        try:
            message.status = MessageStatus.DEAD_LETTER.value
            await self.redis.hset(
                self.dead_letter_queue,
                message.id,
                json.dumps(message.to_dict())
            )
            
            await self._increment_metric("messages_dead_letter")
            
            logger.error(f"Mensagem {message.id} movida para dead letter após {message.attempts} tentativas")
            
        except Exception as e:
            logger.error(f"Erro ao mover mensagem para dead letter: {e}")
    
    async def process_dead_letter_queue(self) -> List[QueueMessage]:
        """Processa mensagens na dead letter queue"""
        try:
            messages = []
            dead_letters = await self.redis.hgetall(self.dead_letter_queue)
            
            for message_data in dead_letters.values():
                message = QueueMessage.from_dict(json.loads(message_data))
                messages.append(message)
            
            return messages
            
        except Exception as e:
            logger.error(f"Erro ao processar dead letter queue: {e}")
            return []
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Retorna status das filas"""
        try:
            pending_count = await self.redis.zcard(self.queue_name)
            processing_count = await self.redis.hlen(self.processing_queue)
            dead_letter_count = await self.redis.hlen(self.dead_letter_queue)
            
            # Métricas
            metrics = await self.redis.hgetall(self.metrics_key)
            metrics_decoded = {k.decode(): int(v) for k, v in metrics.items()}
            
            return {
                "pending": pending_count,
                "processing": processing_count,
                "dead_letter": dead_letter_count,
                "metrics": metrics_decoded,
                "workers": {
                    "active": len([w for w in self.workers if not w.done()]),
                    "max": self.max_workers
                },
                "rate_limiter": {
                    "current_requests": len(self.rate_limiter.requests),
                    "max_requests": self.rate_limiter.max_requests,
                    "window_seconds": self.rate_limiter.window_seconds
                },
                "circuit_breaker": {
                    "state": self.circuit_breaker.state,
                    "failure_count": self.circuit_breaker.failure_count
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter status da fila: {e}")
            return {}
    
    async def _increment_metric(self, metric: str):
        """Incrementa métrica"""
        try:
            await self.redis.hincrby(self.metrics_key, metric, 1)
        except Exception as e:
            logger.error(f"Erro ao incrementar métrica {metric}: {e}")
    
    async def start_workers(self, process_func: Callable):
        """Inicia workers para processar mensagens"""
        self.is_running = True
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i, process_func))
            self.workers.append(worker)
        
        logger.info(f"Iniciados {self.max_workers} workers")
    
    async def stop_workers(self):
        """Para todos os workers"""
        self.is_running = False
        
        # Cancela todos os workers
        for worker in self.workers:
            worker.cancel()
        
        # Aguarda conclusão
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Workers parados")
    
    async def _worker(self, worker_id: int, process_func: Callable):
        """Worker que processa mensagens da fila"""
        logger.info(f"Worker {worker_id} iniciado")
        
        while self.is_running:
            try:
                # Pega mensagem da fila
                message = await self.dequeue()
                
                if not message:
                    # Fila vazia, aguarda
                    await asyncio.sleep(1)
                    continue
                
                logger.info(f"Worker {worker_id} processando mensagem {message.id}")
                
                # Aplica rate limiting
                await self.rate_limiter.wait_if_needed()
                
                # Processa com circuit breaker
                try:
                    await self.circuit_breaker.call(process_func, message)
                    await self.complete_message(message.id)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem {message.id}: {e}")
                    await self.retry_message(message, str(e))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no worker {worker_id}: {e}")
                await asyncio.sleep(5)
        
        logger.info(f"Worker {worker_id} finalizado")

class PriorityMessageQueue(MessageQueue):
    """Fila com regras de prioridade avançadas"""
    
    async def enqueue_with_rules(self, phone_number: str, content: str, metadata: Dict[str, Any] = None) -> bool:
        """Adiciona mensagem aplicando regras de prioridade"""
        
        # Determina prioridade baseada em regras
        priority = self._determine_priority(content, metadata)
        
        # Cria mensagem
        message = QueueMessage(
            id=f"msg_{datetime.now().timestamp()}_{phone_number}",
            phone_number=phone_number,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )
        
        # Verifica limites por usuário
        user_count = await self._get_user_message_count(phone_number)
        if user_count >= 10:  # Máximo 10 mensagens por usuário na fila
            logger.warning(f"Usuário {phone_number} atingiu limite de mensagens na fila")
            return False
        
        return await self.enqueue(message)
    
    def _determine_priority(self, content: str, metadata: Dict[str, Any] = None) -> int:
        """Determina prioridade baseada no conteúdo"""
        content_lower = content.lower()
        
        # Palavras-chave críticas
        if any(word in content_lower for word in ["urgente", "emergência", "crítico", "parado"]):
            return MessagePriority.CRITICAL.value
        
        # Suporte técnico
        if any(word in content_lower for word in ["erro", "bug", "problema", "não funciona"]):
            return MessagePriority.HIGH.value
        
        # Consultas de dados
        if any(word in content_lower for word in ["relatório", "dados", "dashboard"]):
            return MessagePriority.NORMAL.value
        
        # Saudações e conversa geral
        return MessagePriority.LOW.value
    
    async def _get_user_message_count(self, phone_number: str) -> int:
        """Conta mensagens do usuário na fila"""
        try:
            # Pega todas as mensagens
            messages = await self.redis.zrange(self.queue_name, 0, -1)
            
            count = 0
            for msg_data in messages:
                msg = QueueMessage.from_dict(json.loads(msg_data))
                if msg.phone_number == phone_number:
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Erro ao contar mensagens do usuário: {e}")
            return 0