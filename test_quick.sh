#!/bin/bash

echo "🧪 Teste Rápido do Sistema"
echo "========================="

# Função para enviar e mostrar resposta
test_msg() {
    local phone=$1
    local msg=$2
    echo -e "\n👤 Você: $msg"
    
    response=$(curl -s -X POST "http://localhost:8000/webhook/whatsapp" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "From=whatsapp:$phone" \
        -d "Body=$msg" \
        -d "MessageSid=test_$(date +%s)")
    
    message=$(echo "$response" | grep -oP '(?<=<Message>).*?(?=</Message>)')
    echo -e "🤖 Alex: $message"
}

# Testa o fluxo completo
phone="+5511999991234"
echo "=== Testando Fluxo Completo ==="

test_msg "$phone" "oi"
sleep 2

test_msg "$phone" "felipe"  
sleep 2

test_msg "$phone" "tech solutions"
sleep 2

test_msg "$phone" "quero ver as vendas"

echo -e "\n\n✅ Se o Alex:"
echo "1. Pediu seu nome após 'oi'"
echo "2. Agradeceu e pediu empresa após 'felipe'"
echo "3. Ofereceu serviços após 'tech solutions'"
echo "4. Respondeu sobre vendas no final"
echo ""
echo "ENTÃO ESTÁ FUNCIONANDO! 🎉"