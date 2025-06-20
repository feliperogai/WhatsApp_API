#!/bin/bash

echo "🤖 Setup Rápido - Jarvis WhatsApp LLM v2.0"
echo "=========================================="
echo "Configuração otimizada para Ollama em: http://192.168.15.31:11435"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Função para verificar se comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo -e "${BLUE}📋 Verificando pré-requisitos...${NC}"

# Verifica Docker
if ! command_exists docker; then
    echo -e "${RED}❌ Docker não encontrado${NC}"
    exit 1
fi

# Verifica Docker Compose
if ! command_exists docker-compose; then
    echo -e "${RED}❌ Docker Compose não encontrado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker OK${NC}"

# Testa conexão com Ollama
echo -e "${YELLOW}🔍 Testando Ollama...${NC}"
OLLAMA_URL="http://192.168.15.31:11435"

if curl -s "$OLLAMA_URL/api/chat" -X POST \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1:8b", "messages": [{"role": "user", "content": "teste"}]}' >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama respondendo perfeitamente!${NC}"
else
    echo -e "${RED}❌ Ollama não está respondendo em $OLLAMA_URL${NC}"
    echo "Verifique se o Ollama está rodando:"
    echo "  ollama serve"
    echo "  ollama pull llama3.1:8b"
    exit 1
fi

# Cria/verifica .env
echo -e "${YELLOW}📄 Configurando .env...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✅ Arquivo .env criado${NC}"
else
    echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
fi

# Atualiza configuração do Ollama no .env
sed -i 's|OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL=http://192.168.15.31:11435|' .env
sed -i 's|OLLAMA_MODEL=.*|OLLAMA_MODEL=llama3.1:8b|' .env

# Cria diretórios
echo -e "${YELLOW}📁 Criando diretórios...${NC}"
mkdir -p logs

# Para containers antigos
echo -e "${YELLOW}🛑 Parando containers antigos...${NC}"
docker-compose down 2>/dev/null || true

# Build
echo -e "${YELLOW}🔨 Construindo aplicação...${NC}"
docker-compose build

# Inicia serviços
echo -e "${YELLOW}🚀 Iniciando serviços...${NC}"
docker-compose up -d

# Aguarda inicialização
echo -e "${YELLOW}⏳ Aguardando inicialização...${NC}"
sleep 10

# Testa aplicação
echo -e "${YELLOW}🧪 Testando aplicação...${NC}"
max_attempts=12
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Aplicação respondendo!${NC}"
        break
    fi
    
    attempt=$((attempt + 1))
    echo -n "."
    sleep 5
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}❌ Timeout - aplicação não respondeu${NC}"
    echo "Verifique os logs:"
    echo "  docker-compose logs jarvis-whatsapp-llm"
    exit 1
fi

# Teste LLM
echo -e "${YELLOW}🧠 Testando LLM...${NC}"
llm_response=$(curl -s -X POST http://localhost:8000/llm/test \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Diga apenas: OK"}' | grep -o '"response":"[^"]*"' | cut -d'"' -f4)

if [ -n "$llm_response" ]; then
    echo -e "${GREEN}✅ LLM funcionando: $llm_response${NC}"
else
    echo -e "${YELLOW}⚠️ LLM pode estar inicializando...${NC}"
fi

# Sucesso!
echo ""
echo -e "${PURPLE}🎉 JARVIS LLM CONFIGURADO COM SUCESSO! 🎉${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""
echo -e "${GREEN}🌐 Aplicação:${NC} http://localhost:8000"
echo -e "${GREEN}📊 Status:${NC} http://localhost:8000/status"
echo -e "${GREEN}🧠 LLM Status:${NC} http://localhost:8000/llm/status"
echo ""
echo -e "${BLUE}🧪 Teste manual do LLM:${NC}"
echo "curl -X POST http://localhost:8000/llm/test \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"prompt\": \"Olá, como você está?\"}'"
echo ""
echo -e "${YELLOW}📱 Configure webhook no Twilio:${NC}"
echo "  URL: [SEU_NGROK_URL]/webhook/whatsapp"
echo "  Method: POST"
echo ""
echo -e "${GREEN}🔍 Logs em tempo real:${NC}"
echo "  docker-compose logs -f"
echo ""
echo -e "${BLUE}🎯 Próximos passos:${NC}"
echo "  1. Configure webhook no Twilio"
echo "  2. Teste via WhatsApp"
echo "  3. Monitore com: ./monitor_llm.sh"
echo ""
echo -e "${PURPLE}Sistema pronto para conversas inteligentes! 🤖${NC}"