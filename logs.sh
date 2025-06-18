echo "📊 Logs do Jarvis WhatsApp Agent Orchestrator"
echo "============================================="

# Se parametro passado, mostra logs de serviço específico
if [ ! -z "$1" ]; then
    echo "Logs do serviço: $1"
    docker-compose logs -f "$1"
else
    echo "Logs de todos os serviços (Ctrl+C para sair)"
    docker-compose logs -f
fi