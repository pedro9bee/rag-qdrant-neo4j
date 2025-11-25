#!/bin/bash

# ============================================================================
# LangGraph Chat API Startup Script
# ============================================================================
# Usage:
#   ./start-langgraph-api.sh local   # Use env.local
#   ./start-langgraph-api.sh vps     # Use env.vps
#   ./start-langgraph-api.sh         # Default: local
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV_MODE="${1:-local}"
ENV_FILE="env.${ENV_MODE}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      LangGraph Chat API - Startup (${ENV_MODE} mode)            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 1. Validate environment file
# ============================================================================
echo -e "${YELLOW}1️⃣  Validating environment file...${NC}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Using environment: $ENV_FILE${NC}"

# ============================================================================
# 2. Check if port 8001 is already in use
# ============================================================================
echo ""
echo -e "${YELLOW}2️⃣  Checking port 8001...${NC}"

if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port 8001 is already in use!${NC}"
    echo ""
    read -p "Kill existing process and continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Stopping existing process...${NC}"
        kill -9 $(lsof -t -i :8001) 2>/dev/null || true
        sleep 2
        echo -e "${GREEN}✓ Process stopped${NC}"
    else
        exit 1
    fi
else
    echo -e "${GREEN}✓ Port 8001 is available${NC}"
fi

# ============================================================================
# 3. Setup virtual environment
# ============================================================================
echo ""
echo -e "${YELLOW}3️⃣  Setting up LangGraph API...${NC}"

cd langgraph

if [ ! -d "venv" ]; then
    echo -e "${BLUE}   Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${BLUE}   Installing dependencies...${NC}"
    pip install -e . --quiet
    echo -e "${GREEN}   ✓ Virtual environment created and dependencies installed${NC}"
else
    source venv/bin/activate
    echo -e "${GREEN}   ✓ Virtual environment activated${NC}"
fi

# Copy environment file
cp "../$ENV_FILE" .env
echo -e "${GREEN}   ✓ Environment configured${NC}"

# ============================================================================
# 4. Start LangGraph Chat API
# ============================================================================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🚀 LangGraph Chat API Ready!                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "   ${GREEN}LangGraph API:${NC}  http://localhost:8001"
echo -e "   ${GREEN}API Docs:${NC}       http://localhost:8001/docs"
echo -e "   ${GREEN}Health Check:${NC}   http://localhost:8001/health"
echo -e "   ${GREEN}Models:${NC}         http://localhost:8001/v1/models"
echo ""
echo -e "${BLUE}🔧 Environment:${NC} ${ENV_MODE} mode ($ENV_FILE)"
echo -e "${BLUE}🤖 Model:${NC}       langgraph-rag-v1"
echo ""
echo -e "${YELLOW}Starting LangGraph Chat API...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Start the API
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

