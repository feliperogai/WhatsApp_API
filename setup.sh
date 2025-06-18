echo "🚀 Configurando Jarvis WhatsApp Agent Orchestrator"
echo "=================================================="

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verifica se Docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado. Instale o Docker primeiro.${NC}"
    exit 1
fi

# Verifica se Docker Compose está instalado
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado. Instale o Docker Compose primeiro.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker e Docker Compose encontrados${NC}"

# Cria arquivo .env se não existir
if [ ! -f .env ]; then
    echo -e "${YELLOW}📄 Criando arquivo .env...${NC}"
    cp .env.example .env
    
    echo -e "${BLUE}🔧 Configure suas credenciais no arquivo .env:${NC}"
    echo "  - TWILIO_ACCOUNT_SID"
    echo "  - TWILIO_AUTH_TOKEN" 
    echo "  - TWILIO_PHONE_NUMBER"
    echo "  - WEBHOOK_BASE_URL"
    echo ""
    read -p "Pressione Enter para continuar após configurar o .env..."
fi

# Cria diretórios necessários
echo -e "${YELLOW}📁 Criando diretórios...${NC}"
mkdir -p logs
mkdir -p data

# Build da aplicação
echo -e "${YELLOW}🔨 Construindo aplicação Docker...${NC}"
docker-compose build

# Inicia serviços
echo -e "${YELLOW}🚀 Iniciando serviços...${NC}"
docker-compose up -d

# Aguarda serviços iniciarem
echo -e "${YELLOW}⏳ Aguardando serviços iniciarem...${NC}"
sleep 10

# Verifica se serviços estão rodando
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Serviços iniciados com sucesso!${NC}"
    
    echo ""
    echo -e "${BLUE}🌐 Acesse a aplicação:${NC}"
    echo "  http://localhost:8000"
    echo ""
    echo -e "${BLUE}📊 Status dos serviços:${NC}"
    echo "  http://localhost:8000/status"
    echo ""
    echo -e "${BLUE}🔗 Logs em tempo real:${NC}"
    echo "  docker-compose logs -f"
    echo ""
    echo -e "${YELLOW}⚠️  Não esqueça de configurar o webhook no Twilio!${NC}"
    
else
    echo -e "${RED}❌ Erro ao iniciar serviços. Verifique os logs:${NC}"
    echo "docker-compose logs"
fi