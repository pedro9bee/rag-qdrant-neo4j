.PHONY: help up down restart status logs logs-follow clean health ps shell-kestra shell-minio check-services

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
BLUE := \033[0;34m
NC := \033[0m # No Color

COMPOSE := docker compose

help: ## Shows this help message
	@echo "$(GREEN)Kestra + RAG Stack Management$(NC)"
	@echo ""
	@echo "$(BLUE)Stack Management:$(NC)"
	@echo "  $(YELLOW)make up$(NC)              - Start all services in detached mode"
	@echo "  $(YELLOW)make down$(NC)            - Stop and remove all containers"
	@echo "  $(YELLOW)make restart$(NC)         - Restart all services"
	@echo "  $(YELLOW)make status$(NC)          - Show status of all services"
	@echo "  $(YELLOW)make ps$(NC)              - List running containers"
	@echo ""
	@echo "$(BLUE)Logs:$(NC)"
	@echo "  $(YELLOW)make logs$(NC)            - Show logs from all services"
	@echo "  $(YELLOW)make logs-follow$(NC)     - Follow logs from all services"
	@echo "  $(YELLOW)make logs SERVICE=kestra$(NC) - Show logs from specific service"
	@echo ""
	@echo "$(BLUE)Health & Monitoring:$(NC)"
	@echo "  $(YELLOW)make health$(NC)          - Check health status of all services"
	@echo "  $(YELLOW)make check-services$(NC)  - Verify all services are running"
	@echo ""
	@echo "$(BLUE)Shell Access:$(NC)"
	@echo "  $(YELLOW)make shell-kestra$(NC)    - Open shell in Kestra container"
	@echo "  $(YELLOW)make shell-minio$(NC)     - Open shell in MinIO container"
	@echo ""
	@echo "$(BLUE)Cleanup:$(NC)"
	@echo "  $(YELLOW)make clean$(NC)           - Remove all containers, volumes and networks"
	@echo ""
	@echo "$(BLUE)Service URLs:$(NC)"
	@echo "  Kestra UI:      $(GREEN)http://localhost:8080$(NC)"
	@echo "  MinIO Console:  $(GREEN)http://localhost:9003$(NC) (minioadmin/minioadmin)"
	@echo "  Neo4J Browser:  $(GREEN)http://localhost:7474$(NC) (neo4j/neo4j_password)"
	@echo "  QDrant API:     $(GREEN)http://localhost:6333$(NC)"
	@echo "  QDrant Dashboard: $(GREEN)http://localhost:6333/dashboard$(NC)"
	@echo ""

up: ## Start all services
	@echo "$(GREEN)🚀 Starting Kestra + RAG Stack...$(NC)"
	@$(COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)✓ Stack is starting up!$(NC)"
	@echo "$(YELLOW)ℹ Services may take up to 60 seconds to be fully ready$(NC)"
	@echo ""
	@echo "Run $(YELLOW)make health$(NC) to check service status"

down: ## Stop and remove all containers
	@echo "$(YELLOW)🛑 Stopping all services...$(NC)"
	@$(COMPOSE) down
	@echo "$(GREEN)✓ All services stopped$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)🔄 Restarting all services...$(NC)"
	@$(COMPOSE) restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

status: ## Show service status
	@echo "$(BLUE)📊 Service Status:$(NC)"
	@$(COMPOSE) ps

ps: status ## Alias for status

logs: ## Show logs from all services (or specific SERVICE=name)
ifdef SERVICE
	@$(COMPOSE) logs --tail=100 $(SERVICE)
else
	@$(COMPOSE) logs --tail=100
endif

logs-follow: ## Follow logs from all services
	@echo "$(BLUE)📋 Following logs (Ctrl+C to stop)...$(NC)"
	@$(COMPOSE) logs -f

health: ## Check health status of all services
	@echo "$(BLUE)🏥 Health Check:$(NC)"
	@echo ""
	@echo -n "Kestra:  "
	@if curl -sf http://localhost:8080/ > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Healthy$(NC)"; \
	else \
		echo "$(RED)✗ Unhealthy or not ready$(NC)"; \
	fi
	@echo -n "MinIO:   "
	@if curl -sf http://localhost:9002/minio/health/live > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Healthy$(NC)"; \
	else \
		echo "$(RED)✗ Unhealthy or not ready$(NC)"; \
	fi
	@echo -n "Neo4J:   "
	@if curl -sf http://localhost:7474 > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Healthy$(NC)"; \
	else \
		echo "$(RED)✗ Unhealthy or not ready$(NC)"; \
	fi
	@echo -n "QDrant:  "
	@if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Healthy$(NC)"; \
	else \
		echo "$(RED)✗ Unhealthy or not ready$(NC)"; \
	fi
	@echo ""

check-services: ## Verify all services are running
	@echo "$(BLUE)🔍 Checking if all services are running...$(NC)"
	@MISSING=0; \
	for service in kestra minio neo4j qdrant; do \
		if ! docker ps --format '{{.Names}}' | grep -q "^$$service$$"; then \
			echo "$(RED)✗ $$service is not running$(NC)"; \
			MISSING=$$((MISSING + 1)); \
		else \
			echo "$(GREEN)✓ $$service is running$(NC)"; \
		fi; \
	done; \
	if [ $$MISSING -gt 0 ]; then \
		echo ""; \
		echo "$(YELLOW)Run 'make up' to start missing services$(NC)"; \
		exit 1; \
	else \
		echo ""; \
		echo "$(GREEN)✓ All services are running!$(NC)"; \
	fi

shell-kestra: ## Open shell in Kestra container
	@echo "$(BLUE)🐚 Opening shell in Kestra container...$(NC)"
	@docker exec -it kestra /bin/bash

shell-minio: ## Open shell in MinIO container
	@echo "$(BLUE)🐚 Opening shell in MinIO container...$(NC)"
	@docker exec -it minio /bin/sh

clean: ## Remove all containers, volumes and networks
	@echo "$(RED)⚠️  WARNING: This will remove all containers, volumes and data!$(NC)"
	@echo -n "$(YELLOW)Are you sure? [y/N] $(NC)" && read ans && [ $${ans:-N} = y ]
	@echo "$(RED)🧹 Cleaning up...$(NC)"
	@$(COMPOSE) down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Legacy targets (kept for backwards compatibility)
.PHONY: check-docker check-qdrant check-neo4j

check-docker: ## Check if Docker is running
	@if ! docker info >/dev/null 2>&1; then \
		echo "$(RED)✗ Docker is not running or not accessible$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Docker is running$(NC)"; \
	fi

check-qdrant: check-docker ## Check if QDrant container is running
	@if ! docker ps --format '{{.Names}}' | grep -q '^qdrant$$'; then \
		echo "$(YELLOW)⚠ Container 'qdrant' is not running$(NC)"; \
		echo "$(YELLOW)  Run: make up$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Container 'qdrant' is running$(NC)"; \
	fi

check-neo4j: check-docker ## Check if Neo4J container is running
	@if ! docker ps --format '{{.Names}}' | grep -q '^neo4j$$'; then \
		echo "$(YELLOW)⚠ Container 'neo4j' is not running$(NC)"; \
		echo "$(YELLOW)  Run: make up$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Container 'neo4j' is running$(NC)"; \
	fi
