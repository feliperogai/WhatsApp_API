echo "🚀 Iniciando Jarvis WhatsApp Agent Orchestrator"

# Verifica se .env existe
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado. Execute setup.sh primeiro."
    exit 1
fi

# Inicia serviços
echo "Starting services..."
docker-compose up -d

# Aguarda e verifica
sleep 5
if docker-compose ps | grep -q "Up"; then
    echo "✅ Serviços iniciados!"
    echo "🌐 Aplicação disponível em: http://localhost:8000"
else
    echo "❌ Erro ao iniciar. Verifique: docker-compose logs"
fi

# 📄 stop.sh  
#!/bin/bash

echo "🛑 Parando Jarvis WhatsApp Agent Orchestrator"

docker-compose down

echo "✅ Serviços parados"