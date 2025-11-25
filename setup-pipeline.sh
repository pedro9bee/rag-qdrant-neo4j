#!/bin/bash

# ============================================================================
# Setup RAG Pipeline Dependencies
# ============================================================================
# Instala todas as dependências necessárias para o pipeline RAG
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     RAG Pipeline - Instalação de Dependências    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 1. Verificar Python
# ============================================================================
echo -e "${YELLOW}1️⃣  Verificando Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 não encontrado${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"

# ============================================================================
# 2. Verificar/Criar venv no rag-api
# ============================================================================
echo ""
echo -e "${YELLOW}2️⃣  Configurando ambiente virtual...${NC}"
cd rag-api

if [ ! -d "venv" ]; then
    echo -e "${BLUE}   Criando venv...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}   ✓ venv criado${NC}"
else
    echo -e "${GREEN}   ✓ venv já existe${NC}"
fi

# ============================================================================
# 3. Ativar venv e instalar dependências
# ============================================================================
echo ""
echo -e "${YELLOW}3️⃣  Instalando dependências Python...${NC}"
source venv/bin/activate

echo -e "${BLUE}   Atualizando pip...${NC}"
pip install --upgrade pip --quiet

echo -e "${BLUE}   Instalando pacotes via pyproject.toml...${NC}"
pip install -e . --quiet

if [ $? -eq 0 ]; then
    echo -e "${GREEN}   ✓ Dependências instaladas${NC}"
else
    echo -e "${RED}   ❌ Erro na instalação das dependências${NC}"
    exit 1
fi

# ============================================================================
# 4. Instalar modelo spaCy
# ============================================================================
echo ""
echo -e "${YELLOW}4️⃣  Instalando modelo spaCy (en_core_web_lg)...${NC}"
echo -e "${BLUE}   Isso pode demorar alguns minutos...${NC}"

if python -c "import spacy; spacy.load('en_core_web_lg')" 2>/dev/null; then
    echo -e "${GREEN}   ✓ Modelo spaCy já instalado${NC}"
else
    echo -e "${BLUE}   Baixando en_core_web_lg...${NC}"
    python -m spacy download en_core_web_lg
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✓ Modelo spaCy instalado${NC}"
    else
        echo -e "${RED}   ❌ Erro ao instalar modelo spaCy${NC}"
        exit 1
    fi
fi

# ============================================================================
# 4.5. Verificar e instalar MLX (Apple Silicon)
# ============================================================================
echo ""
echo -e "${YELLOW}4.5️⃣  Verificando suporte MLX (Apple Silicon)...${NC}"

if [[ "$(uname)" == "Darwin" ]]; then
    if sysctl -n machdep.cpu.brand_string 2>/dev/null | grep -q "Apple"; then
        echo -e "${GREEN}   ✓ Apple Silicon detectado (M-series)${NC}"
        echo -e "${BLUE}   Instalando MLX para performance otimizada...${NC}"
        
        if pip install mlx==0.30.0 mlx-lm==0.28.3 --quiet 2>/dev/null; then
            echo -e "${GREEN}   ✓ MLX instalado (v0.30.0 + mlx-lm v0.28.3)${NC}"
            echo -e "${BLUE}   Sistema usará MLX automaticamente para validação de entidades${NC}"
            echo -e "${BLUE}   Performance esperada: 2-3x mais rápido que Ollama${NC}"
        else
            echo -e "${YELLOW}   ⚠ Falha ao instalar MLX (continuará com Ollama)${NC}"
            echo -e "${BLUE}     Para instalar manualmente: pip install mlx==0.30.0 mlx-lm==0.28.3${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠ Mac Intel detectado (MLX não suportado)${NC}"
        echo -e "${BLUE}   Sistema usará Ollama${NC}"
    fi
else
    echo -e "${BLUE}   ℹ  Plataforma $(uname) detectada (MLX não disponível)${NC}"
    echo -e "${BLUE}   Sistema usará Ollama${NC}"
fi

# ============================================================================
# 5. Verificar Redis
# ============================================================================
echo ""
echo -e "${YELLOW}5️⃣  Verificando Redis...${NC}"
if docker ps | grep -q "redis"; then
    echo -e "${GREEN}   ✓ Redis rodando no Docker${NC}"
else
    echo -e "${YELLOW}   ⚠  Redis não encontrado. Inicie com: docker-compose up -d${NC}"
fi

# ============================================================================
# 6. Verificar Ollama
# ============================================================================
echo ""
echo -e "${YELLOW}6️⃣  Verificando Ollama...${NC}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}   ✓ Ollama acessível${NC}"
    
    # Verificar modelos necessários
    MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
    
    echo -e "${BLUE}   Verificando modelos necessários:${NC}"
    
    if echo "$MODELS" | grep -q "bge-m3"; then
        echo -e "${GREEN}   ✓ bge-m3:latest${NC}"
    else
        echo -e "${YELLOW}   ⚠ bge-m3:latest não encontrado${NC}"
        echo -e "${BLUE}     Execute: ollama pull bge-m3:latest${NC}"
    fi
    
    if echo "$MODELS" | grep -q "uniner-7b"; then
        echo -e "${GREEN}   ✓ pedro9bee/uniner-7b-all:gguf-q4${NC}"
    else
        echo -e "${YELLOW}   ⚠ pedro9bee/uniner-7b-all:gguf-q4 não encontrado${NC}"
        echo -e "${BLUE}     Execute: ollama pull pedro9bee/uniner-7b-all:gguf-q4${NC}"
    fi
    
    if echo "$MODELS" | grep -q "mistral-7b"; then
        echo -e "${GREEN}   ✓ mistral-7b-v0.3:latest${NC}"
    else
        echo -e "${YELLOW}   ⚠ mistral-7b-v0.3:latest não encontrado${NC}"
        echo -e "${BLUE}     Execute: ollama pull mistral-7b-v0.3:latest${NC}"
    fi
else
    echo -e "${YELLOW}   ⚠  Ollama não acessível em http://localhost:11434${NC}"
    echo -e "${BLUE}     Execute: OLLAMA_HOST=0.0.0.0 ollama serve${NC}"
fi

# ============================================================================
# 7. Verificar env.local
# ============================================================================
echo ""
echo -e "${YELLOW}7️⃣  Verificando configuração...${NC}"
cd ..
if [ -f "env.local" ]; then
    echo -e "${GREEN}   ✓ env.local encontrado${NC}"
else
    echo -e "${YELLOW}   ⚠  env.local não encontrado${NC}"
    echo -e "${BLUE}     Copie de env.example se necessário${NC}"
fi

# ============================================================================
# Resumo Final
# ============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ Setup Completo!                      ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📦 Instalado:${NC}"
echo -e "   • Python venv e dependências"
echo -e "   • Redis client"
echo -e "   • spaCy + en_core_web_lg"
echo -e "   • FastAPI e LangChain"
echo -e "   • MLX Framework (Apple Silicon apenas, se detectado)"
echo ""
echo -e "${BLUE}🚀 Próximos passos:${NC}"
echo -e "   1. Certifique-se que Ollama está rodando:"
echo -e "      ${GREEN}OLLAMA_HOST=0.0.0.0 ollama serve${NC}"
echo ""
echo -e "   2. Inicie os serviços Docker:"
echo -e "      ${GREEN}docker-compose up -d${NC}"
echo ""
echo -e "   3. Inicie o RAG API:"
echo -e "      ${GREEN}./start-local.sh local${NC}"
echo ""
echo -e "${BLUE}📚 Documentação:${NC}"
echo -e "   • PIPELINE_USAGE.md - Guia completo do pipeline"
echo -e "   • http://localhost:8000/docs - Swagger UI"
echo ""

