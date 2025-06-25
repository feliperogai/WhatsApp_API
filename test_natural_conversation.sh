echo "🧪 Testando Conversas Naturais do Jarvis"
echo "========================================"

# URL base
BASE_URL="http://localhost:8000"

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Função para enviar mensagem
send_message() {
    local from=$1
    local body=$2
    echo -e "\n${BLUE}📱 Enviando:${NC} $body"
    
    response=$(curl -s -X POST "$BASE_URL/webhook/whatsapp" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "From=whatsapp:$from" \
        -d "Body=$body" \
        -d "MessageSid=test_$(date +%s)")
    
    # Extrai apenas o conteúdo da mensagem
    message=$(echo "$response" | grep -oP '(?<=<Message>).*?(?=</Message>)')
    echo -e "${GREEN}🤖 Jarvis:${NC} $message"
}

# Função para testar conversa completa
test_conversation() {
    local phone=$1
    shift
    local messages=("$@")
    
    echo -e "\n${YELLOW}=== Nova Conversa ===${NC}"
    for msg in "${messages[@]}"; do
        send_message "$phone" "$msg"
        sleep 2
    done
}

echo -e "\n${YELLOW}1. Testando Saudações Variadas${NC}"
phones=("+5511999990001" "+5511999990002" "+5511999990003")
greetings=("oi" "olá" "opa")

for i in {0..2}; do
    send_message "${phones[$i]}" "${greetings[$i]}"
    sleep 1
done

echo -e "\n${YELLOW}2. Testando Conversa Natural Completa${NC}"
test_conversation "+5511999990004" \
    "oi" \
    "to bem e vc?" \
    "queria saber oq vc faz" \
    "legal! as vendas tão boas?"

echo -e "\n${YELLOW}3. Testando Problemas Técnicos${NC}"
test_conversation "+5511999990005" \
    "opa" \
    "o sistema ta uma merda hoje" \
    "ta tudo lento" \
    "desde manhã"

echo -e "\n${YELLOW}4. Testando Pedido de Menu (Deve ser Natural)${NC}"
send_message "+5511999990006" "menu"
sleep 2
send_message "+5511999990006" "quais seus serviços?"

echo -e "\n${YELLOW}5. Testando Despedidas${NC}"
test_conversation "+5511999990007" \
    "oi" \
    "obrigado pela ajuda" \
    "tchau"

echo -e "\n${YELLOW}6. Testando Resiliência a Erros${NC}"
# Força timeout (mensagem muito complexa)
complex_msg="Preciso de um relatório super detalhado com todos os dados de vendas, clientes, performance, KPIs, comparativos mensais, anuais, projeções, análise de tendências, segmentação por região, produto, vendedor, canal, além de insights e recomendações estratégicas para os próximos 12 meses considerando sazonalidade e fatores macroeconômicos"
send_message "+5511999990008" "$complex_msg"

echo -e "\n\n${YELLOW}=== Teste de Consistência ===${NC}"
echo "Enviando mesma mensagem 3x para verificar variação nas respostas:"

for i in {1..3}; do
    echo -e "\n${BLUE}Tentativa $i:${NC}"
    send_message "+5511999990009" "oi, tudo bem?"
    sleep 2
done

echo -e "\n\n${GREEN}✅ Testes Concluídos!${NC}"
echo "========================================"
echo -e "${YELLOW}Checklist de Validação:${NC}"
echo "[ ] As saudações foram variadas?"
echo "[ ] As conversas fluíram naturalmente?"
echo "[ ] O 'menu' não mostrou lista robótica?"
echo "[ ] Os erros foram tratados de forma humana?"
echo "[ ] As respostas variaram mesmo com entradas iguais?"
echo ""
echo "Se algum item falhou, verifique se as mudanças foram aplicadas corretamente!"