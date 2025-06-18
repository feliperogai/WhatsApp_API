echo "💾 Backup do Jarvis WhatsApp Agent Orchestrator"
echo "============================================="

# Cria diretório de backup com timestamp
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📁 Criando backup em: $BACKUP_DIR"

# Backup do código
echo "📄 Backup do código..."
cp -r app/ "$BACKUP_DIR/"
cp *.py "$BACKUP_DIR/" 2>/dev/null || true
cp *.yml "$BACKUP_DIR/" 2>/dev/null || true
cp *.yaml "$BACKUP_DIR/" 2>/dev/null || true
cp .env.example "$BACKUP_DIR/"
cp requirements.txt "$BACKUP_DIR/"
cp Dockerfile "$BACKUP_DIR/"

# Backup dos logs
echo "📊 Backup dos logs..."
cp -r logs/ "$BACKUP_DIR/" 2>/dev/null || true

# Backup do Redis (se rodando)
if docker-compose ps redis | grep -q "Up"; then
    echo "🗄️ Backup do Redis..."
    docker-compose exec -T redis redis-cli BGSAVE
    sleep 2
    docker cp "$(docker-compose ps -q redis)":/data/dump.rdb "$BACKUP_DIR/"
fi

# Compacta backup
echo "🗜️ Compactando backup..."
tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "✅ Backup criado: ${BACKUP_DIR}.tar.gz"

chmod +x *.sh
echo ""
echo "🎉 SCRIPTS DE GERENCIAMENTO CRIADOS!"
echo "===================================="
echo ""
echo "📋 Scripts disponíveis:"
echo "  ./setup.sh              - Configuração inicial completa"
echo "  ./start.sh              - Inicia os serviços"
echo "  ./stop.sh               - Para os serviços"  
echo "  ./restart.sh            - Reinicia os serviços"
echo "  ./logs.sh               - Visualiza logs em tempo real"
echo "  ./test.sh [número]      - Testa a aplicação"
echo "  ./monitor.sh            - Dashboard de monitoramento"
echo "  ./backup.sh             - Cria backup completo"
echo "  ./update.sh             - Atualiza o sistema"
echo "  ./install_dependencies.sh - Instala Docker/dependências"
echo ""
echo "🚀 Para começar:"
echo "  1. Execute: ./install_dependencies.sh (se necessário)"
echo "  2. Execute: ./setup.sh"
echo "  3. Configure suas credenciais no .env"
echo "  4. Execute: ./start.sh"
echo ""
echo "📱 Configure o webhook no Twilio:"
echo "  URL: https://seu-ngrok-url.ngrok.io/webhook/whatsapp"
echo "  Method: POST"