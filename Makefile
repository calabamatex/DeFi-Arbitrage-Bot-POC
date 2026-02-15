.PHONY: help install install-dev test lint format clean docker-up docker-down docker-build migrate db-reset setup start stop status logs validate smoke-test

help:
	@echo "Available commands:"
	@echo ""
	@echo "  Quick Start:"
	@echo "  make setup          - First-time setup (copy .env, validate, start infra, migrate)"
	@echo "  make start          - Start full stack (infra + bot)"
	@echo "  make stop           - Stop all containers"
	@echo "  make status         - Check bot health and metrics"
	@echo "  make logs           - Tail bot logs"
	@echo "  make validate       - Validate configuration"
	@echo "  make smoke-test     - Run testnet smoke test"
	@echo ""
	@echo "  Development:"
	@echo "  make install        - Install Python runtime dependencies"
	@echo "  make install-dev    - Install runtime + dev/test dependencies"
	@echo "  make test           - Run tests with coverage"
	@echo "  make lint           - Run linters (flake8, mypy)"
	@echo "  make format         - Format code with black and isort"
	@echo "  make clean          - Remove build artifacts and cache"
	@echo ""
	@echo "  Docker:"
	@echo "  make docker-build   - Build bot Docker image"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
	@echo ""
	@echo "  Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migration      - Create new migration"
	@echo "  make db-reset       - Reset database (WARNING: destroys data)"
	@echo ""
	@echo "  Contracts:"
	@echo "  make compile        - Compile smart contracts"
	@echo "  make test-contracts - Test smart contracts with Foundry"

install:
	@echo "Installing Python runtime dependencies..."
	pip install -r requirements.txt

install-dev:
	@echo "Installing Python dev dependencies..."
	pip install -r requirements-dev.txt

test:
	@echo "Running tests..."
	pytest -v --cov=src --cov-report=html --cov-report=term

test-unit:
	@echo "Running unit tests..."
	pytest test/unit -v

test-integration:
	@echo "Running integration tests..."
	pytest test/integration -v

test-e2e:
	@echo "Running e2e tests..."
	pytest test/e2e -v

lint:
	@echo "Running linters..."
	flake8 src test
	mypy src

format:
	@echo "Formatting code..."
	black src test
	isort src test

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	rm -rf build dist

docker-build:
	@echo "Building bot Docker image..."
	docker build -t arb-bot .

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d
	@echo "Waiting for containers to be healthy..."
	sleep 5
	docker-compose ps

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	docker-compose logs -f

migrate:
	@echo "Running database migrations..."
	alembic upgrade head

migration:
	@echo "Creating new migration..."
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-reset:
	@echo "WARNING: This will destroy all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker-compose up -d postgres; \
		sleep 5; \
		alembic upgrade head; \
	fi

compile:
	@echo "Compiling smart contracts with Hardhat..."
	npx hardhat compile

compile-foundry:
	@echo "Compiling smart contracts with Foundry..."
	forge build

test-contracts:
	@echo "Testing smart contracts with Foundry..."
	forge test -vvv

test-contracts-gas:
	@echo "Testing smart contracts with gas report..."
	forge test --gas-report

deploy-testnet:
	@echo "Deploying contracts to testnet via Foundry..."
	@read -p "Enter chain (polygon_amoy/arbitrum_sepolia): " chain; \
	forge script script/Deploy.s.sol --rpc-url $$chain --broadcast --verify

run-bot:
	@echo "Starting arbitrage bot..."
	python run_bot.py

run-liquidation-bot:
	@echo "Starting liquidation bot..."
	python run_liquidation_bot.py

shell:
	@echo "Starting Python shell with project context..."
	python -i -c "from src import *"

# ============================================================
# Quick Start Targets
# ============================================================

setup:
	@echo "=== First-time setup ==="
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — edit it with your values")
	@test -f .env && echo ".env exists"
	pip install -r requirements.txt
	@echo ""
	@echo "--- Validating configuration ---"
	python scripts/validate_config.py || true
	@echo ""
	@echo "--- Starting infrastructure ---"
	docker-compose up -d postgres redis
	@echo "Waiting for services to be healthy..."
	@sleep 8
	@echo ""
	@echo "--- Running database migrations ---"
	alembic upgrade head
	@echo ""
	@echo "=== Setup complete ==="
	@echo "Next steps:"
	@echo "  1. Edit .env with your RPC URLs and key"
	@echo "  2. Deploy contracts: make deploy-testnet"
	@echo "  3. Run smoke test: make smoke-test"
	@echo "  4. Start bot: make start"

start:
	@echo "Starting full stack..."
	docker-compose up -d
	@echo "Waiting for services..."
	@sleep 5
	@docker-compose ps
	@echo ""
	@echo "Health: http://localhost:8080/health"
	@echo "Metrics: http://localhost:8080/metrics"

stop:
	@echo "Stopping all containers..."
	docker-compose down
	@echo "All containers stopped."

status:
	@echo "=== Bot Status ==="
	@curl -s http://localhost:8080/health 2>/dev/null | python -m json.tool 2>/dev/null || echo "Bot not reachable at :8080"
	@echo ""
	@echo "=== Container Status ==="
	@docker-compose ps 2>/dev/null || echo "Docker Compose not running"

logs:
	docker-compose logs -f arb-bot

validate:
	python scripts/validate_config.py

smoke-test:
	@echo "Running smoke tests..."
	@read -p "Chain (polygon_amoy/arbitrum_sepolia): " chain; \
	python scripts/testnet_smoke_test.py --chain $$chain
