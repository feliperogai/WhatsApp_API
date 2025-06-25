import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import redis.asyncio as redis
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class Priority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10

class QueueStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"

@dataclass
class QueueItem:
    id: str
    phone_number: str
    content: str
    priority: int = Priority.NORMAL.value
    created_at: float = None
    attempts: int = 0
    status: str = QueueStatus.PENDING.value
    metadata: Dict[str, Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.metadata is None:
            self.metadata = {}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> 'QueueItem':
        return cls(**json.loads(data))

class QueueManager:
    def __init__(
        self,
        redis_client: redis.Redis,
        max_queue_size: int = 1000,
        max_workers: int = 3,
        max_retries: int = 3,
        retry_delays: List[int] = None
    ):
        self.redis = redis_client
        self.max_queue_size = max_queue_size
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [5, 10, 30]
        
        self.queue_key = "jarvis:queue:messages"
        self.processing_key = "jarvis:queue:processing"
        self.dead_letter_key = "jarvis:queue:dead_letter"
        self.user_count_key = "jarvis:queue:user_count"
        self.metrics_key = "jarvis:queue:metrics"
        
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self._processor_func: Optional[Callable] = None
        self._user_message_counts = defaultdict(int)
        self._last_cleanup = time.time()
    
    async def enqueue(
        self,
        phone_number: str,
        content: str,
        priority: Priority = Priority.NORMAL,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        queue_size = await self.redis.zcard(self.queue_key)
        if queue_size >= self.max_queue_size:
            logger.warning(f"Queue full: {queue_size}/{self.max_queue_size}")
            return None
        
        user_count = await self._get_user_message_count(phone_number)
        if user_count >= 10:
            logger.warning(f"User {phone_number} has too many messages: {user_count}")
            return None
        
        item = QueueItem(
            id=f"{phone_number}_{int(time.time() * 1000000)}",
            phone_number=phone_number,
            content=content,
            priority=priority.value,
            metadata=metadata or {}
        )
        
        score = -item.priority * 1000000 + item.created_at
        await self.redis.zadd(self.queue_key, {item.to_json(): score})
        await self._increment_user_count(phone_number)
        await self._increment_metric("enqueued")
        
        logger.info(f"Enqueued message {item.id} with priority {priority.name}")
        return item.id
    
    async def dequeue(self) -> Optional[QueueItem]:
        result = await self.redis.zpopmax(self.queue_key)
        if not result:
            return None
        
        item_data, _ = result[0]
        item = QueueItem.from_json(item_data)
        
        item.status = QueueStatus.PROCESSING.value
        await self.redis.hset(self.processing_key, item.id, item.to_json())
        
        return item
    
    async def complete(self, item_id: str):
        item_data = await self.redis.hget(self.processing_key, item_id)
        if item_data:
            item = QueueItem.from_json(item_data)
            await self._decrement_user_count(item.phone_number)
            await self.redis.hdel(self.processing_key, item_id)
            await self._increment_metric("completed")
            logger.info(f"Completed message {item_id}")
    
    async def fail(self, item_id: str, error: str):
        item_data = await self.redis.hget(self.processing_key, item_id)
        if not item_data:
            return
        
        item = QueueItem.from_json(item_data)
        item.attempts += 1
        item.error = error
        
        await self.redis.hdel(self.processing_key, item_id)
        
        if item.attempts >= self.max_retries:
            item.status = QueueStatus.DEAD_LETTER.value
            await self.redis.hset(self.dead_letter_key, item_id, item.to_json())
            await self._decrement_user_count(item.phone_number)
            await self._increment_metric("dead_letter")
            logger.error(f"Message {item_id} moved to dead letter after {item.attempts} attempts")
        else:
            delay = self.retry_delays[min(item.attempts - 1, len(self.retry_delays) - 1)]
            await asyncio.sleep(delay)
            
            item.priority = max(1, item.priority - 2)
            score = -item.priority * 1000000 + time.time()
            await self.redis.zadd(self.queue_key, {item.to_json(): score})
            await self._increment_metric("retried")
            logger.warning(f"Retrying message {item_id} (attempt {item.attempts})")
    
    async def start_workers(self, processor_func: Callable):
        self._processor_func = processor_func
        self.is_running = True
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        
        asyncio.create_task(self._cleanup_loop())
        logger.info(f"Started {self.max_workers} queue workers")
    
    async def stop_workers(self):
        self.is_running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Stopped all queue workers")
    
    async def _worker(self, worker_id: int):
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                item = await self.dequeue()
                if not item:
                    await asyncio.sleep(0.1)
                    continue
                
                logger.info(f"Worker {worker_id} processing {item.id}")
                
                try:
                    await self._processor_func(item)
                    await self.complete(item.id)
                except Exception as e:
                    logger.error(f"Worker {worker_id} error processing {item.id}: {e}")
                    await self.fail(item.id, str(e))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} unexpected error: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_loop(self):
        while self.is_running:
            try:
                now = time.time()
                if now - self._last_cleanup > 300:
                    await self._cleanup_stale_processing()
                    self._last_cleanup = now
                
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _cleanup_stale_processing(self):
        processing = await self.redis.hgetall(self.processing_key)
        
        for item_id, item_data in processing.items():
            item = QueueItem.from_json(item_data)
            if time.time() - item.created_at > 300:
                await self.fail(item_id.decode(), "Processing timeout")
    
    async def _get_user_message_count(self, phone_number: str) -> int:
        count = await self.redis.hget(self.user_count_key, phone_number)
        return int(count) if count else 0
    
    async def _increment_user_count(self, phone_number: str):
        await self.redis.hincrby(self.user_count_key, phone_number, 1)
    
    async def _decrement_user_count(self, phone_number: str):
        count = await self._get_user_message_count(phone_number)
        if count > 0:
            await self.redis.hincrby(self.user_count_key, phone_number, -1)
    
    async def _increment_metric(self, metric: str):
        await self.redis.hincrby(self.metrics_key, metric, 1)
    
    async def get_status(self) -> Dict[str, Any]:
        pending = await self.redis.zcard(self.queue_key)
        processing = await self.redis.hlen(self.processing_key)
        dead_letter = await self.redis.hlen(self.dead_letter_key)
        
        metrics = await self.redis.hgetall(self.metrics_key)
        metrics_decoded = {k.decode(): int(v) for k, v in metrics.items()}
        
        return {
            "pending": pending,
            "processing": processing,
            "dead_letter": dead_letter,
            "workers": {
                "active": len([w for w in self.workers if not w.done()]),
                "total": self.max_workers
            },
            "metrics": metrics_decoded,
            "queue_health": "healthy" if pending < self.max_queue_size * 0.8 else "warning"
        }
    
    async def get_dead_letters(self, limit: int = 10) -> List[QueueItem]:
        dead_letters = await self.redis.hgetall(self.dead_letter_key)
        items = []
        
        for item_data in list(dead_letters.values())[:limit]:
            items.append(QueueItem.from_json(item_data))
        
        return sorted(items, key=lambda x: x.created_at, reverse=True)
    
    async def retry_dead_letter(self, item_id: str) -> bool:
        item_data = await self.redis.hget(self.dead_letter_key, item_id)
        if not item_data:
            return False
        
        item = QueueItem.from_json(item_data)
        item.attempts = 0
        item.status = QueueStatus.PENDING.value
        item.priority = Priority.HIGH.value
        
        await self.redis.hdel(self.dead_letter_key, item_id)
        
        score = -item.priority * 1000000 + time.time()
        await self.redis.zadd(self.queue_key, {item.to_json(): score})
        
        logger.info(f"Retried dead letter {item_id}")
        return True
    
    async def clear_dead_letters(self) -> int:
        count = await self.redis.hlen(self.dead_letter_key)
        await self.redis.delete(self.dead_letter_key)
        return count