# Flash Loan Arbitrage Bot - Development Setup

## Quick Start Guide

This guide will help you set up your development environment for the Flash Loan Arbitrage Bot project.

## Prerequisites

- Python 3.11+ (Installed: ✅ Python 3.14.2)
- Node.js 18+ (Installed: ✅ v22.14.0)
- Docker Desktop (Pending installation)
- Foundry (Installed: ✅ v1.5.1-stable)
- Homebrew (macOS)

## Installation Status

### ✅ Completed
- [x] Git repository initialized
- [x] Python virtual environment created
- [x] Python dependencies installed (web3, pytest, sqlalchemy, etc.)
- [x] Hardhat installed and configured
- [x] Foundry installed (forge, cast, anvil, chisel)
- [x] Project directory structure created
- [x] Configuration files created

### ⏳ Pending
- [ ] Docker Desktop installation (manual step required)
- [ ] Docker containers started
- [ ] Database migrations run
- [ ] Smart contracts written

## Project Structure

```
ARBITRAGE/
├── contracts/              # Solidity smart contracts
│   └── FlashLoanArbitrage.sol (to be created)
├── src/                   # Python source code
│   ├── bot/              # Core arbitrage logic
│   ├── dex/              # DEX adapters
│   ├── flash_loan/       # Flash loan integration
│   ├── chain/            # Multi-chain management
│   ├── utils/            # Utility functions
│   ├── db/               # Database models
│   ├── monitoring/       # Monitoring & alerts
│   └── api/              # REST API
├── test/                  # Test files
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── e2e/              # End-to-end tests
│   └── contracts/        # Smart contract tests
├── scripts/              # Deployment & utility scripts
├── alembic/              # Database migrations
├── docs/                 # Documentation
├── config/               # Configuration files
├── .venv/                # Python virtual environment
└── node_modules/         # Node.js dependencies
```

## Step-by-Step Setup

### 1. Activate Python Virtual Environment

```bash
source .venv/bin/activate
```

### 2. Install Docker Desktop (REQUIRED)

Docker Desktop needs to be installed manually due to permission requirements:

**Option A: Use Homebrew (requires password)**
```bash
brew install --cask docker
```

Then open Docker Desktop from Applications and start it.

**Option B: Manual Download**
1. Visit: https://www.docker.com/products/docker-desktop
2. Download Docker Desktop for Mac (Apple Silicon)
3. Install and start Docker Desktop

### 3. Verify Docker Installation

```bash
docker --version
docker-compose --version
```

### 4. Start Docker Containers

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Check container status
docker-compose ps

# View logs
docker-compose logs -f
```

### 5. Setup Database

```bash
# Initialize Alembic (database migrations)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Run migrations
alembic upgrade head

# Verify database connection
docker exec -it arbitrage_postgres psql -U postgres -d arbitrage_bot -c "SELECT version();"
```

### 6. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your configuration
# IMPORTANT: Never commit .env to git!
nano .env
```

Required configuration:
- `PRIVATE_KEY`: Your wallet private key (for testnet)
- RPC URLs for each chain
- API keys for block explorers (for contract verification)

### 7. Compile Smart Contracts

```bash
# Using Hardhat
npx hardhat compile

# Using Foundry
forge build
```

### 8. Run Tests

```bash
# Python tests
pytest -v

# Smart contract tests (Foundry)
forge test -vvv

# Or use Makefile
make test
make test-contracts
```

## Common Development Commands

```bash
# Start development
source .venv/bin/activate        # Always activate venv first

# Docker management
make docker-up                   # Start containers
make docker-down                 # Stop containers
make docker-logs                 # View logs

# Database
make migrate                     # Run migrations
make migration                   # Create new migration
make db-reset                    # Reset database (WARNING!)

# Code quality
make format                      # Format code (black, isort)
make lint                        # Run linters (flake8, mypy)
make test                        # Run all Python tests

# Smart contracts
make compile                     # Compile with Hardhat
make compile-foundry            # Compile with Foundry
make test-contracts             # Test contracts
make deploy-testnet             # Deploy to testnet

# Cleanup
make clean                       # Remove build artifacts
```

## Development Workflow

1. **Start your day:**
   ```bash
   source .venv/bin/activate
   make docker-up
   git pull origin main
   ```

2. **Write code:**
   - Write smart contracts in `contracts/`
   - Write Python code in `src/`
   - Write tests in `test/`

3. **Before committing:**
   ```bash
   make format                  # Format code
   make lint                    # Check for issues
   make test                    # Run tests
   make test-contracts         # Test smart contracts
   ```

4. **Commit changes:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin your-branch
   ```

## Accessing Tools

- **PgAdmin** (Database UI): http://localhost:5050
  - Email: admin@arbitrage.local
  - Password: admin

- **Redis Commander** (Redis UI): http://localhost:8081
  ```bash
  docker-compose --profile tools up -d
  ```

## Troubleshooting

### Docker not starting
```bash
# Check if Docker Desktop is running
docker info

# Restart Docker containers
make docker-down
make docker-up
```

### Database connection issues
```bash
# Check if PostgreSQL is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Reset database
make db-reset
```

### Python dependencies issues
```bash
# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Hardhat compilation errors
```bash
# Clear cache
npx hardhat clean

# Reinstall dependencies
rm -rf node_modules
npm install
```

## Next Steps

Once your environment is set up:

1. **Read the documentation:**
   - REQUIREMENTS.md - Project requirements
   - IMPLEMENTATION_PLAN.md - Development roadmap
   - TECHNICAL_DECISIONS.md - Architecture decisions
   - DATABASE_SCHEMA.md - Database design

2. **Start developing:**
   - Phase 1: Smart contract development (Flash loans)
   - Phase 2: Multi-chain infrastructure
   - Phase 3: Advanced features
   - See IMPLEMENTATION_PLAN.md for details

3. **Join discussions:**
   - Create issues for bugs
   - Open PRs for features
   - Document your code

## Resources

- [Hardhat Documentation](https://hardhat.org/docs)
- [Foundry Book](https://book.getfoundry.sh/)
- [Aave V3 Flash Loans](https://docs.aave.com/developers/guides/flash-loans)
- [Web3.py Documentation](https://web3py.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Support

For questions or issues:
1. Check this README
2. Review project documentation
3. Search existing issues
4. Create a new issue with details

---

**Last Updated:** 2026-01-20
**Status:** Development Environment Setup Phase
