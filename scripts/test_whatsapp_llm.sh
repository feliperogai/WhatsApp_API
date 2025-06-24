echo "🔍 DIAGNÓSTICO COMPLETO - Jarvis WhatsApp LLM"
echo "============================================="

# Configurações
BASE_URL="http://localhost:8000"
OLLAMA_URL="http://192.168.15.31:11435"
PHONE_NUMBER="${1:-+5511999999999}"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Função para checar endpoint
check_endpoint() {
    local name="$1"
    local url="$2"
    local expected="$3"
    
    echo -n -e "${BLUE}Checking $name...${NC} "
    
    response=$(curl -s "$url")
    
    if [[ "$response" == *"$expected"* ]]; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo -e "${YELLOW}Response: ${response:0:100}...${NC}"
        return 1
    fi
}

echo -e "${PURPLE}1. VERIFICANDO INFRAESTRUTURA${NC}"
echo "----------------------------------------"

# 1.1 Verifica se aplicação está rodando
check_endpoint "Application" "$BASE_URL" "Jarvis"

# 1.2 Health check
check_endpoint "Health Check" "$BASE_URL/health" "healthy"

# 1.3 LLM Status
echo -n -e "${BLUE}Checking LLM Status...${NC} "
llm_status=$(curl -s "$BASE_URL/llm/status" | jq -r '.status' 2>/dev/null)
if [[ "$llm_status" == "online" ]]; then
    echo -e "${GREEN}✅ LLM Online${NC}"
else
    echo -e "${RED}❌ LLM Offline (status: $llm_status)${NC}"
fi

# 1.4 Ollama direto
echo -n -e "${BLUE}Checking Ollama Direct...${NC} "
if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama Accessible${NC}"
    models=$(curl -s "$OLLAMA_URL/api/tags" | jq -r '.models[].name' 2>/dev/null | head -5)
    echo -e "${YELLOW}Available models:${NC}"
    echo "$models" | sed 's/^/  - /'
else
    echo -e "${RED}❌ Ollama NOT Accessible${NC}"
fi

echo ""
echo -e "${PURPLE}2. TESTANDO LLM${NC}"
echo "----------------------------------------"

# 2.1 Teste direto do LLM via aplicação
echo -e "${BLUE}Testing LLM via application...${NC}"
llm_response=$(curl -s -X POST "$BASE_URL/llm/test" \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Diga apenas: FUNCIONANDO"}' \
    | jq -r '.response' 2>/dev/null)

if [[ "$llm_response" == *"FUNCIONANDO"* ]]; then
    echo -e "${GREEN}✅ LLM working: '$llm_response'${NC}"
else
    echo -e "${RED}❌ LLM not responding properly${NC}"
    echo -e "${YELLOW}Full response:${NC}"
    curl -s -X POST "$BASE_URL/llm/test" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Diga apenas: FUNCIONANDO"}' | jq . 2>/dev/null
fi

echo ""
echo -e "${PURPLE}3. TESTANDO WEBHOOK WHATSAPP (MODO SYNC)${NC}"
echo "----------------------------------------"

# 3.1 Teste simples
echo -e "${BLUE}Sending test message 'Olá'...${NC}"
webhook_response=$(curl -s -X POST "$BASE_URL/webhook/whatsapp" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "From=whatsapp:$PHONE_NUMBER&Body=Olá&MessageSid=TEST_$(date +%s)" \
    | grep -o '<Message>.*</Message>' | sed 's/<[^>]*>//g')

if [[ -n "$webhook_response" ]]; then
    echo -e "${GREEN}✅ Webhook Response:${NC}"
    echo "$webhook_response" | head -5
else
    echo -e "${RED}❌ No webhook response${NC}"
fi

echo ""

# 3.2 Teste com diferentes mensagens
test_messages=(
    "Preciso de um relatório de vendas"
    "Sistema está com erro"
    "Quero agendar uma reunião"
    "Menu"
)

echo -e "${BLUE}Testing different intents...${NC}"
for msg in "${test_messages[@]}"; do
    echo -e "\n${YELLOW}Testing: '$msg'${NC}"
    
    response=$(curl -s -X POST "$BASE_URL/webhook/whatsapp" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "From=whatsapp:$PHONE_NUMBER&Body=$msg&MessageSid=TEST_$(date +%s)_$RANDOM" \
        | grep -o '<Message>.*</Message>' | sed 's/<[^>]*>//g')
    
    if [[ -n "$response" ]]; then
        echo -e "${GREEN}Response:${NC} ${response:0:200}..."
    else
        echo -e "${RED}No response${NC}"
    fi
done

echo ""
echo -e "${PURPLE}4. VERIFICANDO SISTEMA DE FILA${NC}"
echo "----------------------------------------"

# 4.1 Status da fila
echo -e "${BLUE}Queue Status:${NC}"
queue_status=$(curl -s "$BASE_URL/queue/status")
if [[ -n "$queue_status" ]]; then
    echo "$queue_status" | jq '{pending, processing, workers, circuit_breaker}' 2>/dev/null || echo "$queue_status"
else
    echo -e "${RED}Could not get queue status${NC}"
fi

echo ""
echo -e "${PURPLE}5. TESTANDO WEBHOOK ASYNC (OPCIONAL)${NC}"
echo "----------------------------------------"

echo -e "${BLUE}Testing async webhook...${NC}"
async_response=$(curl -s -X POST "$BASE_URL/webhook/whatsapp/async" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "From=whatsapp:$PHONE_NUMBER&Body=Teste async&MessageSid=ASYNC_$(date +%s)")

echo -e "${YELLOW}Async response:${NC} $async_response"

echo ""
echo -e "${PURPLE}6. VERIFICANDO LOGS${NC}"
echo "----------------------------------------"

echo -e "${BLUE}Recent application logs:${NC}"
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose logs --tail=10 jarvis-whatsapp 2>/dev/null | grep -E "(ERROR|WARNING|LLM|Ollama)" | tail -5
else
    echo "Docker Compose not available"
fi

echo ""
echo -e "${PURPLE}7. DIAGNÓSTICO FINAL${NC}"
echo "----------------------------------------"

# Conta problemas
problems=0

# Verifica componentes críticos
echo -e "${BLUE}Component Status:${NC}"

# App health
if curl -s "$BASE_URL/health" | grep -q "healthy" 2>/dev/null; then
    echo -e "  Application: ${GREEN}✅ Healthy${NC}"
else
    echo -e "  Application: ${RED}❌ Unhealthy${NC}"
    problems=$((problems + 1))
fi

# LLM
if [[ "$llm_status" == "online" ]]; then
    echo -e "  LLM Service: ${GREEN}✅ Online${NC}"
else
    echo -e "  LLM Service: ${RED}❌ Offline${NC}"
    problems=$((problems + 1))
fi

# Ollama
if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "  Ollama: ${GREEN}✅ Accessible${NC}"
else
    echo -e "  Ollama: ${RED}❌ Not Accessible${NC}"
    problems=$((problems + 1))
fi

# Webhook
if [[ -n "$webhook_response" ]]; then
    echo -e "  WhatsApp Webhook: ${GREEN}✅ Working${NC}"
else
    echo -e "  WhatsApp Webhook: ${RED}❌ Not Working${NC}"
    problems=$((problems + 1))
fi

echo ""
if [[ $problems -eq 0 ]]; then
    echo -e "${GREEN}✅ SISTEMA TOTALMENTE OPERACIONAL!${NC}"
    echo ""
    echo -e "${BLUE}Próximos passos:${NC}"
    echo "1. Configure o webhook no Twilio: $BASE_URL/webhook/whatsapp"
    echo "2. Use ngrok se necessário: ngrok http 8000"
    echo "3. Teste enviando mensagem real via WhatsApp"
else
    echo -e "${RED}❌ PROBLEMAS DETECTADOS: $problems${NC}"
    echo ""
    echo -e "${YELLOW}Soluções recomendadas:${NC}"
    
    if [[ "$llm_status" != "online" ]]; then
        echo "1. Verifique configuração do Ollama no .env"
        echo "   OLLAMA_URLS=$OLLAMA_URL"
        echo "   OLLAMA_MODELS=llama3.1:8b"
    fi
    
    if ! curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        echo "2. Verifique se Ollama está rodando em $OLLAMA_URL"
        echo "   No servidor Ollama: ollama serve"
    fi
    
    if [[ -z "$webhook_response" ]]; then
        echo "3. Verifique logs para erros no webhook:"
        echo "   docker-compose logs -f jarvis-whatsapp"
    fi
fi

echo ""
echo "============================================="
echo -e "${PURPLE}Diagnóstico completo!${NC}"
echo "============================================="