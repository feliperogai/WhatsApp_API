import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import aiohttp
import json

from app.services.message_queue import MessageQueue
from app.services.llm_service import LLMService
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertType(Enum):
    QUEUE_SIZE = "queue_size"
    PROCESSING_DELAY = "processing_delay"
    ERROR_RATE = "error_rate"
    CIRCUIT_BREAKER = "circuit_breaker"
    LLM_TIMEOUT = "llm_timeout"
    DEAD_LETTER = "dead_letter"
    RATE_LIMIT = "rate_limit"
    MEMORY_USAGE = "memory_usage"
    SYSTEM_HEALTH = "system_health"

@dataclass
class Alert:
    """Estrutura de um alerta"""
    id: str
    type: AlertType
    level: AlertLevel
    title: str
    message: str
    details: Dict[str, Any]
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    notification_sent: bool = False

class AlertRule:
    """Regra para gerar alertas"""
    def __init__(
        self,
        name: str,
        alert_type: AlertType,
        check_interval: int = 60,
        condition: Callable = None,
        level: AlertLevel = AlertLevel.WARNING
    ):
        self.name = name
        self.alert_type = alert_type
        self.check_interval = check_interval
        self.condition = condition
        self.level = level
        self.last_check = None
        self.active_alert = None

class MonitoringService:
    """Serviço de monitoramento e alertas"""
    
    def __init__(
        self,
        message_queue: MessageQueue,
        llm_service: LLMService,
        twilio_service: TwilioService = None,
        webhook_url: Optional[str] = None,
        admin_phones: List[str] = None
    ):
        self.message_queue = message_queue
        self.llm_service = llm_service
        self.twilio_service = twilio_service
        self.webhook_url = webhook_url
        self.admin_phones = admin_phones or []
        
        # Estado
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.rules: List[AlertRule] = []
        self.is_monitoring = False
        self.monitoring_task = None
        
        # Métricas
        self.metrics_history = []
        self.max_history_size = 1000
        
        # Configurar regras padrão
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Configura regras de alerta padrão"""
        
        # Regra: Fila muito grande
        self.add_rule(AlertRule(
            name="queue_size_high",
            alert_type=AlertType.QUEUE_SIZE,
            check_interval=30,
            condition=lambda metrics: metrics.get("queue", {}).get("pending", 0) > 50,
            level=AlertLevel.WARNING
        ))
        
        # Regra: Fila crítica
        self.add_rule(AlertRule(
            name="queue_size_critical",
            alert_type=AlertType.QUEUE_SIZE,
            check_interval=30,
            condition=lambda metrics: metrics.get("queue", {}).get("pending", 0) > 100,
            level=AlertLevel.CRITICAL
        ))
        
        # Regra: Muitas mensagens na dead letter
        self.add_rule(AlertRule(
            name="dead_letter_high",
            alert_type=AlertType.DEAD_LETTER,
            check_interval=300,
            condition=lambda metrics: metrics.get("queue", {}).get("dead_letter", 0) > 10,
            level=AlertLevel.ERROR
        ))
        
        # Regra: Circuit breaker aberto
        self.add_rule(AlertRule(
            name="circuit_breaker_open",
            alert_type=AlertType.CIRCUIT_BREAKER,
            check_interval=10,
            condition=lambda metrics: metrics.get("queue", {}).get("circuit_breaker", {}).get("state") == "open",
            level=AlertLevel.CRITICAL
        ))
        
        # Regra: Taxa de erro alta
        self.add_rule(AlertRule(
            name="high_error_rate",
            alert_type=AlertType.ERROR_RATE,
            check_interval=60,
            condition=lambda metrics: self._calculate_error_rate(metrics) > 0.2,
            level=AlertLevel.ERROR
        ))
        
        # Regra: Rate limit próximo do máximo
        self.add_rule(AlertRule(
            name="rate_limit_warning",
            alert_type=AlertType.RATE_LIMIT,
            check_interval=30,
            condition=lambda metrics: self._check_rate_limit_usage(metrics) > 0.8,
            level=AlertLevel.WARNING
        ))
        
        # Regra: Atraso no processamento
        self.add_rule(AlertRule(
            name="processing_delay",
            alert_type=AlertType.PROCESSING_DELAY,
            check_interval=60,
            condition=lambda metrics: self._calculate_avg_delay(metrics) > 300,  # 5 minutos
            level=AlertLevel.WARNING
        ))
    
    def add_rule(self, rule: AlertRule):
        """Adiciona regra de alerta"""
        self.rules.append(rule)
        logger.info(f"Alert rule added: {rule.name}")
    
    async def start_monitoring(self):
        """Inicia monitoramento"""
        if self.is_monitoring:
            logger.warning("Monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Monitoring service started")
    
    async def stop_monitoring(self):
        """Para monitoramento"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Monitoring service stopped")
    
    async def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        while self.is_monitoring:
            try:
                # Coleta métricas
                metrics = await self._collect_metrics()
                
                # Armazena histórico
                self._store_metrics(metrics)
                
                # Verifica regras
                await self._check_rules(metrics)
                
                # Limpa alertas antigos resolvidos
                self._cleanup_old_alerts()
                
                # Aguarda próximo ciclo
                await asyncio.sleep(10)  # Check a cada 10 segundos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Coleta métricas do sistema"""
        try:
            # Métricas da queue
            queue_status = await self.message_queue.get_queue_status()
            
            # Métricas do LLM
            llm_status = await self.llm_service.get_service_status()
            
            # Métricas de memória (simplificado)
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "queue": queue_status,
                "llm": llm_status,
                "system": {
                    "memory_mb": memory_info.rss / 1024 / 1024,
                    "memory_percent": process.memory_percent()
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {}
    
    def _store_metrics(self, metrics: Dict[str, Any]):
        """Armazena métricas no histórico"""
        self.metrics_history.append(metrics)
        
        # Limita tamanho do histórico
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    async def _check_rules(self, metrics: Dict[str, Any]):
        """Verifica todas as regras"""
        current_time = datetime.now()
        
        for rule in self.rules:
            # Verifica se é hora de checar
            if rule.last_check:
                time_since_check = (current_time - rule.last_check).seconds
                if time_since_check < rule.check_interval:
                    continue
            
            rule.last_check = current_time
            
            try:
                # Avalia condição
                if rule.condition and rule.condition(metrics):
                    # Condição verdadeira - criar/manter alerta
                    if not rule.active_alert:
                        alert = await self._create_alert(rule, metrics)
                        rule.active_alert = alert
                else:
                    # Condição falsa - resolver alerta se existir
                    if rule.active_alert:
                        await self._resolve_alert(rule.active_alert)
                        rule.active_alert = None
                        
            except Exception as e:
                logger.error(f"Error checking rule {rule.name}: {e}")
    
    async def _create_alert(self, rule: AlertRule, metrics: Dict[str, Any]) -> Alert:
        """Cria novo alerta"""
        alert_id = f"{rule.alert_type.value}_{datetime.now().timestamp()}"
        
        # Gera mensagem baseada no tipo
        title, message = self._generate_alert_message(rule, metrics)
        
        alert = Alert(
            id=alert_id,
            type=rule.alert_type,
            level=rule.level,
            title=title,
            message=message,
            details=metrics,
            created_at=datetime.now()
        )
        
        # Armazena alerta
        self.alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Envia notificações
        await self._send_notifications(alert)
        
        logger.warning(f"Alert created: {title}")
        
        return alert
    
    async def _resolve_alert(self, alert: Alert):
        """Resolve alerta"""
        alert.resolved = True
        alert.resolved_at = datetime.now()
        
        # Notifica resolução
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            await self._send_resolution_notification(alert)
        
        logger.info(f"Alert resolved: {alert.title}")
    
    def _generate_alert_message(self, rule: AlertRule, metrics: Dict[str, Any]) -> tuple:
        """Gera título e mensagem do alerta"""
        
        if rule.alert_type == AlertType.QUEUE_SIZE:
            pending = metrics.get("queue", {}).get("pending", 0)
            title = f"Queue Size Alert: {pending} messages pending"
            message = f"The message queue has {pending} pending messages, which exceeds the threshold."
            
        elif rule.alert_type == AlertType.DEAD_LETTER:
            dead_letter = metrics.get("queue", {}).get("dead_letter", 0)
            title = f"Dead Letter Queue Alert: {dead_letter} failed messages"
            message = f"There are {dead_letter} messages in the dead letter queue requiring attention."
            
        elif rule.alert_type == AlertType.CIRCUIT_BREAKER:
            state = metrics.get("queue", {}).get("circuit_breaker", {}).get("state", "unknown")
            title = f"Circuit Breaker Alert: State is {state}"
            message = "The circuit breaker is open, indicating repeated failures with the LLM service."
            
        elif rule.alert_type == AlertType.ERROR_RATE:
            error_rate = self._calculate_error_rate(metrics)
            title = f"High Error Rate: {error_rate:.1%}"
            message = f"The error rate is {error_rate:.1%}, indicating system instability."
            
        elif rule.alert_type == AlertType.RATE_LIMIT:
            usage = self._check_rate_limit_usage(metrics)
            title = f"Rate Limit Warning: {usage:.1%} usage"
            message = "The system is approaching the rate limit for LLM requests."
            
        else:
            title = f"{rule.alert_type.value} Alert"
            message = f"Alert condition triggered for {rule.name}"
        
        return title, message
    
    async def _send_notifications(self, alert: Alert):
        """Envia notificações do alerta"""
        try:
            # Webhook notification
            if self.webhook_url:
                await self._send_webhook_notification(alert)
            
            # SMS notification para alertas críticos
            if self.twilio_service and alert.level == AlertLevel.CRITICAL:
                await self._send_sms_notifications(alert)
            
            alert.notification_sent = True
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
    
    async def _send_webhook_notification(self, alert: Alert):
        """Envia notificação via webhook"""
        try:
            payload = {
                "alert_id": alert.id,
                "type": alert.type.value,
                "level": alert.level.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.created_at.isoformat(),
                "details": alert.details
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Webhook notification failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    async def _send_sms_notifications(self, alert: Alert):
        """Envia SMS para administradores"""
        for phone in self.admin_phones:
            try:
                message = f"🚨 JARVIS ALERT: {alert.title}\n\n{alert.message}\n\nLevel: {alert.level.value}"
                await self.twilio_service.send_message(phone, message)
                logger.info(f"SMS alert sent to {phone}")
            except Exception as e:
                logger.error(f"Error sending SMS to {phone}: {e}")
    
    async def _send_resolution_notification(self, alert: Alert):
        """Notifica resolução do alerta"""
        duration = (alert.resolved_at - alert.created_at).seconds
        message = f"✅ Alert resolved: {alert.title}\nDuration: {duration}s"
        
        # Webhook
        if self.webhook_url:
            await self._send_webhook_notification({
                **alert.__dict__,
                "event": "resolved",
                "duration_seconds": duration
            })
        
        # SMS para críticos
        if self.twilio_service and alert.level == AlertLevel.CRITICAL:
            for phone in self.admin_phones:
                try:
                    await self.twilio_service.send_message(phone, message)
                except Exception as e:
                    logger.error(f"Error sending resolution SMS: {e}")
    
    def _calculate_error_rate(self, metrics: Dict[str, Any]) -> float:
        """Calcula taxa de erro"""
        try:
            total = metrics.get("queue", {}).get("metrics", {}).get("messages_completed", 0)
            failed = metrics.get("queue", {}).get("metrics", {}).get("messages_failed", 0)
            
            if total == 0:
                return 0.0
            
            return failed / (total + failed)
            
        except Exception:
            return 0.0
    
    def _check_rate_limit_usage(self, metrics: Dict[str, Any]) -> float:
        """Verifica uso do rate limit"""
        try:
            current = metrics.get("queue", {}).get("rate_limiter", {}).get("current_requests", 0)
            max_req = metrics.get("queue", {}).get("rate_limiter", {}).get("max_requests", 1)
            
            return current / max_req
            
        except Exception:
            return 0.0
    
    def _calculate_avg_delay(self, metrics: Dict[str, Any]) -> float:
        """Calcula atraso médio de processamento"""
        # Implementação simplificada
        # Em produção, calcular baseado em timestamps reais
        pending = metrics.get("queue", {}).get("pending", 0)
        workers = metrics.get("queue", {}).get("workers", {}).get("active", 1)
        
        # Estimativa: 30s por mensagem
        if workers > 0:
            return (pending * 30) / workers
        
        return 0
    
    def _cleanup_old_alerts(self):
        """Remove alertas antigos resolvidos"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        alerts_to_remove = []
        for alert_id, alert in self.alerts.items():
            if alert.resolved and alert.resolved_at < cutoff_time:
                alerts_to_remove.append(alert_id)
        
        for alert_id in alerts_to_remove:
            del self.alerts[alert_id]
    
    async def get_active_alerts(self) -> List[Alert]:
        """Retorna alertas ativos"""
        return [alert for alert in self.alerts.values() if not alert.resolved]
    
    async def get_alert_summary(self) -> Dict[str, Any]:
        """Retorna resumo dos alertas"""
        active_alerts = await self.get_active_alerts()
        
        # Conta por nível
        level_counts = {level: 0 for level in AlertLevel}
        for alert in active_alerts:
            level_counts[alert.level] += 1
        
        return {
            "total_active": len(active_alerts),
            "by_level": {level.value: count for level, count in level_counts.items()},
            "alerts": [
                {
                    "id": alert.id,
                    "type": alert.type.value,
                    "level": alert.level.value,
                    "title": alert.title,
                    "created_at": alert.created_at.isoformat()
                }
                for alert in active_alerts
            ],
            "history_count": len(self.alert_history)
        }
    
    def get_metrics_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Retorna histórico de métricas"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        return [
            m for m in self.metrics_history
            if datetime.fromisoformat(m.get("timestamp", "")) > cutoff_time
        ]