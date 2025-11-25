#!/bin/bash

# ============================================================================
# RAG System - Stop Script
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         RAG System - Stopping Services                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Stop RAG API (if running in background)
echo -e "${YELLOW}Stopping RAG API (port 8000)...${NC}"
pkill -f "uvicorn app.main:app" 2>/dev/null && echo -e "${GREEN}✓ RAG API stopped${NC}" || echo -e "${BLUE}RAG API not running${NC}"

# Stop LangGraph Chat API (if running in background)
echo -e "${YELLOW}Stopping LangGraph Chat API (port 8001)...${NC}"
pkill -f "uvicorn api.main:app" 2>/dev/null && echo -e "${GREEN}✓ LangGraph API stopped${NC}" || echo -e "${BLUE}LangGraph API not running${NC}"

# Alternative: kill by port
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Force stopping port 8000...${NC}"
    kill -9 $(lsof -t -i :8000) 2>/dev/null || true
fi

if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}Force stopping port 8001...${NC}"
    kill -9 $(lsof -t -i :8001) 2>/dev/null || true
fi

# Stop Docker services
echo -e "${YELLOW}Stopping Docker services...${NC}"
docker-compose down
echo -e "${GREEN}✓ Docker services stopped${NC}"

echo ""
echo -e "${GREEN}All services stopped!${NC}"

