echo "🔍 Diagnóstico Completo - Jarvis WhatsApp"
echo "========================================"

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Função para checar arquivo
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅ $1 exists${NC}"
        return 0
    else
        echo -e "${RED}❌ $1 missing${NC}"
        return 1
    fi
}

# Função para checar comando
check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ $1 installed${NC}"
        return 0
    else
        echo -e "${RED}❌ $1 not installed${NC}"
        return 1
    fi
}

echo -e "${BLUE}1. Checking Project Structure${NC}"
echo "----------------------------------------"

# Detecta diretório
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi

cd "$PROJECT_ROOT"
echo "Working directory: $PROJECT_ROOT"

# Checa arquivos essenciais
check_file ".env.example"
check_file ".env"
check_file "requirements.txt"
check_file "Dockerfile"
check_file "docker-compose.yml"
check_file "app/main.py"

echo ""
echo -e "${BLUE}2. Checking Dependencies${NC}"
echo "----------------------------------------"

check_command "docker"
check_command "docker-compose"
check_command "python3"
check_command "pip3"
check_command "curl"

echo ""
echo -e "${BLUE}3. Checking Environment Variables${NC}"
echo "----------------------------------------"

if [ -f .env ]; then
    # Checa variáveis críticas
    for var in "TWILIO_ACCOUNT_SID" "TWILIO_AUTH_TOKEN" "TWILIO_PHONE_NUMBER" "OLLAMA_URLS" "REDIS_URL"; do
        if grep -q "^$var=" .env; then
            VALUE=$(grep "^$var=" .env | cut -d'=' -f2)
            if [[ "$VALUE" == *"your_"* ]] || [ -z "$VALUE" ]; then
                echo -e "${YELLOW}⚠️  $var needs configuration${NC}"
            else
                echo -e "${GREEN}✅ $var configured${NC}"
            fi
        else
            echo -e "${RED}❌ $var not found in .env${NC}"
        fi
    done
else
    echo -e "${RED}❌ .env file not found!${NC}"
fi

echo ""
echo -e "${BLUE}4. Checking Python Imports${NC}"
echo "----------------------------------------"

# Testa imports principais
python3 -c "
import sys
sys.path.append('.')
errors = []

try:
    import fastapi
    print('✅ fastapi')
except ImportError:
    print('❌ fastapi')
    errors.append('fastapi')

try:
    import redis
    print('✅ redis')
except ImportError:
    print('❌ redis')
    errors.append('redis')

try:
    import aiohttp
    print('✅ aiohttp')
except ImportError:
    print('❌ aiohttp')
    errors.append('aiohttp')

try:
    import twilio
    print('✅ twilio')
except ImportError:
    print('❌ twilio')
    errors.append('twilio')

try:
    import langchain
    print('✅ langchain')
except ImportError:
    print('❌ langchain')
    errors.append('langchain')

if errors:
    print(f'\n⚠️  Missing packages: {errors}')
    print('Run: pip3 install -r requirements.txt')
"

echo ""
echo -e "${BLUE}5. Checking Code Issues${NC}"
echo "----------------------------------------"

# Checa imports problemáticos
echo "Checking for import errors..."

# main.py check
if grep -q "from app.services.llm_service import OptimizedLLMService" app/main.py 2>/dev/null; then
    echo -e "${RED}❌ Import error in main.py: OptimizedLLMService should be from app.core.llm_pool${NC}"
else
    echo -e "${GREEN}✅ main.py imports look correct${NC}"
fi

# Check class definitions match imports
if [ -f "app/services/llm_service.py" ]; then
    if grep -q "class LLMService" app/services/llm_service.py; then
        echo -e "${GREEN}✅ LLMService class found${NC}"
    else
        echo -e "${RED}❌ LLMService class not found${NC}"
    fi
fi

echo ""
echo -e "${BLUE}6. Checking Docker${NC}"
echo "----------------------------------------"

# Docker daemon running?
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker daemon running${NC}"
else
    echo -e "${RED}❌ Docker daemon not running${NC}"
fi

# Containers status
if docker-compose ps 2>/dev/null | grep -q "Up"; then
    echo -e "${GREEN}✅ Some containers are running${NC}"
    docker-compose ps
else
    echo -e "${YELLOW}⚠️  No containers running${NC}"
fi

echo ""
echo -e "${BLUE}7. Checking Ollama${NC}"
echo "----------------------------------------"

if [ -f .env ]; then
    OLLAMA_URL=$(grep OLLAMA_URLS .env | cut -d'=' -f2 | cut -d',' -f1 | tr -d ' ')
    if [ -z "$OLLAMA_URL" ]; then
        OLLAMA_URL="http://localhost:11434"
    fi
    
    echo "Ollama URL: $OLLAMA_URL"
    
    if curl -s "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama accessible${NC}"
        
        # Check models
        MODELS=$(curl -s "$OLLAMA_URL/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$MODELS" ]; then
            echo "Available models:"
            echo "$MODELS" | sed 's/^/  - /'
        fi
    else
        echo -e "${RED}❌ Ollama not accessible${NC}"
        echo "  Make sure Ollama is running: ollama serve"
    fi
fi

echo ""
echo -e "${BLUE}8. Summary & Recommendations${NC}"
echo "----------------------------------------"

ISSUES=0

# Count issues
[ ! -f .env ] && ISSUES=$((ISSUES + 1))
[ ! -f requirements.txt ] && ISSUES=$((ISSUES + 1))
grep -q "OptimizedLLMService" app/main.py 2>/dev/null && ISSUES=$((ISSUES + 1))
! docker info >/dev/null 2>&1 && ISSUES=$((ISSUES + 1))

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ No critical issues found!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run: ./scripts/setup_fixed.sh"
    echo "2. Configure .env if needed"
    echo "3. Start services: docker-compose up -d"
else
    echo -e "${RED}❌ Found $ISSUES critical issues${NC}"
    echo ""
    echo "Fix these issues:"
    [ ! -f .env ] && echo "1. Create .env from .env.example"
    [ ! -f requirements.txt ] && echo "2. Create requirements.txt"
    grep -q "OptimizedLLMService" app/main.py 2>/dev/null && echo "3. Fix import in main.py"
    ! docker info >/dev/null 2>&1 && echo "4. Start Docker daemon"
fi

echo ""
echo "═══════════════════════════════════════"
echo "Diagnostic complete!"
echo "═══════════════════════════════════════"