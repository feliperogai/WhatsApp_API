#!/bin/bash

echo "🔍 Teste de Integração Ollama + Jarvis"
echo "======================================"

# Configurações
OLLAMA_URL="http://192.168.15.31:11435"
APP_URL="http://localhost:8000"
MODEL="llama3.1:8b"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Função de teste
test_endpoint() {
    local name="$1"
    local cmd="$2"
    
    echo -n -e "${BLUE}Testing $name...${NC} "
    
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo -e "${YELLOW}Command: $cmd${NC}"
        return 1
    fi
}

echo -e "${PURPLE}1. Testando Ollama Direto${NC}"
echo "----------------------------------------"

# Teste 1: Ollama tags
test_endpoint "Ollama API" "curl -s $OLLAMA_URL/api/tags"

# Teste 2: Ollama chat direto
echo -n -e "${BLUE}Testing Ollama Chat...${NC} "
OLLAMA_RESPONSE=$(curl -s "$OLLAMA_URL/api/chat" -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Diga apenas: FUNCIONANDO\"}],
    \"stream\": false
  }" | jq -r '.message.content' 2>/dev/null)

if [[ "$OLLAMA_RESPONSE" == *"FUNCIONANDO"* ]]; then
    echo -e "${GREEN}✅ PASS - Response: '$OLLAMA_RESPONSE'${NC}"
else
    echo -e "${RED}❌ FAIL - Response: '$OLLAMA_RESPONSE'${NC}"
fi

echo ""
echo -e "${PURPLE}2. Testando Aplicação${NC}"
echo "----------------------------------------"

# Espera aplicação iniciar
echo -e "${YELLOW}Aguardando aplicação iniciar...${NC}"
for i in {1..10}; do
    if curl -s "$APP_URL/health" >/dev/null 2>&1; then
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Teste 3: Health check
test_endpoint "App Health" "curl -s $APP_URL/health"

# Teste 4: LLM Status
echo -n -e "${BLUE}Testing LLM Status...${NC} "
LLM_STATUS=$(curl -s "$APP_URL/llm/status" | jq -r '.status' 2>/dev/null)
if [[ "$LLM_STATUS" == "online" ]]; then
    echo -e "${GREEN}✅ PASS - LLM is online${NC}"
else
    echo -e "${RED}❌ FAIL - LLM status: $LLM_STATUS${NC}"
fi

echo ""
echo -e "${PURPLE}3. Testando Integração LLM${NC}"
echo "----------------------------------------"

# Teste 5: LLM via aplicação
echo -n -e "${BLUE}Testing LLM Integration...${NC} "
APP_LLM_RESPONSE=$(curl -s -X POST "$APP_URL/llm/test" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Responda em uma palavra: INTEGRADO"}' \
  | jq -r '.response' 2>/dev/null)

if [[ "$APP_LLM_RESPONSE" == *"INTEGRADO"* ]]; then
    echo -e "${GREEN}✅ PASS - Response: '$APP_LLM_RESPONSE'${NC}"
else
    echo -e "${RED}❌ FAIL - Response: '$APP_LLM_RESPONSE'${NC}"
    echo -e "${YELLOW}Debug: Full response:${NC}"
    curl -s -X POST "$APP_URL/llm/test" \
      -H "Content-Type: application/json" \
      -d '{"prompt": "Responda em uma palavra: INTEGRADO"}' | jq .
fi

echo ""
echo -e "${PURPLE}4. Testando Webhook WhatsApp${NC}"
echo "----------------------------------------"

# Teste 6: Webhook com mensagem simples
echo -e "${BLUE}Simulando mensagem WhatsApp...${NC}"
WEBHOOK_RESPONSE=$(curl -s -X POST "$APP_URL/webhook/whatsapp" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+5511999999999&To=whatsapp:+14155238886&Body=Oi&MessageSid=SM12345" \
  | grep -o '<Message>.*</Message>' | sed 's/<[^>]*>//g')

if [[ -n "$WEBHOOK_RESPONSE" ]] && [[ "$WEBHOOK_RESPONSE" != *"erro"* ]]; then
    echo -e "${GREEN}✅ PASS - Webhook response:${NC}"
    echo "$WEBHOOK_RESPONSE" | head -100
else
    echo -e "${RED}❌ FAIL - No response or error${NC}"
fi

echo ""
echo -e "${PURPLE}5. Testando Classificação de Intenções${NC}"
echo "----------------------------------------"

# Array de mensagens teste
declare -A test_messages=(
    ["Olá, bom dia"]="reception"
    ["Preciso do relatório de vendas"]="data_query"
    ["Sistema está com erro"]="technical_support"
    ["Quero agendar reunião"]="scheduling"
)

for msg in "${!test_messages[@]}"; do
    expected="${test_messages[$msg]}"
    echo -e "${BLUE}Testing: '$msg' (expected: $expected)${NC}"
    
    CLASSIFICATION=$(curl -s -X POST "$APP_URL/webhook/whatsapp" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "From=whatsapp:+5511999999999&To=whatsapp:+14155238886&Body=$msg&MessageSid=SM$RANDOM" \
      | grep -o '<Message>.*</Message>' | sed 's/<[^>]*>//g')
    
    if [[ -n "$CLASSIFICATION" ]]; then
        echo -e "${GREEN}Response: ${NC}$CLASSIFICATION"
    else
        echo -e "${RED}No response${NC}"
    fi
    echo ""
done

echo ""
echo -e "${PURPLE}6. Teste de Performance${NC}"
echo "----------------------------------------"

echo -e "${BLUE}Medindo tempo de resposta...${NC}"
START_TIME=$(date +%s.%N)

curl -s -X POST "$APP_URL/llm/test" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Diga apenas: OK"}' >/dev/null

END_TIME=$(date +%s.%N)
RESPONSE_TIME=$(echo "$END_TIME - $START_TIME" | bc)

echo -e "Tempo de resposta LLM: ${YELLOW}${RESPONSE_TIME}s${NC}"

if (( $(echo "$RESPONSE_TIME < 5" | bc -l) )); then
    echo -e "${GREEN}✅ Performance OK (< 5s)${NC}"
else
    echo -e "${RED}❌ Performance lenta (> 5s)${NC}"
fi

echo ""
echo -e "${PURPLE}7. Status Final${NC}"
echo "----------------------------------------"

# Resumo
echo -e "${BLUE}Resumo da Configuração:${NC}"
echo "• Ollama URL: $OLLAMA_URL"
echo "• Modelo: $MODEL"
echo "• App URL: $APP_URL"

# Status detalhado
echo ""
echo -e "${BLUE}Status Detalhado:${NC}"
curl -s "$APP_URL/status" | jq '{
    status: .status,
    llm: .components.llm_service.status,
    ollama_url: .components.llm_service.ollama_url,
    model: .components.llm_service.model,
    sessions: .components.session_manager.active_sessions
}' 2>/dev/null || echo "Não foi possível obter status"

echo ""
echo -e "${PURPLE}========================================${NC}"
echo -e "${GREEN}✅ Teste de integração concluído!${NC}"
echo -e "${PURPLE}========================================${NC}"

# Dicas finais
echo ""
echo -e "${YELLOW}📝 Próximos passos:${NC}"
echo "1. Configure o webhook no Twilio Dashboard"
echo "2. Use ngrok para expor o webhook: ngrok http 8000"
echo "3. Teste enviando mensagens reais via WhatsApp"
echo "4. Monitore logs: docker-compose logs -f"