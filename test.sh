echo "🧪 Testando Jarvis WhatsApp Agent Orchestrator"
echo "=============================================="

BASE_URL="http://localhost:8000"

# Testa health check
echo "1. Testando health check..."
curl -s "$BASE_URL/health" | jq . || echo "❌ Health check falhou"

echo ""

# Testa status detalhado  
echo "2. Testando status detalhado..."
curl -s "$BASE_URL/status" | jq . || echo "❌ Status check falhou"

echo ""

# Testa envio de mensagem (se número fornecido)
if [ ! -z "$1" ]; then
    echo "3. Testando envio de mensagem para $1..."
    curl -X POST "$BASE_URL/send" \
        -H "Content-Type: application/json" \
        -d "{\"phone_number\": \"$1\", \"message\": \"Teste do sistema Jarvis 🤖\"}" \
        | jq . || echo "❌ Envio falhou"
else
    echo "3. Para testar envio de mensagem: ./test.sh +5511999999999"
fi

echo ""
echo "✅ Testes concluídos"