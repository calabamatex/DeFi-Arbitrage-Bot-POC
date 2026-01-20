#!/bin/bash

# Flash Loan Arbitrage Bot - Setup Script
# This script helps automate the development environment setup

set -e  # Exit on error

echo "========================================="
echo "Flash Loan Arbitrage Bot - Setup Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python virtual environment is activated
check_venv() {
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
        echo "Activating virtual environment..."
        source .venv/bin/activate
    else
        echo -e "${GREEN}✅ Virtual environment active${NC}"
    fi
}

# Check Docker installation
check_docker() {
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✅ Docker installed${NC}"

        # Check if Docker daemon is running
        if docker info &> /dev/null; then
            echo -e "${GREEN}✅ Docker is running${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Docker is installed but not running${NC}"
            echo "Please start Docker Desktop from Applications"
            return 1
        fi
    else
        echo -e "${RED}❌ Docker not installed${NC}"
        echo ""
        echo "To install Docker Desktop:"
        echo "1. Download from: https://www.docker.com/products/docker-desktop"
        echo "2. Or use Homebrew: brew install --cask docker"
        echo "3. Open Docker Desktop and start it"
        return 1
    fi
}

# Start Docker containers
start_docker() {
    echo ""
    echo "Starting Docker containers..."

    if check_docker; then
        docker-compose up -d
        echo ""
        echo "Waiting for containers to be healthy..."
        sleep 10
        docker-compose ps
        echo -e "${GREEN}✅ Docker containers started${NC}"
    else
        echo -e "${YELLOW}⚠️  Skipping Docker container startup${NC}"
        return 1
    fi
}

# Setup database
setup_database() {
    echo ""
    echo "Setting up database..."

    # Check if Alembic is initialized
    if [ ! -d "alembic/versions" ]; then
        echo "Initializing Alembic..."
        source .venv/bin/activate
        alembic init alembic

        # Update alembic.ini with database URL
        sed -i.bak 's|sqlalchemy.url = .*|sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/arbitrage_bot|' alembic.ini
        rm alembic.ini.bak

        echo -e "${GREEN}✅ Alembic initialized${NC}"
    else
        echo -e "${GREEN}✅ Alembic already initialized${NC}"
    fi

    # Check if database is accessible
    if docker exec arbitrage_postgres psql -U postgres -d arbitrage_bot -c "SELECT 1" &> /dev/null; then
        echo -e "${GREEN}✅ Database connection successful${NC}"

        # Run migrations
        echo "Running database migrations..."
        source .venv/bin/activate
        alembic upgrade head
        echo -e "${GREEN}✅ Database migrations complete${NC}"
    else
        echo -e "${YELLOW}⚠️  Cannot connect to database${NC}"
        echo "Make sure Docker containers are running: make docker-up"
    fi
}

# Create .env file if it doesn't exist
setup_env() {
    if [ ! -f ".env" ]; then
        echo ""
        echo "Creating .env file from template..."
        cp .env.example .env
        echo -e "${GREEN}✅ .env file created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env file with your configuration${NC}"
    else
        echo -e "${GREEN}✅ .env file exists${NC}"
    fi
}

# Install npm dependencies
setup_npm() {
    echo ""
    echo "Checking npm dependencies..."

    if [ ! -d "node_modules" ]; then
        echo "Installing npm dependencies..."
        npm install
        echo -e "${GREEN}✅ npm dependencies installed${NC}"
    else
        echo -e "${GREEN}✅ npm dependencies already installed${NC}"
    fi
}

# Compile smart contracts
compile_contracts() {
    echo ""
    echo "Compiling smart contracts..."

    if [ -f "hardhat.config.ts" ]; then
        npx hardhat compile
        echo -e "${GREEN}✅ Smart contracts compiled with Hardhat${NC}"
    fi

    # Check if Foundry is available
    if command -v forge &> /dev/null; then
        forge build
        echo -e "${GREEN}✅ Smart contracts compiled with Foundry${NC}"
    fi
}

# Main setup flow
main() {
    echo "Starting setup process..."
    echo ""

    # 1. Check virtual environment
    check_venv

    # 2. Setup .env file
    setup_env

    # 3. Setup npm dependencies
    setup_npm

    # 4. Start Docker (if available)
    if start_docker; then
        # 5. Setup database (only if Docker is running)
        setup_database
    else
        echo ""
        echo -e "${YELLOW}═══════════════════════════════════════${NC}"
        echo -e "${YELLOW}Docker is not available${NC}"
        echo -e "${YELLOW}Please install Docker Desktop manually${NC}"
        echo -e "${YELLOW}Then run: make docker-up${NC}"
        echo -e "${YELLOW}═══════════════════════════════════════${NC}"
    fi

    # 6. Compile contracts (optional, can be done later)
    # compile_contracts

    echo ""
    echo "========================================="
    echo -e "${GREEN}Setup process complete!${NC}"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your configuration"
    if ! check_docker &> /dev/null; then
        echo "2. Install Docker Desktop"
        echo "3. Run: make docker-up"
        echo "4. Run: make migrate"
    fi
    echo ""
    echo "Common commands:"
    echo "  make help          - Show all available commands"
    echo "  make docker-up     - Start Docker containers"
    echo "  make test          - Run tests"
    echo "  make compile       - Compile smart contracts"
    echo ""
}

# Run main function
main
