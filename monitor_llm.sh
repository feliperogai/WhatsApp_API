#!/bin/bash

echo "📊 Monitor Jarvis LLM v2.0"
echo "=========================="

BASE_URL="http://localhost:8000"
OLLAMA_URL="http://192.168.15.31:11435"
REFRESH_INTERVAL=5

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Função para status colorido
get_status() {
    local url="$1"
    if curl -s "$url" >/dev/null 2>&1; then
        echo -e "${GREEN}ONLINE${NC}"
    else
        echo -e "${RED}OFFLINE${NC}"
    fi
}

# Função principal
show_status() {
    clear
    
    echo -e "${PURPLE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║             🤖 JARVIS LLM MONITOR v2.0                    ║${NC}"
    echo -e "${PURPLE}║                $(date '+%Y-%m-%d %H:%M:%S')                        ║${NC}"
    echo -e "${PURPLE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Status dos Serviços
    echo -e "${CYAN}🔍 STATUS DOS SERVIÇOS${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    printf "%-20s: %s\n" "Aplicação Principal" "$(get_status "$BASE_URL/health")"
    printf "%-20s: %s\n" "LLM Service" "$(get_status "$BASE_URL/llm/status")"
    printf "%-20s: %s\n" "Ollama Externo" "$(get_status "$OLLAMA_URL/api/tags")"
    
    echo ""
    
    # Teste LLM em Tempo Real
    echo -e "${BLUE}🧠 TESTE LLM EM TEMPO REAL${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    # Teste direto do Ollama
    echo -n "Ollama Direto: "
    ollama_test=$(curl -s "$OLLAMA_URL/api/chat" -X POST \
        -H "Content-Type: application/json" \
        -d '{"model": "llama3.1:8b", "messages": [{"role": "user", "content": "Diga apenas a hora atual"}]}' \
        | jq -r '.message.content' 2>/dev/null | head -1)
    
    if [ -n "$ollama_test" ]; then
        echo -e "${GREEN}✅ '$ollama_test'${NC}"
    else
        echo -e "${RED}❌ Não respondeu${NC}"
    fi
    
    # Teste via aplicação
    echo -n "Via Aplicação: "
    app_test=$(curl -s -X POST "$BASE_URL/llm/test" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Responda apenas com um emoji"}' \
        | jq -r '.response' 2>/dev/null | head -1)
    
    if [ -n "$app_test" ]; then
        echo -e "${GREEN}✅ '$app_test'${NC}"
    else
        echo -e "${RED}❌ Não respondeu${NC}"
    fi
    
    echo ""
    
    # Métricas
    echo -e "${YELLOW}📊 MÉTRICAS${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    if command -v jq >/dev/null 2>&1; then
        metrics=$(curl -s "$BASE_URL/status" 2>/dev/null)
        
        if [ -n "$metrics" ]; then
            uptime=$(echo "$metrics" | jq -r '.uptime_human // "N/A"' 2>/dev/null)
            sessions=$(echo "$metrics" | jq -r '.system.active_sessions // 0' 2>/dev/null)
            
            printf "%-20s: %s\n" "Uptime" "$uptime"
            printf "%-20s: %s\n" "Sessões Ativas" "$sessions"
        else
            echo "Métricas indisponíveis"
        fi
    else
        echo "jq não disponível para métricas"
    fi
    
    echo ""
    
    # Containers
    echo -e "${PURPLE}🐳 CONTAINERS${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose ps --format "table" 2>/dev/null | tail -n +2 | while read -r line; do
            if [[ "$line" == *"Up"* ]]; then
                echo -e "  ${GREEN}$line${NC}"
            elif [[ "$line" == *"Exit"* ]]; then
                echo -e "  ${RED}$line${NC}"
            else
                echo -e "  ${YELLOW}$line${NC}"
            fi
        done
    else
        echo "Docker Compose não disponível"
    fi
    
    echo ""
    
    # Logs Recentes
    echo -e "${CYAN}📝 LOGS RECENTES${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose logs --tail=3 jarvis-whatsapp-llm 2>/dev/null | sed 's/^/  /' | tail -3
    else
        echo "Logs não disponíveis"
    fi
    
    echo ""
    echo -e "${PURPLE}────────────────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}Ctrl+C para sair | Atualização: ${REFRESH_INTERVAL}s | Ollama: $OLLAMA_URL${NC}"
}

# Função de teste único
test_once() {
    show_status
    exit 0
}

# Main
case "${1:-monitor}" in
    "once"|"single")
        test_once
        ;;
    "test")
        echo "🧪 Teste rápido..."
        echo "Aplicação: $(get_status "$BASE_URL/health")"
        echo "LLM: $(get_status "$BASE_URL/llm/status")"
        echo "Ollama: $(get_status "$OLLAMA_URL/api/tags")"
        exit 0
        ;;
    "monitor"|"")
        trap 'echo -e "\n${YELLOW}Monitor interrompido${NC}"; exit 0' INT
        
        while true; do
            show_status
            sleep $REFRESH_INTERVAL
        done
        ;;
    *)
        echo "Uso: $0 [monitor|once|test]"
        exit 1
        ;;
esac