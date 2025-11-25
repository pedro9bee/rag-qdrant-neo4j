#!/bin/bash

# ============================================================================
# RAG System Local Startup Script
# ============================================================================
# Usage:
#   ./start-local.sh local   # Use env.local
#   ./start-local.sh vps     # Use env.vps
#   ./start-local.sh         # Default: local
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV_MODE="${1:-local}"  # Default to 'local' if no parameter
ENV_FILE="env.${ENV_MODE}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         RAG System - Local Startup (${ENV_MODE} mode)              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 1. Validate environment file
# ============================================================================
echo -e "${YELLOW}1️⃣  Validating environment file...${NC}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    echo -e "${YELLOW}Available files:${NC}"
    ls -1 env.* 2>/dev/null || echo "  No env files found!"
    echo ""
    echo -e "${YELLOW}Usage: ./start-local.sh [local|vps]${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Using environment: $ENV_FILE${NC}"

# Copy to .env for easy access
cp "$ENV_FILE" .env
echo -e "${GREEN}✅ Copied to .env${NC}"

# ============================================================================
# 2. Check LLM Service (Salad Cloud or Local Ollama)
# ============================================================================
echo ""
echo -e "${YELLOW}2️⃣  Checking LLM service...${NC}"

# Extract URL from env file - remove comments and get clean value
OLLAMA_URL=$(grep "^OLLAMA_BASE_URL=" "$ENV_FILE" | grep -v "^#" | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d ' ')

if [ -z "$OLLAMA_URL" ]; then
    OLLAMA_URL="http://localhost:11434"
fi

echo -e "${BLUE}   LLM URL: $OLLAMA_URL${NC}"

# Check if it's Salad Cloud (external API) or local Ollama
if [[ "$OLLAMA_URL" == *"salad.cloud"* ]] || [[ "$OLLAMA_URL" == *"https://"* ]]; then
    echo -e "${GREEN}✅ Using Salad Cloud (External API)${NC}"
    echo -e "${BLUE}   Testing connectivity...${NC}"
    
    # Test with vLLM endpoint
    if curl -s -f -m 5 "$OLLAMA_URL/v1/models" > /dev/null 2>&1 || \
       curl -s -f -m 5 "$OLLAMA_URL/health" > /dev/null 2>&1 || \
       curl -s -m 5 "$OLLAMA_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✓ Salad Cloud is accessible${NC}"
        echo -e "${BLUE}   Model: Qwen/Qwen2.5-7B-Instruct${NC}"
    else
        echo -e "${YELLOW}⚠️  Cannot verify Salad Cloud connectivity${NC}"
        echo -e "${BLUE}   This might be normal if the service requires authentication${NC}"
        echo -e "${BLUE}   The API will test the connection when making requests${NC}"
    fi
else
    # Local Ollama
    echo -e "${BLUE}   Testing local Ollama...${NC}"
    
    if curl -s -f "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama is running and accessible${NC}"
        
        # Check for required models
        echo -e "${BLUE}   Checking models...${NC}"
        MODELS=$(curl -s "$OLLAMA_URL/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "")
        
        if echo "$MODELS" | grep -q "bge-m3"; then
            echo -e "${GREEN}   ✓ bge-m3:latest found${NC}"
        else
            echo -e "${YELLOW}   ⚠  bge-m3:latest not found. Pull with: ollama pull bge-m3:latest${NC}"
        fi
    else
        echo -e "${RED}❌ Ollama is not accessible at $OLLAMA_URL${NC}"
        echo ""
        echo -e "${YELLOW}To start Ollama:${NC}"
        echo -e "  ${BLUE}OLLAMA_HOST=0.0.0.0 ollama serve${NC}"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# ============================================================================
# 3. Start Docker services
# ============================================================================
echo ""
echo -e "${YELLOW}3️⃣  Starting Docker infrastructure...${NC}"
echo -e "${BLUE}   Services: MinIO, Neo4j, Qdrant, Redis, Open WebUI${NC}"

docker-compose up -d

echo -e "${GREEN}✅ Docker services started${NC}"

# ============================================================================
# 4. Wait for services to be ready
# ============================================================================
echo ""
echo -e "${YELLOW}4️⃣  Waiting for services to be healthy...${NC}"

check_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=0
    
    echo -n -e "${BLUE}   Checking $name...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
        echo -n "."
    done
    
    echo -e " ${YELLOW}⚠${NC}"
    return 1
}

check_service "Neo4j" "http://localhost:7474"
check_service "Qdrant" "http://localhost:6333"
check_service "MinIO" "http://localhost:9002/minio/health/live"

echo -e "${GREEN}✅ Core services are ready${NC}"

# ============================================================================
# 5. Check if port 8000 is already in use (before cd to rag-api)
# ============================================================================
echo ""
echo -e "${YELLOW}5️⃣  Checking port 8000...${NC}"

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use!${NC}"
    echo ""
    echo -e "${BLUE}Process using port 8000:${NC}"
    lsof -i :8000
    echo ""
    read -p "Kill existing process and continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Stopping existing process...${NC}"
        kill -9 $(lsof -t -i :8000) 2>/dev/null || true
        sleep 2
        echo -e "${GREEN}✓ Process stopped${NC}"
    else
        echo -e "${RED}Aborting. Please stop the service manually:${NC}"
        echo -e "  ${BLUE}kill -9 \$(lsof -t -i :8000)${NC}"
        echo -e "  ${BLUE}# or${NC}"
        echo -e "  ${BLUE}pkill -f 'uvicorn app.main:app'${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Port 8000 is available${NC}"
fi

# ============================================================================
# 6. Setup RAG API virtual environment
# ============================================================================
echo ""
echo -e "${YELLOW}6️⃣  Setting up RAG API...${NC}"

cd rag-api

if [ ! -d "venv" ]; then
    echo -e "${BLUE}   Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}   ✓ Virtual environment created${NC}"
fi

echo -e "${BLUE}   Activating virtual environment...${NC}"
source venv/bin/activate

# Check if dependencies need to be installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${BLUE}   Installing dependencies from pyproject.toml...${NC}"
    pip install -e . --quiet
    echo -e "${GREEN}   ✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}   ✓ Dependencies already installed${NC}"
fi

# Copy environment file
cp "../$ENV_FILE" .env
echo -e "${GREEN}   ✓ Environment configured${NC}"

# ============================================================================
# 7. Start RAG API
# ============================================================================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    🚀 System Ready!                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "   ${GREEN}RAG API:${NC}       http://localhost:8000"
echo -e "   ${GREEN}API Docs:${NC}      http://localhost:8000/docs"
echo -e "   ${GREEN}Open WebUI:${NC}    http://localhost:3000"
echo -e "   ${GREEN}Neo4j:${NC}         http://localhost:7474"
echo -e "   ${GREEN}MinIO Console:${NC} http://localhost:9003"
echo -e "   ${GREEN}Qdrant:${NC}        http://localhost:6333/dashboard"
echo ""
echo -e "${BLUE}🔧 Environment:${NC} ${ENV_MODE} mode ($ENV_FILE)"
echo -e "${BLUE}🤖 LLM Service:${NC}  $OLLAMA_URL"
echo ""
echo -e "${YELLOW}Starting RAG API...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Start the API with auto-reload for development
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

