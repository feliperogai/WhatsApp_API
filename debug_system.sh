#!/bin/bash

echo "🔍 Debug do Sistema"
echo "=================="

# 1. Verifica se o arquivo existe no container
echo "1. Verificando arquivo no container..."
docker exec jarvis-whatsapp-llm ls -la /app/app/agents/llm_proactive_reception_agent.py

# 2. Verifica conteúdo do arquivo
echo -e "\n2. Primeiras linhas do arquivo:"
docker exec jarvis-whatsapp-llm head -20 /app/app/agents/llm_proactive_reception_agent.py

# 3. Verifica import no orchestrator
echo -e "\n3. Import no orchestrator:"
docker exec jarvis-whatsapp-llm grep -n "reception_agent" /app/app/core/langgraph_orchestrator.py | head -5

# 4. Verifica logs de erro
echo -e "\n4. Últimos erros no log:"
docker logs jarvis-whatsapp-llm 2>&1 | grep -i "error\|exception" | tail -10

# 5. Status do serviço
echo -e "\n5. Status do serviço:"
curl -s http://localhost:8000/health | grep -o '"status":"[^"]*"'

echo -e "\n\n🔧 Se houver problemas, execute:"
echo "./fix_it_now.sh"