# 🤖 Jarvis WhatsApp Agent Orchestrator

Sistema avançado de orquestração de agentes IA para WhatsApp usando Twilio, com 4 agentes especializados trabalhando em conjunto.

## 🚀 Funcionalidades

- **Orquestração Inteligente**: 4 agentes especializados trabalhando em harmonia
- **Integração WhatsApp**: Via Twilio para máxima confiabilidade  
- **Sessões Persistentes**: Gerenciamento de contexto com Redis
- **IA Avançada**: Classificação inteligente de intenções
- **Escalabilidade**: Arquitetura preparada para produção
- **Monitoramento**: Logs estruturados e health checks

## 🤖 Agentes Disponíveis

1. **Reception Agent**: Recepção e triagem inicial de usuários
2. **Classification Agent**: IA para classificação inteligente de intenções  
3. **Data Agent**: Especialista em consultas e relatórios de dados
4. **Support Agent**: Suporte técnico especializado

## ⚙️ Configuração Rápida

### 1. Clone e Configure

```bash
git clone <repository>
cd whatsapp_agent_orchestrator
cp .env.example .env
```

### 2. Configure suas credenciais no .env

```env
TWILIO_ACCOUNT_SID=AC1c9d31b427c19abdf4f607c9aa74d144
TWILIO_AUTH_TOKEN=a8ed455b4153b003caa10a584ec7b330
TWILIO_PHONE_NUMBER=+14155238886
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io
```

### 3. Rode com Docker

```bash
docker-compose up -d
```

### 4. Configure Webhook no Twilio

- Vá para o Console Twilio > WhatsApp Sandbox
- Configure Webhook URL: `https://your-ngrok-url.ngrok.io/webhook/whatsapp`
- Method: POST

## 🛠️ Instalação Manual

```bash
# Instalar dependências
pip install -r requirements.txt

# Instalar Redis
# Ubuntu/Debian: apt-get install redis-server
# macOS: brew install redis

# Rodar aplicação
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 Endpoints da API

- `GET /` - Página inicial com documentação
- `POST /webhook/whatsapp` - Webhook do Twilio
- `GET /health` - Health check
- `GET /status` - Status detalhado do sistema
- `POST /send` - Enviar mensagem manual
- `POST /reset-session` - Resetar sessão de usuário
- `POST /broadcast` - Broadcast para múltiplos usuários

## 🧪 Testando o Sistema

### Via WhatsApp
Envie mensagens para seu número Twilio:

- "Olá" → Ativa o Reception Agent
- "Relatório de vendas" → Redireciona para Data Agent
- "Problema no sistema" → Redireciona para Support Agent
- "Agendar reunião" → Ativa Classification Agent

### Via API
```bash
# Enviar mensagem manual
curl -X POST "http://localhost:8000/send" \\
  -H "Content-Type: application/json" \\
  -d '{"phone_number": "+5511999999999", "message": "Teste do sistema"}'

# Verificar status
curl http://localhost:8000/status
```

## 🔧 Personalização de Agentes

### Adicionando Novo Agente

1. Crie classe herdando de `BaseAgent`:

```python
from app.agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="my_agent",
            name="Meu Agente Custom",
            description="Descrição do agente"
        )
    
    async def can_handle(self, message, session):
        # Lógica para determinar se pode processar
        return True
    
    async def process_message(self, message, session):
        # Lógica de processamento
        return AgentResponse(...)
```

2. Registre no orquestrador em `app/core/orchestrator.py`

### Conectando com seus Sistemas

Modifique os agentes para integrar com:
- Seu banco de dados
- APIs internas
- Sistemas ERP/CRM
- Serviços de ML/IA externos

## 📊 Monitoramento e Logs

### Logs Estruturados
- Console: Logs coloridos em tempo real
- Arquivo: Rotação diária em `logs/`
- Formato: JSON estruturado

### Métricas Disponíveis
- Sessões ativas
- Status dos agentes
- Performance de resposta
- Taxa de erro

## 🚀 Deploy em Produção

### Docker Swarm
```yaml
version: '3.8'
services:
  jarvis-whatsapp:
    image: jarvis-whatsapp:latest
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jarvis-whatsapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: jarvis-whatsapp
  template:
    spec:
      containers:
      - name: jarvis-whatsapp
        image: jarvis-whatsapp:latest
        ports:
        - containerPort: 8000
```

## 🔒 Segurança

- Validação de webhooks Twilio
- Rate limiting (recomendado nginx/traefik)
- Sanitização de inputs
- Logs sem informações sensíveis

## 🤝 Contribuindo

1. Fork o projeto
2. Crie branch para feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para branch (`git push origin feature/nova-funcionalidade`)
5. Abra Pull Request

## 📄 Licença

Este projeto está sob licença MIT. Veja `LICENSE` para mais detalhes.

## 🆘 Suporte

- 📧 Email: suporte@empresa.com
- 📱 WhatsApp: +55 11 99999-9999
- 💬 Discord: [link-discord]
- 📖 Docs: [link-documentacao]

---

**Desenvolvido com ❤️ para revolucionar atendimento via WhatsApp** 
