echo "🚀 Jarvis WhatsApp Setup v2.0"
echo "============================="

# Detecta o diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Se estiver em scripts/, volta para raiz
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

cd "$PROJECT_ROOT"
echo "📁 Working directory: $PROJECT_ROOT"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found. Please install Docker."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose not found. Please install Docker Compose."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 not found. Please install Python 3."; exit 1; }

# Create .env if not exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📝 Created .env file from .env.example"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and configure:"
        echo "   1. Twilio credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)"
        echo "   2. Ollama URL (default: http://localhost:11434)"
        echo "   3. Redis password if needed"
        echo ""
        echo "Press Enter to continue after editing .env..."
        read
    else
        echo "❌ .env.example not found!"
        exit 1
    fi
fi

# Validate .env has required fields
if ! grep -q "TWILIO_ACCOUNT_SID=" .env || grep -q "TWILIO_ACCOUNT_SID=your_account_sid" .env; then
    echo "❌ Please configure TWILIO_ACCOUNT_SID in .env"
    exit 1
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data

# Fix permissions for scripts
echo "🔧 Setting executable permissions..."
chmod +x scripts/*.sh

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt || {
        echo "⚠️  Failed to install some dependencies. Trying with --user flag..."
        pip3 install --user -r requirements.txt
    }
else
    echo "❌ requirements.txt not found!"
    exit 1
fi

# Check Ollama connection
OLLAMA_URL=$(grep OLLAMA_URL .env | cut -d'=' -f2 | tr -d ' ' || echo "http://localhost:11434")
echo "🔍 Checking Ollama at $OLLAMA_URL..."

if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo "✅ Ollama is accessible"
    
    # Check if model exists
    MODEL=$(grep OLLAMA_MODEL .env | cut -d'=' -f2 | tr -d ' ' || echo "llama3.1:8b")
    if curl -s "$OLLAMA_URL/api/tags" | grep -q "$MODEL"; then
        echo "✅ Model $MODEL is available"
    else
        echo "⚠️  Model $MODEL not found. Pulling it now..."
        ollama pull $MODEL || echo "⚠️  Failed to pull model. Please run: ollama pull $MODEL"
    fi
else
    echo "⚠️  Warning: Ollama not accessible at $OLLAMA_URL"
    echo "   Make sure Ollama is running: ollama serve"
    echo "   Or update OLLAMA_URL in .env"
fi

# Build and start
echo ""
echo "🐳 Building Docker containers..."
docker-compose build || { echo "❌ Docker build failed"; exit 1; }

echo ""
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo ""
        echo "✅ Application is running!"
        break
    fi
    echo -n "."
    sleep 1
done

# Final status
echo ""
echo "═══════════════════════════════════════════════════════"
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✅ SETUP COMPLETED SUCCESSFULLY!"
    echo ""
    echo "📱 WhatsApp webhook URL: http://localhost:8000/webhook/whatsapp"
    echo "📊 Dashboard: http://localhost:8000"
    echo "📈 Queue Monitor: http://localhost:8000/queue/dashboard"
    echo ""
    echo "🔍 Useful commands:"
    echo "   View logs: docker-compose logs -f"
    echo "   Test LLM: ./scripts/test_llm.sh"
    echo "   Monitor: ./scripts/monitor_llm.sh"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Configure Twilio webhook URL (use ngrok if needed)"
    echo "   2. Test with: curl -X POST http://localhost:8000/webhook/whatsapp -d 'From=whatsapp:+5511999999999&Body=Oi&MessageSid=TEST123'"
else
    echo "❌ Application failed to start"
    echo ""
    echo "Debug commands:"
    echo "   Check logs: docker-compose logs"
    echo "   Check containers: docker-compose ps"
    echo "   Restart: docker-compose restart"
fi
echo "═══════════════════════════════════════════════════════"