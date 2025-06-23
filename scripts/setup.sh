#!/bin/bash

echo "🚀 Jarvis WhatsApp Setup"
echo "======================="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found. Please install Docker."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose not found. Please install Docker Compose."; exit 1; }

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env file. Please configure your credentials."
    echo "   Edit .env and add your Twilio credentials"
    exit 1
fi

# Check Ollama connection
OLLAMA_URL=$(grep OLLAMA_URLS .env | cut -d'=' -f2 | cut -d',' -f1)
echo "🔍 Checking Ollama at $OLLAMA_URL..."

if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo "✅ Ollama is accessible"
else
    echo "⚠️  Warning: Ollama not accessible at $OLLAMA_URL"
    echo "   Make sure Ollama is running or update OLLAMA_URLS in .env"
fi

# Create directories
mkdir -p logs

# Build and start
echo "🔨 Building application..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 10

# Check health
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ Application is running!"
    echo ""
    echo "📱 WhatsApp webhook URL: http://localhost:8000/webhook/whatsapp"
    echo "📊 Dashboard: http://localhost:8000"
    echo "📈 Metrics: http://localhost:8000/metrics"
    echo ""
    echo "🔍 View logs: docker-compose logs -f"
else
    echo "❌ Application failed to start"
    echo "Check logs: docker-compose logs"
fi