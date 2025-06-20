#!/bin/bash

echo "🔍 Diagnóstico - Jarvis LLM Integration"
echo "======================================="

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configurações
OLLAMA_URL="http://192.168.15.31:11435"
APP_URL="http://localhost:8000"

echo -e "${PURPLE}1. Verificando Conectividade${NC}"
echo "----------------------------------------"

# Teste de rede para Ollama
echo -n -e "${BLUE}Ping para Ollama host (192.168.15.31)...${NC} "
if ping -c 1 192.168.15.31 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ FALHOU - Host inacessível${NC}"
    echo -e "${YELLOW}Verifique:${NC}"
    echo "  - O servidor Ollama está ligado?"
    echo "  - O IP está correto?"
    echo "  - Firewall está bloqueando?"
fi

# Teste de porta Ollama
echo -n -e "${BLUE}Testando porta Ollama (11435)...${NC} "
if nc -zv 192.168.15.31 11435 2>&1 | grep -q succeeded; then
    echo -e "${GREEN}✅ Porta aberta${NC}"
else
    echo -e "${RED}❌ Porta fechada${NC}"
    echo -e "${YELLOW}Verifique:${NC}"
    echo "  - Ollama está rodando? (ollama serve)"
    echo "  - Porta correta? (padrão: 11434)"
fi

echo ""
echo -e "${PURPLE}2. Verificando Ollama${NC}"
echo "----------------------------------------"

# Teste API Ollama
echo -n -e "${BLUE}API Ollama /api/tags...${NC} "
if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
    
    # Lista modelos
    echo -e "${BLUE}Modelos disponíveis:${NC}"
    curl -s "$OLLAMA_URL/api/tags" | jq -r '.models[].name' 2>/dev/null | sed 's/^/  - /'
else
    echo -e "${RED}❌ FALHOU${NC}"
fi

# Teste modelo específico
echo -n -e "${BLUE}Testando modelo llama3.1:8b...${NC} "
MODEL_EXISTS=$(curl -s "$OLLAMA_URL/api/tags" | jq -r '.models[].name' | grep -c "llama3.1:8b")
if [ "$MODEL_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}✅ Modelo disponível${NC}"
else
    echo -e "${RED}❌ Modelo não encontrado${NC}"
    echo -e "${YELLOW}Execute: ollama pull llama3.1:8b${NC}"
fi

echo ""
echo -e "${PURPLE}3. Verificando Docker${NC}"
echo "----------------------------------------"

# Containers rodando
echo -e "${BLUE}Containers:${NC}"
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" | tail -n +2 | while read line; do
    if [[ "$line" == *"Up"* ]]; then
        echo -e "  ${GREEN}$line${NC}"
    else
        echo -e "  ${RED}$line${NC}"
    fi
done

# Logs recentes de erro
echo ""
echo -e "${BLUE}Erros recentes (últimas 10 linhas):${NC}"
docker-compose logs jarvis-whatsapp-llm 2>&1 | grep -i "error\|exception" | tail -10 | sed 's/^/  /'

echo ""
echo -e "${PURPLE}4. Verificando Aplicação${NC}"
echo "----------------------------------------"

# Health check
echo -n -e "${BLUE}Health check...${NC} "
HEALTH=$(curl -s "$APP_URL/health" | jq -r '.status' 2>/dev/null)
if [[ "$HEALTH" == "healthy" ]]; then
    echo -e "${GREEN}✅ Healthy${NC}"
else
    echo -e "${RED}❌ Unhealthy${NC}"
fi

# LLM Status detalhado
echo -e "${BLUE}LLM Service status:${NC}"
curl -s "$APP_URL/llm/status" 2>/dev/null | jq '{
    status: .status,
    ollama_url: .ollama_url,
    model: .model,
    initialized: .initialized,
    model_available: .model_available
}' 2>/dev/null || echo "  Não disponível"

echo ""
echo -e "${PURPLE}5. Teste de Integração Rápido${NC}"
echo "----------------------------------------"

# Teste webhook
echo -e "${BLUE}Testando webhook com 'Olá'...${NC}"
RESPONSE=$(curl -s -X POST "$APP_URL/webhook/whatsapp" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+5511999999999&To=whatsapp:+14155238886&Body=Olá&MessageSid=SMtest123" \
  2>&1)

if [[ "$RESPONSE" == *"<Response>"* ]] && [[ "$RESPONSE" == *"<Message>"* ]]; then
    echo -e "${GREEN}✅ Webhook respondeu${NC}"
    echo "$RESPONSE" | grep -o '<Message>.*</Message>' | sed 's/<[^>]*>//g' | sed 's/^/  Resposta: /'
else
    echo -e "${RED}❌ Webhook não respondeu corretamente${NC}"
    echo -e "${YELLOW}Resposta recebida:${NC}"
    echo "$RESPONSE" | head -5 | sed 's/^/  /'
fi

echo ""
echo -e "${PURPLE}6. Diagnóstico de Variáveis de Ambiente${NC}"
echo "----------------------------------------"

echo -e "${BLUE}Verificando .env...${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✅ Arquivo .env existe${NC}"
    
    # Verifica variáveis importantes
    for var in "OLLAMA_BASE_URL" "OLLAMA_MODEL" "TWILIO_ACCOUNT_SID"; do
        if grep -q "^$var=" .env; then
            VALUE=$(grep "^$var=" .env | cut -d'=' -f2)
            echo -e "  $var: ${GREEN}definido${NC} (${VALUE:0:20}...)"
        else
            echo -e "  $var: ${RED}não definido${NC}"
        fi
    done
else
    echo -e "${RED}❌ Arquivo .env não encontrado${NC}"
fi

echo ""
echo -e "${PURPLE}7. Recomendações${NC}"
echo "----------------------------------------"

# Analisa problemas e sugere soluções
PROBLEMS=0

# Verifica Ollama
if ! curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo -e "${RED}⚠️ Problema: Ollama não acessível${NC}"
    echo "  Solução: Verifique se Ollama está rodando em $OLLAMA_URL"
    echo "  Execute: ollama serve"
    PROBLEMS=$((PROBLEMS + 1))
fi

# Verifica aplicação
if [[ "$HEALTH" != "healthy" ]]; then
    echo -e "${RED}⚠️ Problema: Aplicação não está saudável${NC}"
    echo "  Solução: Reinicie os containers"
    echo "  Execute: docker-compose restart"
    PROBLEMS=$((PROBLEMS + 1))
fi

# Verifica integração
LLM_STATUS=$(curl -s "$APP_URL/llm/status" | jq -r '.status' 2>/dev/null)
if [[ "$LLM_STATUS" != "online" ]]; then
    echo -e "${RED}⚠️ Problema: LLM não está online${NC}"
    echo "  Solução: Verifique logs para erros"
    echo "  Execute: docker-compose logs jarvis-whatsapp-llm"
    PROBLEMS=$((PROBLEMS + 1))
fi

if [ $PROBLEMS -eq 0 ]; then
    echo -e "${GREEN}✅ Nenhum problema detectado!${NC}"
    echo "  Sistema parece estar funcionando corretamente."
else
    echo ""
    echo -e "${YELLOW}Total de problemas encontrados: $PROBLEMS${NC}"
fi

echo ""
echo -e "${PURPLE}8. Comandos Úteis${NC}"
echo "----------------------------------------"
echo "• Ver logs em tempo real: docker-compose logs -f jarvis-whatsapp-llm"
echo "• Reiniciar aplicação: docker-compose restart jarvis-whatsapp-llm"
echo "• Testar Ollama direto: curl $OLLAMA_URL/api/chat -d '{...}'"
echo "• Resetar tudo: docker-compose down && docker-compose up -d"
echo "• Monitorar: ./monitor_llm.sh"

echo ""
echo -e "${BLUE}Diagnóstico concluído!${NC}"