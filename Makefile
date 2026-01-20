.PHONY: help install test lint format clean docker-up docker-down migrate db-reset

help:
	@echo "Available commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run linters (flake8, mypy)"
	@echo "  make format       - Format code with black and isort"
	@echo "  make clean        - Remove build artifacts and cache"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make migrate      - Run database migrations"
	@echo "  make db-reset     - Reset database (WARNING: destroys data)"
	@echo "  make compile      - Compile smart contracts"
	@echo "  make test-contracts - Test smart contracts with Foundry"

install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt

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
	@echo "Deploying to testnet..."
	npx hardhat run scripts/deploy.ts --network mumbai

verify-contract:
	@echo "Verifying contract on block explorer..."
	@read -p "Enter contract address: " addr; \
	@read -p "Enter network (mumbai/polygon): " network; \
	npx hardhat verify --network $$network $$addr

run-local:
	@echo "Starting local development server..."
	python -m src.main

run-bot:
	@echo "Starting arbitrage bot..."
	python -m src.bot.main

shell:
	@echo "Starting Python shell with project context..."
	python -i -c "from src import *"
