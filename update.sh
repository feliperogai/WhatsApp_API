echo "🔄 Atualizando Jarvis WhatsApp Agent Orchestrator"
echo "==============================================="

# Para serviços
echo "Parando serviços..."
docker-compose down

# Atualiza código (se usando git)
if [ -d ".git" ]; then
    echo "📥 Atualizando código..."
    git pull origin main
fi

# Rebuild imagens
echo "🔨 Reconstruindo imagens..."
docker-compose build --no-cache

# Reinicia
echo "🚀 Reiniciando serviços..."
docker-compose up -d

echo "✅ Atualização concluída!"