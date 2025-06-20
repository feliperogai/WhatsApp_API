import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import asyncio
import json

logger = logging.getLogger(__name__)

@dataclass
class LLMMetrics:
    """Métricas específicas do LLM"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    total_tokens_processed: int = 0
    avg_confidence: float = 0.0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    confidence_scores: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_request(self, response_time: float, confidence: float, tokens: int = 0, success: bool = True):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.response_times.append(response_time)
        self.confidence_scores.append(confidence)
        self.total_tokens_processed += tokens
        
        # Recalcula médias
        self.avg_response_time = sum(self.response_times) / len(self.response_times)
        self.avg_confidence = sum(self.confidence_scores) / len(self.confidence_scores)

@dataclass
class AgentMetrics:
    """Métricas por agente"""
    name: str
    activations: int = 0
    avg_processing_time: float = 0.0
    success_rate: float = 0.0
    total_conversations: int = 0
    processing_times: deque = field(default_factory=lambda: deque(maxlen=50))
    
    def add_activation(self, processing_time: float, success: bool = True):
        self.activations += 1
        self.processing_times.append(processing_time)
        self.avg_processing_time = sum(self.processing_times) / len(self.processing_times)
        
        if success:
            self.total_conversations += 1
        
        self.success_rate = (self.total_conversations / self.activations) * 100

class MetricsService:
    def __init__(self):
        self.llm_metrics = LLMMetrics()
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.conversation_metrics = defaultdict(int)
        self.system_metrics = {
            "uptime_start": datetime.now(),
            "total_sessions": 0,
            "active_sessions": 0,
            "peak_concurrent_sessions": 0
        }
        self.hourly_stats = defaultdict(lambda: defaultdict(int))
        
    def record_llm_request(
        self, 
        response_time: float, 
        confidence: float, 
        tokens: int = 0, 
        success: bool = True,
        model: str = "unknown"
    ):
        """Registra uma requisição LLM"""
        self.llm_metrics.add_request(response_time, confidence, tokens, success)
        
        # Estatísticas horárias
        hour = datetime.now().hour
        self.hourly_stats[hour]["llm_requests"] += 1
        if success:
            self.hourly_stats[hour]["llm_success"] += 1
        
        logger.debug(f"LLM request recorded: {response_time:.2f}s, confidence: {confidence:.2f}")
    
    def record_agent_activation(
        self, 
        agent_id: str, 
        agent_name: str,
        processing_time: float, 
        success: bool = True
    ):
        """Registra ativação de agente"""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentMetrics(name=agent_name)
        
        self.agent_metrics[agent_id].add_activation(processing_time, success)
        
        # Estatísticas horárias
        hour = datetime.now().hour
        self.hourly_stats[hour][f"agent_{agent_id}"] += 1
        
        logger.debug(f"Agent activation recorded: {agent_id} ({processing_time:.2f}s)")
    
    def record_conversation_event(self, event_type: str, phone_number: str = None):
        """Registra eventos de conversa"""
        self.conversation_metrics[event_type] += 1
        
        if event_type == "session_start":
            self.system_metrics["total_sessions"] += 1
            self.system_metrics["active_sessions"] += 1
            
            # Atualiza pico de sessões concorrentes
            if self.system_metrics["active_sessions"] > self.system_metrics["peak_concurrent_sessions"]:
                self.system_metrics["peak_concurrent_sessions"] = self.system_metrics["active_sessions"]
        
        elif event_type == "session_end":
            self.system_metrics["active_sessions"] = max(0, self.system_metrics["active_sessions"] - 1)
        
        # Estatísticas horárias
        hour = datetime.now().hour
        self.hourly_stats[hour][event_type] += 1
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna resumo completo das métricas"""
        uptime = datetime.now() - self.system_metrics["uptime_start"]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime).split('.')[0],
            
            # Métricas LLM
            "llm": {
                "total_requests": self.llm_metrics.total_requests,
                "success_rate": (self.llm_metrics.successful_requests / max(1, self.llm_metrics.total_requests)) * 100,
                "avg_response_time": round(self.llm_metrics.avg_response_time, 3),
                "avg_confidence": round(self.llm_metrics.avg_confidence, 3),
                "total_tokens": self.llm_metrics.total_tokens_processed,
                "requests_per_hour": self._calculate_hourly_rate("llm_requests")
            },
            
            # Métricas por agente
            "agents": {
                agent_id: {
                    "name": metrics.name,
                    "activations": metrics.activations,
                    "avg_processing_time": round(metrics.avg_processing_time, 3),
                    "success_rate": round(metrics.success_rate, 1)
                }
                for agent_id, metrics in self.agent_metrics.items()
            },
            
            # Métricas do sistema
            "system": {
                **self.system_metrics,
                "sessions_per_hour": self._calculate_hourly_rate("session_start")
            },
            
            # Métricas de conversa
            "conversations": dict(self.conversation_metrics),
            
            # Performance
            "performance": {
                "avg_llm_latency": round(self.llm_metrics.avg_response_time, 3),
                "peak_concurrent_sessions": self.system_metrics["peak_concurrent_sessions"],
                "total_throughput": self.llm_metrics.total_requests + sum(
                    m.activations for m in self.agent_metrics.values()
                )
            }
        }
    
    def get_prometheus_metrics(self) -> str:
        """Retorna métricas no formato Prometheus"""
        metrics = []
        
        # Métricas LLM
        metrics.extend([
            f"jarvis_llm_requests_total {self.llm_metrics.total_requests}",
            f"jarvis_llm_requests_successful {self.llm_metrics.successful_requests}",
            f"jarvis_llm_requests_failed {self.llm_metrics.failed_requests}",
            f"jarvis_llm_avg_response_time {self.llm_metrics.avg_response_time}",
            f"jarvis_llm_avg_confidence {self.llm_metrics.avg_confidence}",
            f"jarvis_llm_tokens_processed {self.llm_metrics.total_tokens_processed}",
        ])
        
        # Métricas por agente
        for agent_id, agent_metrics in self.agent_metrics.items():
            metrics.extend([
                f'jarvis_agent_activations{{agent="{agent_id}"}} {agent_metrics.activations}',
                f'jarvis_agent_avg_processing_time{{agent="{agent_id}"}} {agent_metrics.avg_processing_time}',
                f'jarvis_agent_success_rate{{agent="{agent_id}"}} {agent_metrics.success_rate}',
            ])
        
        # Métricas do sistema
        uptime = (datetime.now() - self.system_metrics["uptime_start"]).total_seconds()
        metrics.extend([
            f"jarvis_uptime_seconds {int(uptime)}",
            f"jarvis_total_sessions {self.system_metrics['total_sessions']}",
            f"jarvis_active_sessions {self.system_metrics['active_sessions']}",
            f"jarvis_peak_concurrent_sessions {self.system_metrics['peak_concurrent_sessions']}",
        ])
        
        # Métricas de conversa
        for event_type, count in self.conversation_metrics.items():
            metrics.append(f'jarvis_conversation_events{{type="{event_type}"}} {count}')
        
        return '\n'.join(metrics)
    
    def _calculate_hourly_rate(self, metric_key: str) -> float:
        """Calcula taxa por hora baseada nas últimas 24h"""
        current_hour = datetime.now().hour
        total = 0
        hours_counted = 0
        
        for i in range(24):
            hour = (current_hour - i) % 24
            if hour in self.hourly_stats:
                total += self.hourly_stats[hour].get(metric_key, 0)
                hours_counted += 1
        
        return total / max(1, hours_counted)
    
    def get_detailed_agent_stats(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retorna estatísticas detalhadas de um agente específico"""
        if agent_id not in self.agent_metrics:
            return None
        
        agent = self.agent_metrics[agent_id]
        recent_times = list(agent.processing_times)
        
        return {
            "agent_id": agent_id,
            "name": agent.name,
            "activations": agent.activations,
            "total_conversations": agent.total_conversations,
            "success_rate": round(agent.success_rate, 2),
            "avg_processing_time": round(agent.avg_processing_time, 3),
            "min_processing_time": min(recent_times) if recent_times else 0,
            "max_processing_time": max(recent_times) if recent_times else 0,
            "recent_performance": recent_times[-10:] if recent_times else []
        }
    
    def reset_metrics(self):
        """Reseta todas as métricas (útil para testes)"""
        self.llm_metrics = LLMMetrics()
        self.agent_metrics.clear()
        self.conversation_metrics.clear()
        self.hourly_stats.clear()
        self.system_metrics = {
            "uptime_start": datetime.now(),
            "total_sessions": 0,
            "active_sessions": 0,
            "peak_concurrent_sessions": 0
        }
        logger.info("Metrics reset successfully")

# Instância global
metrics_service = MetricsService()