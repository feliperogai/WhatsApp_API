from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime
import logging

from app.services.enhanced_whatsapp_service import EnhancedWhatsAppService
from app.services.message_queue import MessagePriority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])

# Referência global para o serviço
whatsapp_service: EnhancedWhatsAppService = None

def set_whatsapp_service(service: EnhancedWhatsAppService):
    """Define referência do serviço WhatsApp"""
    global whatsapp_service
    whatsapp_service = service

@router.get("/status")
async def get_queue_status() -> Dict[str, Any]:
    """Obtém status detalhado da fila"""
    try:
        if not whatsapp_service or not whatsapp_service.message_queue:
            raise HTTPException(status_code=503, detail="Queue service not available")
        
        status = await whatsapp_service.message_queue.get_queue_status()
        
        # Adiciona informações extras
        return {
            **status,
            "timestamp": datetime.now().isoformat(),
            "healthy": status.get("circuit_breaker", {}).get("state") != "open"
        }
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/pending")
async def get_pending_messages(limit: int = 10) -> List[Dict[str, Any]]:
    """Lista mensagens pendentes na fila"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        # Busca mensagens pendentes do Redis
        messages = []
        queue_data = await whatsapp_service.redis_client.zrange(
            whatsapp_service.message_queue.queue_name,
            0,
            limit - 1,
            withscores=True
        )
        
        for msg_data, score in queue_data:
            msg_dict = json.loads(msg_data)
            msg_dict["priority_score"] = -score  # Score negativo para prioridade
            messages.append(msg_dict)
        
        return messages
        
    except Exception as e:
        logger.error(f"Error getting pending messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/processing")
async def get_processing_messages() -> List[Dict[str, Any]]:
    """Lista mensagens sendo processadas"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        messages = []
        processing_data = await whatsapp_service.redis_client.hgetall(
            whatsapp_service.message_queue.processing_queue
        )
        
        for msg_id, msg_data in processing_data.items():
            msg_dict = json.loads(msg_data)
            messages.append(msg_dict)
        
        return messages
        
    except Exception as e:
        logger.error(f"Error getting processing messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/dead-letter")
async def get_dead_letter_messages(limit: int = 20) -> List[Dict[str, Any]]:
    """Lista mensagens na dead letter queue"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        messages = await whatsapp_service.message_queue.process_dead_letter_queue()
        
        # Converte para dict e limita resultado
        return [msg.to_dict() for msg in messages[:limit]]
        
    except Exception as e:
        logger.error(f"Error getting dead letter messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/messages/retry/{message_id}")
async def retry_dead_letter_message(message_id: str) -> Dict[str, str]:
    """Reprocessa mensagem da dead letter queue"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        # Busca mensagem na dead letter
        msg_data = await whatsapp_service.redis_client.hget(
            whatsapp_service.message_queue.dead_letter_queue,
            message_id
        )
        
        if not msg_data:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Remove da dead letter
        await whatsapp_service.redis_client.hdel(
            whatsapp_service.message_queue.dead_letter_queue,
            message_id
        )
        
        # Recoloca na fila principal
        from app.services.message_queue import QueueMessage
        message = QueueMessage.from_dict(json.loads(msg_data))
        message.attempts = 0  # Reset tentativas
        message.priority = MessagePriority.HIGH.value  # Alta prioridade
        
        success = await whatsapp_service.message_queue.enqueue(message)
        
        if success:
            return {"status": "success", "message": "Message re-queued successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to re-queue message")
            
    except Exception as e:
        logger.error(f"Error retrying message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/messages/priority")
async def send_priority_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Envia mensagem com prioridade alta"""
    try:
        phone_number = data.get("phone_number")
        message = data.get("message")
        priority = data.get("priority", MessagePriority.CRITICAL.value)
        
        if not phone_number or not message:
            raise HTTPException(status_code=400, detail="phone_number and message required")
        
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        success = await whatsapp_service.process_priority_message(
            phone_number, message, priority
        )
        
        if success:
            return {
                "status": "success",
                "message": "Priority message queued",
                "phone_number": phone_number
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to queue message")
            
    except Exception as e:
        logger.error(f"Error sending priority message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/clear-dead-letter")
async def clear_dead_letter_queue() -> Dict[str, Any]:
    """Limpa dead letter queue"""
    try:
        if not whatsapp_service:
            raise HTTPException(status_code=503, detail="Service not available")
        
        # Conta mensagens antes
        count = await whatsapp_service.redis_client.hlen(
            whatsapp_service.message_queue.dead_letter_queue
        )
        
        # Limpa a queue
        await whatsapp_service.redis_client.delete(
            whatsapp_service.message_queue.dead_letter_queue
        )
        
        return {
            "status": "success",
            "messages_cleared": count
        }
        
    except Exception as e:
        logger.error(f"Error clearing dead letter queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard", response_class=HTMLResponse)
async def queue_dashboard():
    """Dashboard HTML para monitoramento da fila"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Queue Monitor - Jarvis LLM</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: #0a0a0a;
                color: #e0e0e0;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 15px;
            }
            .metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .metric-card {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                transition: all 0.3s ease;
            }
            .metric-card:hover {
                background: rgba(255,255,255,0.08);
                transform: translateY(-2px);
            }
            .metric-value {
                font-size: 36px;
                font-weight: bold;
                margin: 10px 0;
            }
            .metric-label {
                color: #888;
                text-transform: uppercase;
                font-size: 12px;
                letter-spacing: 1px;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-healthy { background: #00ff00; box-shadow: 0 0 10px #00ff00; }
            .status-warning { background: #ffaa00; box-shadow: 0 0 10px #ffaa00; }
            .status-error { background: #ff0000; box-shadow: 0 0 10px #ff0000; }
            .chart-container {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                height: 300px;
            }
            .messages-table {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 20px;
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            th {
                background: rgba(255,255,255,0.05);
                font-weight: 600;
                text-transform: uppercase;
                font-size: 12px;
                letter-spacing: 1px;
            }
            .priority-critical { color: #ff4444; }
            .priority-high { color: #ffaa00; }
            .priority-normal { color: #00aaff; }
            .priority-low { color: #888; }
            .refresh-info {
                text-align: center;
                color: #666;
                margin-top: 20px;
            }
            .control-buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Queue Monitor - Jarvis LLM</h1>
                <p>Real-time Message Queue Dashboard</p>
            </div>
            
            <div class="control-buttons">
                <button onclick="refreshData()">🔄 Refresh</button>
                <button onclick="clearDeadLetter()">🗑️ Clear Dead Letters</button>
            </div>
            
            <div class="metrics" id="metrics">
                <div class="metric-card">
                    <div class="metric-label">Pending Messages</div>
                    <div class="metric-value" id="pending">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Processing</div>
                    <div class="metric-value" id="processing">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Dead Letter</div>
                    <div class="metric-value" id="deadLetter">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Active Workers</div>
                    <div class="metric-value" id="workers">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Rate Limit</div>
                    <div class="metric-value" id="rateLimit">-</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Circuit Breaker</div>
                    <div class="metric-value" id="circuitBreaker">-</div>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="queueChart"></canvas>
            </div>
            
            <div class="messages-table">
                <h3>📋 Processing Messages</h3>
                <table id="processingTable">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Phone</th>
                            <th>Content</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody id="processingBody">
                        <tr><td colspan="6" style="text-align: center;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="refresh-info">
                Auto-refresh every 5 seconds | Last update: <span id="lastUpdate">-</span>
            </div>
        </div>
        
        <script>
            let chart = null;
            const chartData = {
                labels: [],
                datasets: [{
                    label: 'Pending',
                    data: [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)'
                }, {
                    label: 'Processing',
                    data: [],
                    borderColor: '#00ff00',
                    backgroundColor: 'rgba(0, 255, 0, 0.1)'
                }, {
                    label: 'Dead Letter',
                    data: [],
                    borderColor: '#ff4444',
                    backgroundColor: 'rgba(255, 68, 68, 0.1)'
                }]
            };
            
            function initChart() {
                const ctx = document.getElementById('queueChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: chartData,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                ticks: { color: '#888' }
                            },
                            x: {
                                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                ticks: { color: '#888' }
                            }
                        },
                        plugins: {
                            legend: { labels: { color: '#e0e0e0' } }
                        }
                    }
                });
            }
            
            async function refreshData() {
                try {
                    // Get queue status
                    const response = await fetch('/queue/status');
                    const data = await response.json();
                    
                    // Update metrics
                    document.getElementById('pending').textContent = data.pending || 0;
                    document.getElementById('processing').textContent = data.processing || 0;
                    document.getElementById('deadLetter').textContent = data.dead_letter || 0;
                    document.getElementById('workers').textContent = 
                        `${data.workers?.active || 0}/${data.workers?.max || 0}`;
                    document.getElementById('rateLimit').textContent = 
                        `${data.rate_limiter?.current_requests || 0}/${data.rate_limiter?.max_requests || 0}`;
                    
                    // Circuit breaker status
                    const cbState = data.circuit_breaker?.state || 'unknown';
                    const cbElement = document.getElementById('circuitBreaker');
                    cbElement.innerHTML = `<span class="status-indicator status-${
                        cbState === 'closed' ? 'healthy' : cbState === 'open' ? 'error' : 'warning'
                    }"></span>${cbState}`;
                    
                    // Update chart
                    const now = new Date().toLocaleTimeString();
                    chartData.labels.push(now);
                    chartData.datasets[0].data.push(data.pending || 0);
                    chartData.datasets[1].data.push(data.processing || 0);
                    chartData.datasets[2].data.push(data.dead_letter || 0);
                    
                    // Keep only last 20 points
                    if (chartData.labels.length > 20) {
                        chartData.labels.shift();
                        chartData.datasets.forEach(ds => ds.data.shift());
                    }
                    
                    chart.update();
                    
                    // Get processing messages
                    const procResponse = await fetch('/queue/messages/processing');
                    const procMessages = await procResponse.json();
                    
                    // Update table
                    const tbody = document.getElementById('processingBody');
                    if (procMessages.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No messages processing</td></tr>';
                    } else {
                        tbody.innerHTML = procMessages.map(msg => `
                            <tr>
                                <td>${msg.id.substring(0, 8)}...</td>
                                <td>${msg.phone_number}</td>
                                <td>${msg.content.substring(0, 50)}...</td>
                                <td><span class="priority-${getPriorityClass(msg.priority)}">${msg.priority}</span></td>
                                <td>${msg.status}</td>
                                <td>${new Date(msg.created_at).toLocaleString()}</td>
                            </tr>
                        `).join('');
                    }
                    
                    // Update last refresh time
                    document.getElementById('lastUpdate').textContent = new Date().toLocaleString();
                    
                } catch (error) {
                    console.error('Error refreshing data:', error);
                }
            }
            
            function getPriorityClass(priority) {
                if (priority >= 10) return 'critical';
                if (priority >= 8) return 'high';
                if (priority >= 5) return 'normal';
                return 'low';
            }
            
            async function clearDeadLetter() {
                if (!confirm('Clear all messages from dead letter queue?')) return;
                
                try {
                    const response = await fetch('/queue/messages/clear-dead-letter', {
                        method: 'DELETE'
                    });
                    const result = await response.json();
                    alert(`Cleared ${result.messages_cleared} messages`);
                    refreshData();
                } catch (error) {
                    alert('Error clearing dead letter queue');
                }
            }
            
            // Initialize
            initChart();
            refreshData();
            
            // Auto-refresh every 5 seconds
            setInterval(refreshData, 5000);
        </script>
    </body>
    </html>
    """
    return html

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para atualizações em tempo real"""
    await websocket.accept()
    
    try:
        while True:
            # Envia status atualizado a cada 2 segundos
            if whatsapp_service and whatsapp_service.message_queue:
                status = await whatsapp_service.message_queue.get_queue_status()
                await websocket.send_json({
                    "type": "status_update",
                    "data": status,
                    "timestamp": datetime.now().isoformat()
                })
            
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()