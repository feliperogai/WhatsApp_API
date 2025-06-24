import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from app.core.queue_manager import QueueItem, Priority
from app.core.rate_limiter import AdaptiveRateLimiter
from app.core.llm_pool import OptimizedLLMService, LLMResponse
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
    
    async def process(self, message: str, context: Dict[str, Any], llm_service: OptimizedLLMService) -> str:
        raise NotImplementedError

class GreetingAgent(Agent):
    def __init__(self):
        super().__init__("greeting", "Agente de Saudação")
    
    async def process(self, message: str, context: Dict[str, Any], llm_service: OptimizedLLMService) -> str:
        system_prompt = """Você é um assistente amigável. Responda saudações de forma cordial e ofereça ajuda.
Seja breve e direto. Máximo 3 linhas."""
        
        response = await llm_service.generate_response(
            message,
            system_prompt,
            session_id=context.get("session_id"),
            temperature=0.7,
            max_tokens=150
        )
        
        return response.content

class DataAgent(Agent):
    def __init__(self):
        super().__init__("data", "Agente de Dados")
    
    async def process(self, message: str, context: Dict[str, Any], llm_service: OptimizedLLMService) -> str:
        system_prompt = """Você é um analista de dados. Forneça informações sobre relatórios, métricas e KPIs.
Use dados fictícios realistas. Seja preciso e profissional. Formate com emojis quando apropriado."""
        
        response = await llm_service.generate_response(
            message,
            system_prompt,
            session_id=context.get("session_id"),
            temperature=0.5,
            max_tokens=300
        )
        
        return response.content

class SupportAgent(Agent):
    def __init__(self):
        super().__init__("support", "Agente de Suporte")
    
    async def process(self, message: str, context: Dict[str, Any], llm_service: OptimizedLLMService) -> str:
        system_prompt = """Você é um agente de suporte técnico. Ajude a resolver problemas e forneça soluções.
Seja empático e forneça passos claros. Use numeração para instruções."""
        
        response = await llm_service.generate_response(
            message,
            system_prompt,
            session_id=context.get("session_id"),
            temperature=0.6,
            max_tokens=400
        )
        
        return response.content

class GeneralAgent(Agent):
    def __init__(self):
        super().__init__("general", "Agente Geral")
    
    async def process(self, message: str, context: Dict[str, Any], llm_service: OptimizedLLMService) -> str:
        system_prompt = """Você é o assistente Jarvis. Responda de forma útil e profissional.
Se não souber, seja honesto. Máximo 5 linhas."""
        
        response = await llm_service.generate_response(
            message,
            system_prompt,
            session_id=context.get("session_id"),
            temperature=0.7,
            max_tokens=200
        )
        
        return response.content

class MessageProcessor:
    def __init__(
        self,
        llm_service: OptimizedLLMService,
        rate_limiter: AdaptiveRateLimiter,
        twilio_service: TwilioService,
        redis_client
    ):
        self.llm_service = llm_service
        self.rate_limiter = rate_limiter
        self.twilio_service = twilio_service
        self.redis = redis_client
        
        self.agents = {
            "greeting": GreetingAgent(),
            "data_query": DataAgent(),
            "support": SupportAgent(),
            "general": GeneralAgent()
        }
        
        self.session_key_prefix = "jarvis:session:"
        self.metrics_key = "jarvis:processor:metrics"
    
    async def process_message(self, item: QueueItem):
        start_time = datetime.now()
        session_id = f"{item.phone_number}_{datetime.now().strftime('%Y%m%d')}"
        
        try:
            await self.rate_limiter.wait_and_acquire(item.phone_number, item.priority)
            
            context = await self._get_session_context(session_id)
            context["phone_number"] = item.phone_number
            context["session_id"] = session_id
            
            intent_result = await self.rate_limiter.check_circuit_breaker(
                self.llm_service.classify_intent,
                item.content
            )
            
            intent = intent_result.get("intent", "general")
            confidence = intent_result.get("confidence", 0.5)
            
            logger.info(f"Intent classified: {intent} (confidence: {confidence})")
            
            agent = self.agents.get(intent, self.agents["general"])
            
            response_text = await self.rate_limiter.check_circuit_breaker(
                agent.process,
                item.content,
                context,
                self.llm_service
            )
            
            await self._update_session_context(session_id, {
                "last_intent": intent,
                "last_message": item.content,
                "last_response": response_text[:100],
                "last_interaction": datetime.now().isoformat()
            })
            
            success = await self.twilio_service.send_whatsapp_message(
                item.phone_number,
                response_text
            )
            
            if not success:
                raise Exception("Failed to send WhatsApp message")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            await self.rate_limiter.record_performance(processing_time, True)
            await self._record_metrics("success", processing_time, intent)
            
            logger.info(f"Message processed successfully in {processing_time:.2f}s")
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            
            await self.rate_limiter.record_performance(processing_time, False)
            await self._record_metrics("error", processing_time)
            
            logger.error(f"Error processing message: {e}")
            
            try:
                error_message = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
                await self.twilio_service.send_whatsapp_message(item.phone_number, error_message)
            except:
                pass
            
            raise
    
    async def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        key = self.session_key_prefix + session_id
        
        context_data = await self.redis.get(key)
        if context_data:
            return json.loads(context_data)
        
        return {
            "created_at": datetime.now().isoformat(),
            "message_count": 0
        }
    
    async def _update_session_context(self, session_id: str, updates: Dict[str, Any]):
        key = self.session_key_prefix + session_id
        
        context = await self._get_session_context(session_id)
        context.update(updates)
        context["message_count"] = context.get("message_count", 0) + 1
        
        await self.redis.setex(key, 86400, json.dumps(context))
    
    async def _record_metrics(self, status: str, processing_time: float, intent: str = None):
        await self.redis.hincrby(self.metrics_key, f"total_{status}", 1)
        
        if intent:
            await self.redis.hincrby(self.metrics_key, f"intent_{intent}", 1)
        
        await self.redis.hincrbyfloat(self.metrics_key, "total_processing_time", processing_time)
        await self.redis.hincrby(self.metrics_key, "total_processed", 1)
    
    async def get_metrics(self) -> Dict[str, Any]:
        metrics_data = await self.redis.hgetall(self.metrics_key)
        metrics = {k.decode(): float(v) for k, v in metrics_data.items()}
        
        total_processed = metrics.get("total_processed", 1)
        avg_processing_time = metrics.get("total_processing_time", 0) / total_processed if total_processed > 0 else 0
        
        return {
            "total_success": int(metrics.get("total_success", 0)),
            "total_error": int(metrics.get("total_error", 0)),
            "success_rate": metrics.get("total_success", 0) / total_processed if total_processed > 0 else 0,
            "avg_processing_time": avg_processing_time,
            "intents": {
                k.replace("intent_", ""): int(v) 
                for k, v in metrics.items() 
                if k.startswith("intent_")
            },
            "rate_limiter": self.rate_limiter.get_current_rate(),
            "llm_status": await self.llm_service.get_status()
        }

class MessageBatcher:
    def __init__(self, processor: MessageProcessor, batch_size: int = 5, batch_timeout: float = 2.0):
        self.processor = processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_batch: List[QueueItem] = []
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()
    
    async def add_to_batch(self, item: QueueItem):
        async with self.batch_lock:
            self.pending_batch.append(item)
            
            if len(self.pending_batch) >= self.batch_size:
                await self._process_batch()
            else:
                self.batch_event.set()
    
    async def batch_processor(self):
        while True:
            try:
                await asyncio.wait_for(self.batch_event.wait(), timeout=self.batch_timeout)
                self.batch_event.clear()
                
                async with self.batch_lock:
                    if self.pending_batch:
                        await self._process_batch()
                        
            except asyncio.TimeoutError:
                async with self.batch_lock:
                    if self.pending_batch:
                        await self._process_batch()
    
    async def _process_batch(self):
        if not self.pending_batch:
            return
        
        batch = self.pending_batch.copy()
        self.pending_batch.clear()
        
        logger.info(f"Processing batch of {len(batch)} messages")
        
        tasks = [self.processor.process_message(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error(f"Batch processing error for {item.id}: {result}")
        
        logger.info(f"Batch processing completed")