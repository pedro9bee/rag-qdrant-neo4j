#!/bin/bash

# ============================================================================
# LangGraph Standalone Runner
# ============================================================================
# Usage:
#   ./start-langgraph.sh local ingest --bucket documents
#   ./start-langgraph.sh vps query "What is LangGraph?"
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ENV_MODE="${1:-local}"
ENV_FILE="env.${ENV_MODE}"
shift || true  # Remove first argument

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         LangGraph Runner (${ENV_MODE} mode)                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Validate environment
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    echo -e "${YELLOW}Usage: ./start-langgraph.sh [local|vps] <command> [args]${NC}"
    exit 1
fi

cd langgraph

# Setup venv
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${BLUE}Installing dependencies...${NC}"
    pip install -e . --quiet
    echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"
else
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
fi

# Copy environment
cp "../$ENV_FILE" .env

echo -e "${GREEN}Environment: ${ENV_MODE}${NC}"
echo ""

# Run command
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${BLUE}./start-langgraph.sh [local|vps] ingest --bucket documents${NC}"
    echo -e "  ${BLUE}./start-langgraph.sh [local|vps] query 'What is LangGraph?'${NC}"
    echo ""
    exit 1
fi

echo -e "${BLUE}Running: python run_standalone.py $@${NC}"
echo ""

python run_standalone.py "$@"

