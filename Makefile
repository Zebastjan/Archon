# Archon Makefile - Simple, Secure, Cross-Platform
SHELL := /bin/bash
.SHELLFLAGS := -ec

# Docker compose command - prefer newer 'docker compose' plugin over standalone 'docker-compose'
COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

.PHONY: help dev dev-docker dev-docker-full dev-work-orders dev-hybrid-work-orders stop test test-fe test-be lint lint-fe lint-be clean install check agent-work-orders health-check deploy index-repos setup-hooks index-commits kg-evolution kg-commits kg-compare kg-when

help:
	@echo "Archon Development Commands"
	@echo "==========================="
	@echo "  make dev                    - Backend in Docker, frontend local (recommended)"
	@echo "  make dev-docker             - Backend + frontend in Docker"
	@echo "  make dev-docker-full        - Everything in Docker (server + mcp + ui + work orders)"
	@echo "  make dev-hybrid-work-orders - Server + MCP in Docker, UI + work orders local (2 terminals)"
	@echo "  make dev-work-orders        - Backend in Docker, agent work orders local, frontend local"
	@echo "  make agent-work-orders      - Run agent work orders service locally"
	@echo "  make health-check           - Validate all services are healthy"
	@echo "  make stop                   - Stop all services"
	@echo "  make test                   - Run all tests"
	@echo "  make test-fe                - Run frontend tests only"
	@echo "  make test-be                - Run backend tests only"
	@echo "  make lint                   - Run all linters"
	@echo "  make lint-fe                - Run frontend linter only"
	@echo "  make lint-be                - Run backend linter only"
	@echo "  make clean                  - Remove containers and volumes"
	@echo "  make install                - Install dependencies"
	@echo "  make check                  - Check environment setup"
	@echo "  make deploy                 - Rebuild container and verify health"
	@echo "  make index-repos            - Index all repositories"
	@echo "  make index-commits          - Index multiple commits (REPO=archon COMMITS=10)"
	@echo "  make kg-evolution           - Show entity evolution (REPO=archon ENTITY=func_name)"
	@echo "  make kg-commits             - List commits with changes (REPO=archon)"
	@echo "  make kg-compare             - Compare branches (REPO=archon BRANCH1=main BRANCH2=feat)"
	@echo "  make kg-when                - Find when entity was added (REPO=archon ENTITY=func_name)"
	@echo "  make generate-embeddings    - Generate BGE-M3 embeddings (REPO=archon BATCH_SIZE=50)"

# Install dependencies
install:
	@echo "Installing dependencies..."
	@cd archon-ui-main && npm install
	@cd python && uv sync --group all --group dev
	@echo "✓ Dependencies installed"

# Check environment
check:
	@echo "Checking environment..."
	@node -v >/dev/null 2>&1 || { echo "✗ Node.js not found (require Node 18+)."; exit 1; }
	@node check-env.js
	@echo "Checking Docker..."
	@docker --version > /dev/null 2>&1 || { echo "✗ Docker not found"; exit 1; }
	@$(COMPOSE) version > /dev/null 2>&1 || { echo "✗ Docker Compose not found"; exit 1; }
	@echo "✓ Environment OK"


# Hybrid development (recommended)
dev: check
	@echo "Starting hybrid development..."
	@echo "Backend: Docker | Frontend: Local with hot reload"
	@$(COMPOSE) --profile backend up -d --build
	@set -a; [ -f .env ] && . ./.env; set +a; \
	echo "Backend running at http://$${HOST:-localhost}:$${ARCHON_SERVER_PORT:-8181}"
	@echo "Starting frontend..."
	@cd archon-ui-main && \
	VITE_ARCHON_SERVER_PORT=$${ARCHON_SERVER_PORT:-8181} \
	VITE_ARCHON_SERVER_HOST=$${HOST:-} \
	npm run dev

# Full Docker development (backend + frontend, no work orders)
dev-docker: check
	@echo "Starting Docker environment (backend + frontend)..."
	@$(COMPOSE) --profile full up -d --build
	@echo "✓ Services running"
	@echo "Frontend: http://localhost:3737"
	@echo "API: http://localhost:8181"

# Full Docker with all services (server + mcp + ui + agent work orders)
dev-docker-full: check
	@echo "Starting full Docker environment with agent work orders..."
	@$(COMPOSE) up archon-server archon-mcp archon-frontend archon-agent-work-orders -d --build
	@set -a; [ -f .env ] && . ./.env; set +a; \
	echo "✓ All services running"; \
	echo "Frontend: http://localhost:3737"; \
	echo "API: http://$${HOST:-localhost}:$${ARCHON_SERVER_PORT:-8181}"; \
	echo "MCP: http://$${HOST:-localhost}:$${ARCHON_MCP_PORT:-8051}"; \
	echo "Agent Work Orders: http://$${HOST:-localhost}:$${AGENT_WORK_ORDERS_PORT:-8053}"

# Agent work orders service locally (standalone)
agent-work-orders:
	@echo "Starting Agent Work Orders service locally..."
	@set -a; [ -f .env ] && . ./.env; set +a; \
	export SERVICE_DISCOVERY_MODE=local; \
	export ARCHON_SERVER_URL=http://localhost:$${ARCHON_SERVER_PORT:-8181}; \
	export ARCHON_MCP_URL=http://localhost:$${ARCHON_MCP_PORT:-8051}; \
	export AGENT_WORK_ORDERS_PORT=$${AGENT_WORK_ORDERS_PORT:-8053}; \
	cd python && uv run python -m uvicorn src.agent_work_orders.server:app --host 0.0.0.0 --port $${AGENT_WORK_ORDERS_PORT:-8053} --reload

# Health check validation
health-check:
	@echo "🔍 Running health check validation..."
	@./scripts/validate_health.sh

# Hybrid development with agent work orders (backend in Docker, agent work orders local, frontend local)
dev-work-orders: check
	@echo "Starting hybrid development with agent work orders..."
	@echo "Backend: Docker | Agent Work Orders: Local | Frontend: Local"
	@$(COMPOSE) up archon-server archon-mcp -d --build
	@set -a; [ -f .env ] && . ./.env; set +a; \
	echo "Backend running at http://$${HOST:-localhost}:$${ARCHON_SERVER_PORT:-8181}"; \
	echo "Starting agent work orders service..."; \
	echo "Run in separate terminal: make agent-work-orders"; \
	echo "Starting frontend..."; \
	cd archon-ui-main && \
	VITE_ARCHON_SERVER_PORT=$${ARCHON_SERVER_PORT:-8181} \
	VITE_ARCHON_SERVER_HOST=$${HOST:-} \
	npm run dev

# Hybrid development: Server + MCP in Docker, UI + Work Orders local (requires 2 terminals)
dev-hybrid-work-orders: check
	@echo "Starting hybrid development: Server + MCP in Docker, UI + Work Orders local"
	@echo "================================================================"
	@$(COMPOSE) up archon-server archon-mcp -d --build
	@set -a; [ -f .env ] && . ./.env; set +a; \
	echo ""; \
	echo "✓ Server + MCP running in Docker"; \
	echo "  Server: http://$${HOST:-localhost}:$${ARCHON_SERVER_PORT:-8181}"; \
	echo "  MCP: http://$${HOST:-localhost}:$${ARCHON_MCP_PORT:-8051}"; \
	echo ""; \
	echo "Next steps:"; \
	echo "  1. Terminal 1 (this one): Press Ctrl+C when done"; \
	echo "  2. Terminal 2: make agent-work-orders"; \
	echo "  3. Terminal 3: cd archon-ui-main && npm run dev"; \
	echo ""; \
	echo "Or use 'make dev-docker-full' to run everything in Docker."; \
	@read -p "Press Enter to continue or Ctrl+C to stop..." _

# Stop all services
stop:
	@echo "Stopping all services..."
	@$(COMPOSE) --profile backend --profile frontend --profile full --profile work-orders down
	@echo "✓ Services stopped"

# Run all tests
test: test-fe test-be

# Run frontend tests
test-fe:
	@echo "Running frontend tests..."
	@cd archon-ui-main && npm test

# Run backend tests
test-be:
	@echo "Running backend tests..."
	@cd python && uv run pytest

# Run all linters
lint: lint-fe lint-be

# Run frontend linter
lint-fe:
	@echo "Linting frontend..."
	@cd archon-ui-main && npm run lint

# Run backend linter
lint-be:
	@echo "Linting backend..."
	@cd python && uv run ruff check --fix

# Clean everything (with confirmation)
clean:
	@echo "⚠️  This will remove all containers and volumes"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(COMPOSE) down -v --remove-orphans; \
		echo "✓ Cleaned"; \
	else \
		echo "Cancelled"; \
	fi

.DEFAULT_GOAL := help

# Run all tests
test:
	cd python && uv run pytest -v

# Quick MCP reload (no rebuild, uses volume-mounted code)
mcp-reload:
	@echo "🔄 Quick MCP reload (no rebuild needed)..."
	@./scripts/mcp-dev-reload.sh

# Full MCP restart with rebuild (slow, use only when deps change)
mcp-restart:
	@echo "🔄 Restarting MCP container with rebuild..."
	@$(COMPOSE) up -d --build archon-mcp
	@sleep 3
	@docker logs archon-mcp --tail 5

# Check MCP status
mcp-status:
	@docker ps --filter "name=archon-mcp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# MCP logs (follow mode)
mcp-logs:
	@docker logs -f archon-mcp --tail 20

# Index all repositories (archon, octofriend, Omnibus, syllablaze)
# Auto-reindex is also triggered on each git commit via hooks
index-repos:
	@echo "Indexing all repositories..."
	@docker exec archon python /archon/scripts/index_all_repos.py
	@echo "✅ Indexing complete"

# Set up git hooks for all repositories to auto-reindex on commit
# Run this from within each repo:
#   git config core.hooksPath /home/zebastjan/dev/archon/scripts/git-hooks
setup-hooks:
	@echo "Setting up git hooks for all repos..."
	@cd /home/zebastjan/dev/archon && git config core.hooksPath /home/zebastjan/dev/archon/scripts/git-hooks || true
	@cd /home/zebastjan/dev/syllablaze && git config core.hooksPath /home/zebastjan/dev/archon/scripts/git-hooks || true
	@cd /home/zebastjan/dev/octofriend && git config core.hooksPath /home/zebastjan/dev/archon/scripts/git-hooks || true
	@cd /home/zebastjan/dev/Omnibus && git config core.hooksPath /home/zebastjan/dev/archon/scripts/git-hooks || true
	@echo "✅ Git hooks configured in all repos"

# Index multiple commits for knowledge graph (cross-commit tracking)
# Example: make index-commits REPO=archon COMMITS=10
index-commits:
	@echo "Indexing multiple commits for knowledge graph..."
	@docker exec archon python /archon/scripts/index_commits.py --repo $(REPO) --commits $(COMMITS)
	@echo "✅ Multi-commit indexing complete"

# Query the knowledge graph
# Example: make kg-evolution REPO=archon ENTITY=load_config
# Example: make kg-commits REPO=archon
kg-evolution:
	@docker exec archon python /archon/scripts/kg_query.py --repo $(REPO) evolution --entity $(ENTITY)

kg-commits:
	@docker exec archon python /archon/scripts/kg_query.py --repo $(REPO) commits

kg-compare:
	@docker exec archon python /archon/scripts/kg_query.py --repo $(REPO) compare-branches $(BRANCH1) $(BRANCH2)

kg-when:
	@docker exec archon python /archon/scripts/kg_query.py --repo $(REPO) when-added --entity $(ENTITY)

# Generate embeddings for code entities
# Example: make generate-embeddings (all repos)
# Example: make generate-embeddings REPO=archon
# Example: make generate-embeddings BATCH_SIZE=100
generate-embeddings:
	@echo "Generating embeddings..."
	@docker exec archon python /archon/scripts/generate_embeddings.py \
		$(if $(REPO),--repo $(REPO),) \
		$(if $(BATCH_SIZE),--batch-size $(BATCH_SIZE),--batch-size 50)

# Deploy: rebuild and restart container with health verification
deploy:
	@echo "Syncing .env to container..."
	@docker cp .env archon:/app/.env 2>/dev/null || true
	@echo "Building Docker image..."
	@$(COMPOSE) build --no-cache
	@echo "Stopping current container..."
	@$(COMPOSE) down
	@echo "Starting new container..."
	@$(COMPOSE) up -d
	@echo "Running migrations..."
	@docker exec archon python -c "from src.server.api_routes.migration import run_migrations; import asyncio; asyncio.run(run_migrations())" 2>/dev/null || echo "No migrations to run or migration module not found"
	@echo "Verifying health..."
	@./scripts/validate_health.sh
	@echo "✅ Deploy complete!"
