import asyncio
import time
from typing import Dict, Optional
from collections import deque, defaultdict
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now
            
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def wait_for_tokens(self, tokens: int = 1) -> float:
        while not await self.consume(tokens):
            needed = tokens - self.tokens
            wait_time = needed / self.rate
            await asyncio.sleep(wait_time)
            return wait_time
        return 0

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, half_open_requests: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0
        self.state = "closed"
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        async with self._lock:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half_open"
                    self.success_count = 0
                    logger.info("Circuit breaker: half-open")
                else:
                    raise Exception("Circuit breaker is open")
            
            try:
                result = await func(*args, **kwargs)
                
                if self.state == "half_open":
                    self.success_count += 1
                    if self.success_count >= self.half_open_requests:
                        self.state = "closed"
                        self.failure_count = 0
                        logger.info("Circuit breaker: closed")
                elif self.state == "closed":
                    self.failure_count = max(0, self.failure_count - 1)
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.state == "half_open" or self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.error(f"Circuit breaker: open after {self.failure_count} failures")
                
                raise e
    
    def get_state(self) -> Dict[str, any]:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "can_attempt": self.state != "open" or (time.time() - self.last_failure_time > self.recovery_timeout)
        }

class RateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis,
        global_rate: float = 10/60,  # 10 requests per minute
        global_burst: int = 5,
        user_rate: float = 3/60,      # 3 requests per minute per user
        user_burst: int = 2
    ):
        self.redis = redis_client
        self.global_bucket = TokenBucket(global_rate, global_burst)
        self.user_buckets: Dict[str, TokenBucket] = {}
        self.user_rate = user_rate
        self.user_burst = user_burst
        self._user_buckets_lock = asyncio.Lock()
        
        self.request_times = deque(maxlen=1000)
        self.user_request_times = defaultdict(lambda: deque(maxlen=100))
        
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    async def acquire(self, user_id: str, priority: int = 5) -> bool:
        priority_multiplier = max(0.5, min(2.0, priority / 5))
        
        if not await self.global_bucket.consume():
            return False
        
        async with self._user_buckets_lock:
            if user_id not in self.user_buckets:
                self.user_buckets[user_id] = TokenBucket(self.user_rate, self.user_burst)
            
            user_bucket = self.user_buckets[user_id]
        
        if not await user_bucket.consume(1 / priority_multiplier):
            await self.global_bucket.consume(-1)
            return False
        
        self.request_times.append(time.time())
        self.user_request_times[user_id].append(time.time())
        
        return True
    
    async def wait_and_acquire(self, user_id: str, priority: int = 5) -> float:
        start_time = time.time()
        
        global_wait = await self.global_bucket.wait_for_tokens()
        
        async with self._user_buckets_lock:
            if user_id not in self.user_buckets:
                self.user_buckets[user_id] = TokenBucket(self.user_rate, self.user_burst)
            user_bucket = self.user_buckets[user_id]
        
        priority_multiplier = max(0.5, min(2.0, priority / 5))
        user_wait = await user_bucket.wait_for_tokens(1 / priority_multiplier)
        
        total_wait = time.time() - start_time
        
        self.request_times.append(time.time())
        self.user_request_times[user_id].append(time.time())
        
        logger.info(f"Rate limit wait for {user_id}: {total_wait:.2f}s (priority: {priority})")
        return total_wait
    
    async def check_circuit_breaker(self, func, *args, **kwargs):
        return await self.circuit_breaker.call(func, *args, **kwargs)
    
    def get_current_rate(self) -> Dict[str, float]:
        now = time.time()
        minute_ago = now - 60
        
        global_rpm = sum(1 for t in self.request_times if t > minute_ago)
        
        user_rates = {}
        for user_id, times in self.user_request_times.items():
            user_rpm = sum(1 for t in times if t > minute_ago)
            if user_rpm > 0:
                user_rates[user_id] = user_rpm
        
        return {
            "global_rpm": global_rpm,
            "user_rates": user_rates,
            "circuit_breaker": self.circuit_breaker.get_state()
        }
    
    async def cleanup_old_buckets(self):
        async with self._user_buckets_lock:
            now = time.time()
            inactive_users = []
            
            for user_id, bucket in self.user_buckets.items():
                if now - bucket.last_update > 3600:
                    inactive_users.append(user_id)
            
            for user_id in inactive_users:
                del self.user_buckets[user_id]
                if user_id in self.user_request_times:
                    del self.user_request_times[user_id]
            
            if inactive_users:
                logger.info(f"Cleaned up {len(inactive_users)} inactive user buckets")

class AdaptiveRateLimiter(RateLimiter):
    def __init__(self, redis_client: redis.Redis, **kwargs):
        super().__init__(redis_client, **kwargs)
        self.performance_history = deque(maxlen=100)
        self.adjustment_interval = 300
        self.last_adjustment = time.time()
        
        self.min_global_rate = 5/60
        self.max_global_rate = 30/60
        self.target_latency = 2.0
    
    async def record_performance(self, latency: float, success: bool):
        self.performance_history.append({
            "timestamp": time.time(),
            "latency": latency,
            "success": success
        })
        
        if time.time() - self.last_adjustment > self.adjustment_interval:
            await self._adjust_rates()
    
    async def _adjust_rates(self):
        if len(self.performance_history) < 10:
            return
        
        recent = list(self.performance_history)[-20:]
        avg_latency = sum(p["latency"] for p in recent) / len(recent)
        success_rate = sum(1 for p in recent if p["success"]) / len(recent)
        
        current_rate = self.global_bucket.rate
        
        if avg_latency > self.target_latency * 1.5 or success_rate < 0.8:
            new_rate = max(self.min_global_rate, current_rate * 0.8)
        elif avg_latency < self.target_latency * 0.7 and success_rate > 0.95:
            new_rate = min(self.max_global_rate, current_rate * 1.2)
        else:
            new_rate = current_rate
        
        if new_rate != current_rate:
            self.global_bucket.rate = new_rate
            logger.info(f"Adjusted global rate: {current_rate*60:.1f} → {new_rate*60:.1f} rpm")
        
        self.last_adjustment = time.time()