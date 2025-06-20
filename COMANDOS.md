# 🚀 Comandos Rápidos - Jarvis LLM v2.0

**Sistema otimizado para seu Ollama em: http://192.168.15.31:11435**

## ⚡ Setup Rápido (3 comandos)

```bash
# 1. Otimizar projeto
chmod +x optimize_project.sh && ./optimize_project.sh

# 2. Setup automático
chmod +x setup_llm.sh && ./setup_llm.sh

# 3. Testar sistema
./test_llm.sh
```

## 🎯 Comandos Principais

### Setup e Inicialização
```bash
./setup_llm.sh              # Setup otimizado para seu Ollama
docker-compose up -d         # Iniciar serviços
docker-compose down          # Parar serviços
docker-compose restart       # Reiniciar serviços
```

### Testes
```bash
./test_llm.sh                        # Teste completo
./test_llm.sh +5511999999999         # Teste com envio para número
curl http://localhost:8000/health    # Health check rápido
```

### Monitoramento
```bash
./monitor_llm.sh             # Monitor em tempo real
./monitor_llm.sh once        # Ver status uma vez
./monitor_llm.sh test        # Teste rápido de conectividade
docker-compose logs -f       # Logs em tempo real
```

## 🧠 Testes LLM Diretos

### Via API
```bash
# Teste básico
curl -X POST http://localhost:8000/llm/test \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Olá, como você está?"}'

# Status LLM
curl http://localhost:8000/llm/status

# Status geral
curl http://localhost:8000/status
```

### Via Ollama Direto (seu comando)
```bash
curl -s http://192.168.15.31:11435/api/chat -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      { "role": "user", "content": "Qual é a capital do Brasil..." }
    ]
  }' | jq -r '.message.content' | tr -d '\n'
```

## 📱 WhatsApp

### Configuração Webhook Twilio
```
URL: https://seu-ngrok-url.ngrok.io/webhook/whatsapp
Method: POST
```

### Mensagens de Teste
- "Olá" → Ativa Reception Agent
- "Preciso de relatório de vendas" → Data Agent
- "Sistema com erro" → Support Agent
- "Agendar reunião" → Classification Agent

### API de Envio
```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+5511999999999",
    "message": "Teste do Jarvis LLM!"
  }'
```

## 🐳 Docker

### Comandos Úteis
```bash
# Ver containers
docker-compose ps

# Logs específicos
docker-compose logs jarvis-whatsapp-llm
docker-compose logs redis

# Rebuild
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Limpar tudo
docker-compose down -v
docker system prune -f
```

### Resolver Problemas
```bash
# Se der erro de permissão
sudo chmod +x *.sh

# Se Ollama não conectar
curl -s http://192.168.15.31:11435/api/tags

# Se container não iniciar
docker-compose logs jarvis-whatsapp-llm

# Resetar tudo
docker-compose down -v
./setup_llm.sh
```

## 🔧 Configurações

### Arquivo .env Principal
```bash
# Ollama (seu setup)
OLLAMA_BASE_URL=http://192.168.15.31:11435
OLLAMA_MODEL=llama3.1:8b

# Twilio
TWILIO_ACCOUNT_SID=seu_sid
TWILIO_AUTH_TOKEN=seu_token
TWILIO_PHONE_NUMBER=+14155238886

# Webhook
WEBHOOK_BASE_URL=https://sua-url.ngrok.io
```

### Ajustar Performance
```bash
# Para respostas mais rápidas
LLM_MAX_TOKENS=300
LLM_TEMPERATURE=0.3

# Para respostas mais criativas
LLM_MAX_TOKENS=800
LLM_TEMPERATURE=0.8
```

## 📊 URLs Importantes

```
http://localhost:8000          # Dashboard principal
http://localhost:8000/health   # Health check
http://localhost:8000/status   # Status detalhado
http://localhost:8000/llm/status # Status LLM específico
```

## 🆘 Resolução de Problemas

### Problema: Ollama não conecta
```bash
# Testar Ollama
curl http://192.168.15.31:11435/api/tags

# Se não responder, verificar:
# 1. Ollama está rodando?
# 2. Firewall bloqueando?
# 3. IP/porta corretos?
```

### Problema: Container não inicia
```bash
# Ver logs detalhados
docker-compose logs jarvis-whatsapp-llm

# Comum: erro de dependências
docker-compose build --no-cache
```

### Problema: LLM não responde
```bash
# Testar direto
./test_llm.sh

# Verificar memória/CPU
docker stats

# Reiniciar LLM service
docker-compose restart jarvis-whatsapp-llm
```

## ⚡ Atalhos Rápidos

```bash
# Status rápido
alias js='./monitor_llm.sh once'

# Teste rápido
alias jt='./test_llm.sh'

# Logs rápidos
alias jl='docker-compose logs -f jarvis-whatsapp-llm'

# Restart rápido
alias jr='docker-compose restart jarvis-whatsapp-llm'
```

---

**🤖 Jarvis LLM v2.0 - Otimizado para seu Ollama!**