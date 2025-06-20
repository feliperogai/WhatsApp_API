import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import redis.asyncio as redis

from app.services.message_queue import (
    MessageQueue, PriorityMessageQueue, QueueMessage,
    MessagePriority, MessageStatus, RateLimiter, CircuitBreaker
)
from app.services.llm_cache_service import LLMCacheService, CacheEntry
from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from app.services.monitoring_alerts import MonitoringService, AlertLevel, AlertType

# Fixtures
@pytest.fixture
async def redis_client():
    """Mock Redis client"""
    client = AsyncMock(spec=redis.Redis)
    # Setup default responses
    client.ping.return_value = True
    client.zadd.return_value = 1
    client.zpopmax.return_value = []
    client.hset.return_value = True
    client.hdel.return_value = 1
    client.hgetall.return_value = {}
    client.zcard.return_value = 0
    client.hlen.return_value = 0
    client.sadd.return_value = 1
    client.scard.return_value = 0
    client.smembers.return_value = set()
    return client

@pytest.fixture
async def message_queue(redis_client):
    """Message queue instance"""
    queue = MessageQueue(redis_client, "test_queue")
    return queue

@pytest.fixture
async def priority_queue(redis_client):
    """Priority message queue instance"""
    queue = PriorityMessageQueue(redis_client, "test_priority_queue")
    return queue

@pytest.fixture
def sample_message():
    """Sample queue message"""
    return QueueMessage(
        id="test_123",
        phone_number="+5511999999999",
        content="Test message",
        priority=MessagePriority.NORMAL.value,
        metadata={"test": True}
    )

class TestRateLimiter:
    """Testes para o Rate Limiter"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """Testa que rate limiter permite requisições dentro do limite"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        # Primeiras 3 requisições devem passar
        for i in range(3):
            assert await limiter.acquire() is True
        
        # 4ª requisição deve falhar
        assert await limiter.acquire() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self):
        """Testa que rate limiter reseta após janela de tempo"""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        
        # Primeira requisição passa
        assert await limiter.acquire() is True
        
        # Segunda falha
        assert await limiter.acquire() is False
        
        # Aguarda janela passar
        await asyncio.sleep(1.1)
        
        # Deve permitir novamente
        assert await limiter.acquire() is True
    
    @pytest.mark.asyncio
    async def test_wait_if_needed(self):
        """Testa função wait_if_needed"""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        
        # Primeira requisição
        await limiter.wait_if_needed()
        
        # Segunda requisição deve aguardar
        start_time = asyncio.get_event_loop().time()
        await limiter.wait_if_needed()
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Deve ter aguardado pelo menos 1 segundo
        assert elapsed >= 1.0

class TestCircuitBreaker:
    """Testes para o Circuit Breaker"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Testa que circuit breaker abre após falhas"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        async def failing_function():
            raise Exception("Test failure")
        
        # Primeiras falhas não abrem o circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_function)
        
        assert breaker.state == "closed"
        
        # 3ª falha deve abrir
        with pytest.raises(Exception):
            await breaker.call(failing_function)
        
        assert breaker.state == "open"
        
        # Próxima chamada deve falhar imediatamente
        with pytest.raises(Exception, match="Circuit breaker está aberto"):
            await breaker.call(failing_function)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Testa recuperação do circuit breaker"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        async def failing_function():
            raise Exception("Test failure")
        
        async def success_function():
            return "success"
        
        # Abre o circuit
        with pytest.raises(Exception):
            await breaker.call(failing_function)
        
        assert breaker.state == "open"
        
        # Aguarda recovery timeout
        await asyncio.sleep(1.1)
        
        # Próxima chamada bem-sucedida deve fechar o circuit
        result = await breaker.call(success_function)
        assert result == "success"
        assert breaker.state == "closed"

class TestMessageQueue:
    """Testes para a Message Queue"""
    
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, message_queue, sample_message, redis_client):
        """Testa enfileiramento e desenfileiramento básico"""
        # Mock Redis responses
        redis_client.zadd.return_value = 1
        redis_client.zpopmax.return_value = [(json.dumps(sample_message.to_dict()).encode(), -5)]
        
        # Enqueue
        success = await message_queue.enqueue(sample_message)
        assert success is True
        redis_client.zadd.assert_called_once()
        
        # Dequeue
        message = await message_queue.dequeue()
        assert message is not None
        assert message.id == sample_message.id
        redis_client.zpopmax.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, message_queue, redis_client):
        """Testa ordenação por prioridade"""
        # Criar mensagens com diferentes prioridades
        msg_low = QueueMessage(id="1", phone_number="+1", content="Low", priority=1)
        msg_normal = QueueMessage(id="2", phone_number="+2", content="Normal", priority=5)
        msg_critical = QueueMessage(id="3", phone_number="+3", content="Critical", priority=10)
        
        # Mock para retornar na ordem de prioridade
        redis_client.zpopmax.side_effect = [
            [(json.dumps(msg_critical.to_dict()).encode(), -10)],
            [(json.dumps(msg_normal.to_dict()).encode(), -5)],
            [(json.dumps(msg_low.to_dict()).encode(), -1)],
            []
        ]
        
        # Dequeue deve retornar em ordem de prioridade
        msg1 = await message_queue.dequeue()
        assert msg1.priority == 10  # Critical primeiro
        
        msg2 = await message_queue.dequeue()
        assert msg2.priority == 5   # Normal segundo
        
        msg3 = await message_queue.dequeue()
        assert msg3.priority == 1   # Low por último
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, message_queue, sample_message, redis_client):
        """Testa mecanismo de retry"""
        # Configura mensagem com 1 tentativa já feita
        sample_message.attempts = 1
        sample_message.max_attempts = 3
        
        # Mock Redis
        redis_client.hdel.return_value = 1
        redis_client.zadd.return_value = 1
        
        # Retry
        await message_queue.retry_message(sample_message, "Test error")
        
        # Verifica que foi removida do processing e re-enfileirada
        redis_client.hdel.assert_called_once()
        assert sample_message.attempts == 2
        assert sample_message.error == "Test error"
    
    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, message_queue, sample_message, redis_client):
        """Testa dead letter queue"""
        # Configura mensagem no limite de tentativas
        sample_message.attempts = 2
        sample_message.max_attempts = 3
        
        # Mock Redis
        redis_client.hdel.return_value = 1
        redis_client.hset.return_value = 1
        
        # Retry deve mover para dead letter
        await message_queue.retry_message(sample_message, "Final error")
        
        # Verifica que foi movida para dead letter
        calls = redis_client.hset.call_args_list
        assert any(message_queue.dead_letter_queue in str(call) for call in calls)
    
    @pytest.mark.asyncio
    async def test_get_queue_status(self, message_queue, redis_client):
        """Testa obtenção de status da fila"""
        # Mock Redis responses
        redis_client.zcard.return_value = 5  # 5 pending
        redis_client.hlen.side_effect = [3, 2]  # 3 processing, 2 dead letter
        redis_client.hgetall.return_value = {
            b"messages_enqueued": b"100",
            b"messages_completed": b"90",
            b"messages_failed": b"5"
        }
        
        status = await message_queue.get_queue_status()
        
        assert status["pending"] == 5
        assert status["processing"] == 3
        assert status["dead_letter"] == 2
        assert status["metrics"]["messages_enqueued"] == 100

class TestPriorityMessageQueue:
    """Testes para a Priority Message Queue"""
    
    @pytest.mark.asyncio
    async def test_priority_detection(self, priority_queue):
        """Testa detecção automática de prioridade"""
        # Testa palavras-chave críticas
        priority = priority_queue._determine_priority("URGENTE: Sistema parado!")
        assert priority == MessagePriority.CRITICAL.value
        
        # Testa suporte técnico
        priority = priority_queue._determine_priority("Erro ao fazer login")
        assert priority == MessagePriority.HIGH.value
        
        # Testa consulta de dados
        priority = priority_queue._determine_priority("Preciso do relatório mensal")
        assert priority == MessagePriority.NORMAL.value
        
        # Testa conversa geral
        priority = priority_queue._determine_priority("Olá, bom dia!")
        assert priority == MessagePriority.LOW.value
    
    @pytest.mark.asyncio
    async def test_user_message_limit(self, priority_queue, redis_client):
        """Testa limite de mensagens por usuário"""
        phone = "+5511999999999"
        
        # Mock para simular 10 mensagens do usuário
        messages = []
        for i in range(10):
            msg = QueueMessage(
                id=f"msg_{i}",
                phone_number=phone,
                content=f"Message {i}"
            )
            messages.append(json.dumps(msg.to_dict()).encode())
        
        redis_client.zrange.return_value = messages
        
        # 11ª mensagem deve ser rejeitada
        success = await priority_queue.enqueue_with_rules(
            phone, "Nova mensagem", {}
        )
        
        assert success is False

class TestLLMCacheService:
    """Testes para o serviço de cache LLM"""
    
    @pytest.fixture
    async def cache_service(self, redis_client):
        return LLMCacheService(redis_client)
    
    @pytest.mark.asyncio
    async def test_cache_hit_miss(self, cache_service, redis_client):
        """Testa cache hit e miss"""
        prompt = "Qual é a capital do Brasil?"
        response = "A capital do Brasil é Brasília."
        
        # Cache miss inicial
        redis_client.get.return_value = None
        result = await cache_service.get(prompt)
        assert result is None
        
        # Armazena no cache
        redis_client.setex.return_value = True
        redis_client.sadd.return_value = 1
        success = await cache_service.set(prompt, response)
        assert success is True
        
        # Cache hit
        entry = CacheEntry(
            key="test_key",
            prompt=prompt,
            response=response,
            model="llama3.1:8b",
            temperature=0.7,
            created_at=datetime.now()
        )
        redis_client.get.return_value = json.dumps(entry.to_dict()).encode()
        
        result = await cache_service.get(prompt)
        assert result == response
    
    @pytest.mark.asyncio
    async def test_similarity_detection(self, cache_service):
        """Testa detecção de similaridade"""
        # Testa cálculo de similaridade
        sim1 = cache_service._calculate_similarity(
            "Qual é a capital do Brasil?",
            "Qual é a capital do Brazil?"
        )
        assert sim1 > 0.8  # Alta similaridade
        
        sim2 = cache_service._calculate_similarity(
            "Qual é a capital do Brasil?",
            "Como está o tempo hoje?"
        )
        assert sim2 < 0.3  # Baixa similaridade
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, cache_service, redis_client):
        """Testa invalidação de cache"""
        # Mock Redis responses
        keys_to_delete = [b"cache:key1", b"cache:key2"]
        redis_client.scan_iter.return_value = keys_to_delete.__aiter__()
        redis_client.delete.return_value = 2
        redis_client.srem.return_value = 1
        
        count = await cache_service.invalidate("*")
        assert count == 2
        redis_client.delete.assert_called_once_with(*keys_to_delete)

class TestEnhancedWhatsAppService:
    """Testes para o serviço WhatsApp aprimorado"""
    
    @pytest.fixture
    async def whatsapp_service(self):
        service = EnhancedWhatsAppService()
        # Mock dependencies
        service.session_manager = AsyncMock()
        service.twilio_service = AsyncMock()
        service.llm_service = AsyncMock()
        service.message_queue = AsyncMock()
        service.redis_client = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_webhook_processing_with_queue(self, whatsapp_service):
        """Testa processamento de webhook com queue"""
        webhook_data = {
            'From': 'whatsapp:+5511999999999',
            'Body': 'Teste de mensagem',
            'MessageSid': 'SM123456'
        }
        
        # Mock validação e enfileiramento
        whatsapp_service.twilio_service.validate_webhook.return_value = True
        whatsapp_service.twilio_service.extract_phone_number.return_value = '+5511999999999'
        whatsapp_service.message_queue.enqueue_with_rules.return_value = True
        whatsapp_service.message_queue.get_queue_status.return_value = {"pending": 3}
        whatsapp_service.twilio_service.create_webhook_response.return_value = "<Response>OK</Response>"
        
        response = await whatsapp_service.process_incoming_webhook(webhook_data)
        
        # Verifica que mensagem foi enfileirada
        whatsapp_service.message_queue.enqueue_with_rules.assert_called_once()
        assert "<Response>" in response
    
    @pytest.mark.asyncio
    async def test_rate_limiting_per_user(self, whatsapp_service):
        """Testa rate limiting por usuário"""
        phone = "+5511999999999"
        
        # Mock para simular rate limit excedido
        whatsapp_service.redis_client.incr.return_value = 11  # Acima do limite
        whatsapp_service.redis_client.expire.return_value = True
        
        is_limited = await whatsapp_service._is_user_rate_limited(phone)
        assert is_limited is True
        
        # Mock para usuário dentro do limite
        whatsapp_service.redis_client.incr.return_value = 5
        is_limited = await whatsapp_service._is_user_rate_limited(phone)
        assert is_limited is False

class TestMonitoringService:
    """Testes para o serviço de monitoramento"""
    
    @pytest.fixture
    async def monitoring_service(self):
        mock_queue = AsyncMock()
        mock_llm = AsyncMock()
        mock_twilio = AsyncMock()
        
        service = MonitoringService(
            message_queue=mock_queue,
            llm_service=mock_llm,
            twilio_service=mock_twilio,
            admin_phones=["+5511999999999"]
        )
        return service
    
    @pytest.mark.asyncio
    async def test_alert_creation(self, monitoring_service):
        """Testa criação de alertas"""
        # Mock metrics indicando problema
        metrics = {
            "queue": {
                "pending": 100,  # Alto número de pendentes
                "circuit_breaker": {"state": "closed"}
            }
        }
        
        # Checa regras
        monitoring_service.message_queue.get_queue_status.return_value = metrics["queue"]
        await monitoring_service._check_rules(metrics)
        
        # Deve ter criado alerta para queue size
        active_alerts = await monitoring_service.get_active_alerts()
        assert len(active_alerts) > 0
        
        # Verifica tipo do alerta
        queue_alerts = [a for a in active_alerts if a.type == AlertType.QUEUE_SIZE]
        assert len(queue_alerts) > 0
    
    @pytest.mark.asyncio
    async def test_alert_resolution(self, monitoring_service):
        """Testa resolução de alertas"""
        # Cria alerta manualmente
        from app.services.monitoring_alerts import Alert
        alert = Alert(
            id="test_alert",
            type=AlertType.CIRCUIT_BREAKER,
            level=AlertLevel.CRITICAL,
            title="Test Alert",
            message="Test message",
            details={},
            created_at=datetime.now()
        )
        
        monitoring_service.alerts[alert.id] = alert
        
        # Resolve alerta
        await monitoring_service._resolve_alert(alert)
        
        assert alert.resolved is True
        assert alert.resolved_at is not None

# Testes de integração
class TestIntegration:
    """Testes de integração do sistema completo"""
    
    @pytest.mark.asyncio
    async def test_full_message_flow_with_queue(self):
        """Testa fluxo completo de mensagem com queue"""
        # Este teste seria mais complexo em produção
        # Aqui apenas demonstramos a estrutura
        
        # 1. Webhook recebe mensagem
        # 2. Mensagem é enfileirada
        # 3. Worker processa mensagem
        # 4. LLM gera resposta (com cache check)
        # 5. Resposta é enviada via Twilio
        
        assert True  # Placeholder

# Testes de performance
class TestPerformance:
    """Testes de performance e carga"""
    
    @pytest.mark.asyncio
    async def test_queue_performance_under_load(self, message_queue, redis_client):
        """Testa performance da fila sob carga"""
        # Mock Redis para retornar sucesso sempre
        redis_client.zadd.return_value = 1
        
        # Enfileira 1000 mensagens
        start_time = asyncio.get_event_loop().time()
        
        tasks = []
        for i in range(1000):
            msg = QueueMessage(
                id=f"perf_test_{i}",
                phone_number=f"+551199999{i:04d}",
                content=f"Performance test message {i}"
            )
            tasks.append(message_queue.enqueue(msg))
        
        await asyncio.gather(*tasks)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Deve processar 1000 mensagens em menos de 5 segundos
        assert elapsed < 5.0
        assert redis_client.zadd.call_count == 1000

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])