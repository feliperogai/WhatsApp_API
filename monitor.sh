echo "📊 Monitor do Jarvis WhatsApp Agent Orchestrator"
echo "=============================================="

while true; do
    clear
    echo "📊 DASHBOARD JARVIS WHATSAPP - $(date)"
    echo "====================================="
    echo ""
    
    # Status dos containers
    echo "🐳 CONTAINERS:"
    docker-compose ps
    echo ""
    
    # Uso de recursos
    echo "💾 USO DE RECURSOS:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker-compose ps -q)
    echo ""
    
    # Health check da aplicação
    echo "🔍 HEALTH CHECK:"
    curl -s http://localhost:8000/health | jq . 2>/dev/null || echo "❌ Aplicação não responsiva"
    echo ""
    
    # Logs recentes (últimas 5 linhas)
    echo "📝 LOGS RECENTES:"
    docker-compose logs --tail=5 jarvis-whatsapp
    echo ""
    
    echo "Pressione Ctrl+C para sair | Atualizando a cada 10s..."
    sleep 10
done