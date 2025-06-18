echo "📦 Instalando dependências do Jarvis WhatsApp Agent Orchestrator"
echo "================================================================"

# Deteta sistema operacional
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Sistema Linux detectado"
    
    # Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        echo "📥 Instalando Docker via apt..."
        sudo apt-get update
        sudo apt-get install -y docker.io docker-compose
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker $USER
        
    # CentOS/RHEL
    elif command -v yum &> /dev/null; then
        echo "📥 Instalando Docker via yum..."
        sudo yum install -y docker docker-compose
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker $USER
    fi
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 Sistema macOS detectado"
    
    if command -v brew &> /dev/null; then
        echo "📥 Instalando Docker via Homebrew..."
        brew install --cask docker
        brew install docker-compose
    else
        echo "❌ Homebrew não encontrado. Instale em: https://brew.sh"
        echo "📥 Ou baixe Docker Desktop: https://www.docker.com/products/docker-desktop"
    fi
    
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    echo "🪟 Sistema Windows detectado"
    echo "📥 Baixe e instale Docker Desktop: https://www.docker.com/products/docker-desktop"
fi

echo ""
echo "✅ Instalação concluída!"
echo "🔄 Reinicie o terminal e execute: ./setup.sh"