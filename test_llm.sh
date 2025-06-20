#!/bin/bash

echo "🧪 Teste Rápido - Jarvis WhatsApp LLM v2.0"
echo "=========================================="

BASE_URL="http://localhost:8000"
OLLAMA_URL="http://192.168.15.31:11435"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Função para teste
test_endpoint() {
    local name="$1"
    local url="$2"
    local method="${3:-GET}"
    local data="$4"
    
    echo -n -e "${BLUE}🔍 $name...${NC} "
    
    if [ "$method" = "GET" ]; then
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ OK${NC}"
            return 0
        else
            echo -e "${RED}❌ FALHOU${NC}"
            return 1
        fi
    else
        if curl -s -X "$method" "$url" -H "Content-Type: application/json" -d "$data" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ OK${NC}"
            return 0
        else
            echo -e "${RED}❌ FALHOU${NC}"
            return 1
        fi
    fi
}

echo "1. Testando infraestrutura básica..."
echo "───────────────────────────────────────"

test_endpoint "Health Check" "$BASE_URL/health"
test_endpoint "Status Geral" "$BASE_URL/status"
test_endpoint "Status LLM" "$BASE_URL/llm/status"

echo ""
echo "2. Testando Ollama diretamente..."
echo "───────────────────────────────────────"

# Teste direto do Ollama com sua configuração exata
echo -n -e "${BLUE}🧠 Ollama direto...${NC} "
ollama_response=$(curl -s "$OLLAMA_URL/api/chat" -X POST \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1:8b", "messages": [{"role": "user", "content": "Responda apenas: OK"}]}' \
  | jq -r '.message.content' 2>/dev/null | tr -d '\n')

if [ -n "$ollama_response" ]; then
    echo -e "${GREEN}✅ OK - Resposta: '$ollama_response'${NC}"
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

echo ""
echo "3. Testando LLM via aplicação..."
echo "───────────────────────────────────────"

# Teste via aplicação
echo -n -e "${BLUE}🤖 LLM via App...${NC} "
app_response=$(curl -s -X POST "$BASE_URL/llm/test" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Responda apenas: FUNCIONANDO"}' \
  | jq -r '.response' 2>/dev/null)

if [ -n "$app_response" ]; then
    echo -e "${GREEN}✅ OK - Resposta: '$app_response'${NC}"
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

echo ""
echo "4. Testando conversas inteligentes..."
echo "───────────────────────────────────────"

# Testes de classificação
test_messages=(
    "Olá, preciso de ajuda"
    "Quero um relatório de vendas"
    "O sistema está com erro"
    "Preciso agendar uma reunião"
)

for msg in "${test_messages[@]}"; do
    echo -n -e "${BLUE}💬 '$msg'...${NC} "
    
    response=$(curl -s -X POST "$BASE_URL/llm/test" \
        -H "Content-Type: application/json" \
        -d "{\"prompt\": \"Como agente de classificação, qual agente deve responder: '$msg'\"}" \
        | jq -r '.response' 2>/dev/null)
    
    if [ -n "$response" ]; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ FALHOU${NC}"
    fi
done

echo ""
echo "5. Testando envio de mensagem..."
echo "───────────────────────────────────────"

if [ ! -z "$1" ]; then
    echo -e "${BLUE}📱 Enviando teste para $1...${NC}"
    
    send_response=$(curl -s -X POST "$BASE_URL/send" \
        -H "Content-Type: application/json" \
        -d "{\"phone_number\": \"$1\", \"message\": \"🤖 Teste do Jarvis LLM v2.0 - Sistema funcionando perfeitamente!\"}")
    
    if echo "$send_response" | grep -q "sent"; then
        echo -e "${GREEN}✅ Mensagem enviada com sucesso!${NC}"
    else
        echo -e "${RED}❌ Erro no envio${NC}"
    fi
else
    echo -e "${YELLOW}💡 Para testar envio: ./test_llm.sh +5511999999999${NC}"
fi

echo ""
echo "6. Status dos containers..."
echo "───────────────────────────────────────"

if command -v docker-compose >/dev/null 2>&1; then
    docker-compose ps
else
    echo "Docker Compose não disponível"
fi

echo ""
echo "═══════════════════════════════════════"
echo -e "${BLUE}📊 RESUMO DOS TESTES${NC}"
echo "═══════════════════════════════════════"

# Verifica status geral
health_ok=$(curl -s "$BASE_URL/health" | grep -c "healthy" || echo "0")
llm_ok=$(curl -s "$BASE_URL/llm/status" | grep -c "online" || echo "0")
ollama_ok=$(curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && echo "1" || echo "0")

if [ "$health_ok" -gt 0 ] && [ "$llm_ok" -gt 0 ] && [ "$ollama_ok" -gt 0 ]; then
    echo -e "${GREEN}✅ SISTEMA TOTALMENTE OPERACIONAL!${NC}"
    echo -e "${GREEN}✅ Ollama conectado e respondendo${NC}"
    echo -e "${GREEN}✅ Aplicação LLM funcionando${NC}"
    echo -e "${GREEN}✅ Agentes IA ativos${NC}"
    
    echo ""
    echo -e "${BLUE}🎯 PRÓXIMOS PASSOS:${NC}"
    echo "1. Configure webhook no Twilio"
    echo "2. Teste conversas via WhatsApp"
    echo "3. Monitore: ./monitor_llm.sh"
    echo "4. Dashboard: http://localhost:8000"
    
    echo ""
    echo -e "${PURPLE}🤖 Jarvis está pronto para conversar! 🚀${NC}"
    
else
    echo -e "${RED}❌ PROBLEMAS DETECTADOS${NC}"
    
    if [ "$ollama_ok" -eq 0 ]; then
        echo -e "${RED}❌ Ollama não está respondendo${NC}"
        echo "Verifique: curl -s $OLLAMA_URL/api/tags"
    fi
    
    if [ "$health_ok" -eq 0 ]; then
        echo -e "${RED}❌ Aplicação não está saudável${NC}"
        echo "Verifique logs: docker-compose logs"
    fi
    
    echo ""
    echo -e "${YELLOW}🔧 PARA RESOLVER:${NC}"
    echo "1. Verifique se Ollama está rodando"
    echo "2. Verifique logs: docker-compose logs"
    echo "3. Reinicie: docker-compose restart"
fi

echo ""
echo -e "${BLUE}🤖 Teste concluído!${NC}"