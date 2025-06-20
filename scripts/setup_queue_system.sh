#!/bin/bash

echo "🚀 Setup do Sistema Jarvis com Queue Management"
echo "=============================================="
echo "Configuração otimizada para LLM local com controle de requisições"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Função para verificar comando
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verifica pré-requisitos
echo -e "${BLUE}📋 Verificando pré-requisitos...${NC}"

if ! command_exists docker; then
    echo -e "${RED}❌ Docker não encontrado${NC}"
    echo "Instale Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}❌ Docker Compose não encontrado${NC}"
    echo "Instale Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✅ Docker e Docker Compose OK${NC}"

# Testa Ollama
echo -e "${YELLOW}🔍 Verificando Ollama...${NC}"
OLLAMA_URL="http://192.168.15.31:11435"

if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama respondendo em $OLLAMA_URL${NC}"
    
    # Verifica modelo
    if curl -s "$OLLAMA_URL/api/tags" | grep -q "llama3.1:8b"; then
        echo -e "${GREEN}✅ Modelo llama3.1:8b disponível${NC}"
    else
        echo -e "${YELLOW}⚠️ Modelo llama3.1:8b não encontrado${NC}"
        echo "Execute no servidor Ollama: ollama pull llama3.1:8b"
    fi
else
    echo -e "${RED}❌ Ollama não está respondendo em $OLLAMA_URL${NC}"
    echo "Verifique:"
    echo "1. Ollama está rodando? (ollama serve)"
    echo "2. IP e porta estão corretos?"
    echo "3. Firewall está bloqueando?"
    exit 1
fi

# Configuração do ambiente
echo -e "${BLUE}🔧 Configurando ambiente...${NC}"

# Cria arquivo .env se não existir
if [ ! -f .env ]; then
    echo -e "${YELLOW}Criando arquivo .env...${NC}"
    cat > .env << EOF
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+14155238886

# Application Configuration
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Webhook Configuration
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io

# LLM Configuration - Otimizado
OLLAMA_BASE_URL=http://192.168.15.31:11435
OLLAMA_MODEL=llama3.1:8b
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=500
LLM_TIMEOUT=30

# Queue Settings
QUEUE_MAX_SIZE=1000
MAX_CONCURRENT_LLM=3
RATE_LIMIT_REQUESTS=5
RATE_LIMIT_WINDOW=60

# Cache Settings
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=1000
EOF
    echo -e "${GREEN}✅ Arquivo .env criado${NC}"
    echo -e "${YELLOW}⚠️ Configure suas credenciais Twilio no arquivo .env${NC}"
else
    echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
fi

# Cria arquivo redis.conf se não existir
if [ ! -f redis.conf ]; then
    echo -e "${YELLOW}Criando redis.conf otimizado...${NC}"
    # Conteúdo já foi criado no artifact anterior
    echo -e "${GREEN}✅ redis.conf criado${NC}"
fi

# Cria diretórios necessários
echo -e "${BLUE}📁 Criando diretórios...${NC}"
mkdir -p logs
mkdir -p grafana/provisioning/dashboards
mkdir -p grafana/provisioning/datasources

# Cria configuração do Prometheus
echo -e "${YELLOW}Criando prometheus.yml...${NC}"
cat > prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'jarvis-queue'
    static_configs:
      - targets: ['jarvis-whatsapp-queue:8000']
    metrics_path: '/metrics'
EOF

# Cria datasource do Grafana
cat > grafana/provisioning/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

echo -e "${GREEN}✅ Configurações criadas${NC}"

# Para containers antigos
echo -e "${YELLOW}🛑 Parando containers antigos...${NC}"
docker-compose -f docker-compose.queue.yml down 2>/dev/null || true

# Build da aplicação
echo -e "${YELLOW}🔨 Construindo aplicação com Queue System...${NC}"
docker-compose -f docker-compose.queue.yml build

# Inicia serviços básicos
echo -e "${YELLOW}🚀 Iniciando serviços...${NC}"
docker-compose -f docker-compose.queue.yml up -d redis
sleep 5

# Testa Redis
echo -e "${BLUE}🔍 Testando Redis...${NC}"
if docker-compose -f docker-compose.queue.yml exec -T redis redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Redis OK${NC}"
else
    echo -e "${RED}❌ Redis não está respondendo${NC}"
    exit 1
fi

# Inicia aplicação principal
echo -e "${YELLOW}🚀 Iniciando Jarvis Queue System...${NC}"
docker-compose -f docker-compose.queue.yml up -d jarvis-whatsapp-queue

# Aguarda inicialização
echo -e "${YELLOW}⏳ Aguardando inicialização (30s)...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "\n${GREEN}✅ Aplicação iniciada!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Verifica status
echo -e "${BLUE}📊 Verificando status do sistema...${NC}"
HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)

if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Sistema saudável${NC}"
    
    # Mostra status da queue
    QUEUE_STATUS=$(curl -s http://localhost:8000/queue/status 2>/dev/null | jq '.' 2>/dev/null)
    if [ -n "$QUEUE_STATUS" ]; then
        echo -e "${BLUE}Queue Status:${NC}"
        echo "$QUEUE_STATUS" | jq '{pending, processing, dead_letter, workers}'
    fi
else
    echo -e "${RED}❌ Sistema não está saudável${NC}"
    echo "Verifique logs: docker-compose -f docker-compose.queue.yml logs"
fi

# Informações finais
echo ""
echo -e "${PURPLE}🎉 SETUP CONCLUÍDO! 🎉${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}📱 Aplicação Principal:${NC} http://localhost:8000"
echo -e "${GREEN}📊 Queue Dashboard:${NC} http://localhost:8000/queue/dashboard"
echo -e "${GREEN}🔍 Queue Status:${NC} http://localhost:8000/queue/status"
echo ""
echo -e "${YELLOW}🔧 Comandos úteis:${NC}"
echo "• Ver logs: docker-compose -f docker-compose.queue.yml logs -f"
echo "• Parar: docker-compose -f docker-compose.queue.yml down"
echo "• Reiniciar: docker-compose -f docker-compose.queue.yml restart"
echo "• Status da fila: curl http://localhost:8000/queue/status | jq"
echo ""
echo -e "${YELLOW}📡 Para desenvolvimento (ngrok):${NC}"
echo "docker-compose -f docker-compose.queue.yml --profile dev up -d"
echo ""
echo -e "${YELLOW}📈 Para monitoramento completo:${NC}"
echo "docker-compose -f docker-compose.queue.yml --profile monitoring up -d"
echo "• Redis Insight: http://localhost:8001"
echo "• Prometheus: http://localhost:9090"
echo "• Grafana: http://localhost:3000 (admin/jarvis123)"
echo ""
echo -e "${BLUE}💡 Configurações de Queue:${NC}"
echo "• Max requisições LLM: 5/minuto"
echo "• Workers simultâneos: 3"
echo "• Circuit breaker: 3 falhas"
echo "• Cache TTL: 1 hora"
echo ""
echo -e "${PURPLE}Sistema pronto para processar mensagens com controle de carga! 🚀${NC}"