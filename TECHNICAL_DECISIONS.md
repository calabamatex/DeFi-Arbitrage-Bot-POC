# Technical Decisions & Architecture Document

**Project:** Flash Loan Arbitrage Bot
**Version:** 2.0
**Date:** 2026-01-19

---

## Table of Contents

1. [Architecture Decisions](#architecture-decisions)
2. [Technology Stack Decisions](#technology-stack-decisions)
3. [Smart Contract Decisions](#smart-contract-decisions)
4. [Database Decisions](#database-decisions)
5. [Infrastructure Decisions](#infrastructure-decisions)
6. [Security Decisions](#security-decisions)
7. [Performance Decisions](#performance-decisions)
8. [Trade-offs & Alternatives Considered](#trade-offs--alternatives-considered)

---

## Architecture Decisions

### AD-001: Microservices vs Monolith

**Decision:** Hybrid approach - Start with modular monolith, evolve to microservices

**Rationale:**
- **Phase 1-3:** Modular monolith
  - Faster initial development
  - Easier debugging and testing
  - Lower operational overhead
  - Clear module boundaries prepare for future split

- **Phase 4+:** Gradual microservices extraction
  - Chain-specific services can scale independently
  - Failure isolation (one chain failure doesn't affect others)
  - Technology diversity (can use Rust for performance-critical parts)

**Implementation:**
```
Modular Monolith Structure:
src/
├── bot/          # Main orchestration
├── chain/        # Multi-chain management (future: separate service)
├── dex/          # DEX adapters (future: per-chain services)
├── flash_loan/   # Flash loan execution
├── simulation/   # Transaction simulation
├── risk/         # Risk management
└── monitoring/   # Metrics and monitoring

Future Microservices:
- Chain Manager Service (manages RPC connections per chain)
- Opportunity Scanner Service (per-chain deployment)
- Execution Engine Service
- Risk Manager Service (centralized)
- Metrics Service (centralized)
```

**Alternatives Considered:**
1. **Pure Monolith** - Rejected: Doesn't scale well for multi-chain
2. **Microservices from start** - Rejected: Too complex for MVP, slower development

---

### AD-002: Event-Driven vs Request-Response

**Decision:** Hybrid - Event-driven for opportunity detection, Request-response for execution

**Rationale:**
- **Event-Driven (Pub/Sub)**:
  - Opportunity Scanner → Message Queue → Execution Engine
  - Decouples detection from execution
  - Natural backpressure handling
  - Easy to add multiple consumers (future: multiple execution strategies)

- **Request-Response**:
  - Flash loan execution needs immediate feedback
  - Risk validation synchronous (must block execution if rejected)
  - Transaction status tracking

**Implementation:**
```python
# Event-driven opportunity flow
opportunity_scanner.detect_opportunity()
  → publish_to_queue(opportunity)
  → execution_engine.consume_from_queue()
  → validate_and_execute()

# Synchronous execution flow
execution_engine.execute_arbitrage(opportunity)
  → risk_manager.validate(opportunity)  # Blocking
  → simulator.simulate(tx)              # Blocking
  → flash_loan_contract.execute()       # Blocking
  → await confirmation                  # Blocking
```

**Message Queue:** Redis Pub/Sub (simple, fast, already using Redis for cache)

**Alternatives Considered:**
1. **Pure Event-Driven** - Rejected: Harder to guarantee execution order, more complex error handling
2. **Pure Request-Response** - Rejected: Tight coupling, harder to scale

---

### AD-003: Database Strategy

**Decision:** PostgreSQL with TimescaleDB for time-series data

**Rationale:**
- **PostgreSQL:**
  - ACID compliance (critical for financial data)
  - Complex queries for analytics
  - JSON support for flexible schema
  - Mature, battle-tested
  - Strong community and tooling

- **TimescaleDB:**
  - Extension of PostgreSQL (no new database to learn)
  - Optimized for time-series (gas prices, metrics)
  - Automatic partitioning and retention policies
  - Continuous aggregates for fast queries
  - Compression for storage efficiency

**Data Organization:**
- **Transactional tables:** opportunities, transactions, trades
- **Time-series tables (hypertables):** gas_prices, metrics, events
- **Configuration tables:** chains, dexes, tokens

**Alternatives Considered:**
1. **MongoDB** - Rejected: Lacks ACID guarantees, harder to join data
2. **InfluxDB** - Rejected: Separate database for time-series, more complexity
3. **DynamoDB** - Rejected: Vendor lock-in, complex for relational queries

---

### AD-004: Caching Strategy

**Decision:** Redis for hot data, in-memory for ultra-hot data

**Rationale:**

**Redis (Distributed Cache):**
- Token prices (TTL: 10 seconds)
- DEX pool addresses (TTL: 1 hour)
- Chain configurations (TTL: 5 minutes)
- RPC provider health (TTL: 30 seconds)

**In-Memory (Per-Process):**
- Smart contract ABIs (never expires)
- Current gas prices (updated every 5 seconds)
- Active opportunities (expires after 2 seconds)

**Cache Invalidation:**
- Time-based expiration (TTL)
- Event-based invalidation (config changes)
- Manual flush for emergencies

**Implementation:**
```python
# Two-tier caching
class CacheManager:
    def __init__(self):
        self.memory_cache = {}  # Local process
        self.redis_client = Redis()  # Distributed

    async def get(self, key: str, tier: str = 'redis'):
        if tier == 'memory':
            return self.memory_cache.get(key)
        else:
            return await self.redis_client.get(key)

    async def get_with_fallback(self, key: str, factory: callable):
        # Try memory cache
        value = self.memory_cache.get(key)
        if value:
            return value

        # Try Redis
        value = await self.redis_client.get(key)
        if value:
            self.memory_cache[key] = value
            return value

        # Fetch from source
        value = await factory()
        await self.redis_client.setex(key, ttl, value)
        self.memory_cache[key] = value
        return value
```

---

## Technology Stack Decisions

### TS-001: Programming Language - Python

**Decision:** Python 3.11+ for backend

**Rationale:**
- **Pros:**
  - Rich Web3 ecosystem (web3.py, eth-account, eth-abi)
  - Fast development (time-to-market critical)
  - Team expertise
  - Excellent async/await support
  - Strong data science libraries (for analytics)

- **Cons:**
  - Slower than compiled languages (acceptable for this use case)
  - GIL limits true parallelism (mitigated with async I/O)

**Performance Optimization:**
- Use async/await for I/O-bound operations (>90% of workload)
- Cython for CPU-intensive calculations if needed
- NumPy/Pandas for data processing
- Consider Rust microservices for ultra-low latency parts (future)

**Alternatives Considered:**
1. **Rust** - Rejected for MVP: Slower development, steeper learning curve
2. **TypeScript/Node.js** - Rejected: Less mature Web3 libraries than Python
3. **Go** - Rejected: Less DeFi ecosystem support

---

### TS-002: Smart Contract Language - Solidity

**Decision:** Solidity 0.8.20+ with OpenZeppelin libraries

**Rationale:**
- **Industry Standard:**
  - Most audited code in Solidity
  - Largest pool of security auditors
  - Best tooling (Hardhat, Foundry)
  - Most examples and documentation

- **OpenZeppelin:**
  - Battle-tested libraries (Ownable, Pausable, ReentrancyGuard)
  - Regular security audits
  - Community trust

**Security Features:**
- Solidity 0.8.x: Built-in overflow/underflow protection
- Custom modifiers for access control
- Comprehensive events for transparency
- Emergency pause mechanism

**Alternatives Considered:**
1. **Vyper** - Rejected: Smaller ecosystem, fewer auditors
2. **Yul** - Rejected: Too low-level, harder to audit

---

### TS-003: Smart Contract Development Framework

**Decision:** Hardhat for development, Foundry for testing

**Rationale:**

**Hardhat:**
- Development environment
- Deployment scripts
- Network management
- Debugger
- Plugin ecosystem

**Foundry:**
- Faster test execution (Rust-based)
- Fuzz testing
- Gas optimization analysis
- Forge for advanced testing
- Better Solidity testing experience (tests in Solidity)

**Workflow:**
```bash
# Development & Deployment
npx hardhat compile
npx hardhat test        # Basic tests
npx hardhat deploy

# Advanced Testing
forge test              # Fast unit tests
forge test --gas-report # Gas optimization
forge test --fuzz-runs 10000  # Fuzzing
```

**Alternatives Considered:**
1. **Truffle** - Rejected: Slower, less actively maintained
2. **Hardhat-only** - Rejected: Tests slower than Foundry
3. **Foundry-only** - Rejected: Deployment less mature than Hardhat

---

### TS-004: Web3 Provider Strategy

**Decision:** Multi-provider failover with Alchemy as primary, public RPCs as backup

**Rationale:**

**Provider Tiers:**
1. **Tier 1 (Premium):** Alchemy, Infura, QuickNode
   - Reliability: 99.9%+
   - Rate limits: High (25-100 req/sec)
   - Cost: $49-499/month
   - Use for: Production trading

2. **Tier 2 (Fast Public):** Ankr, Llamanodes
   - Reliability: 99%+
   - Rate limits: Medium (10-25 req/sec)
   - Cost: Free to low cost
   - Use for: Backup, development

3. **Tier 3 (Fallback):** Public RPCs
   - Reliability: Variable
   - Rate limits: Low (1-10 req/sec)
   - Cost: Free
   - Use for: Emergency fallback only

**Failover Strategy:**
```python
providers = [
    {' name': 'Alchemy', 'priority': 1, 'health_score': 100},
    {'name': 'Ankr', 'priority': 2, 'health_score': 90},
    {'name': 'Public', 'priority': 3, 'health_score': 70}
]

# Try providers in order of (health_score * priority_weight)
for provider in sorted(providers, key=lambda p: p['health_score'] / p['priority']):
    try:
        result = await provider.call()
        return result
    except:
        continue
```

**Cost Analysis:**
- 100K requests/day = ~3M requests/month
- Alchemy Growth plan: $199/month for 3M requests
- Cost per execution: $0.000066 (negligible vs gas costs)

---

## Smart Contract Decisions

### SC-001: Flash Loan Provider Selection

**Decision:** Primary = Aave V3, Fallback = Uniswap V3 Flash Swaps

**Rationale:**

**Aave V3 Advantages:**
- Lowest fees (0.05% = 5 basis points)
- Highest liquidity ($1B+ TVL per asset)
- Available on all target chains
- Mature, audited protocol
- Simple callback pattern

**Uniswap V3 Flash Swaps:**
- 0% fee (only pay swap fee if swapping)
- Good liquidity
- Available on all chains
- More complex callback
- Use when: Token not available on Aave, or pool has better liquidity

**Fee Comparison:**
```
Flash Loan $100,000:
- Aave V3: $50 fee (0.05%)
- Uniswap V3 Flash Swap: $0 fee (but limited to pool liquidity)
- Balancer: $0-10 fee (varies by pool)

Recommendation: Try Uniswap first (if available), fallback to Aave
```

**Implementation:**
```solidity
enum FlashLoanProvider {
    AAVE_V3,
    UNISWAP_V3,
    BALANCER
}

function executeArbitrage(
    FlashLoanProvider provider,
    ...
) external {
    if (provider == FlashLoanProvider.UNISWAP_V3) {
        _executeUniswapFlash(...);
    } else if (provider == FlashLoanProvider.AAVE_V3) {
        _executeAaveFlash(...);
    }
}
```

**Alternatives Considered:**
1. **dYdX** - Rejected: Only on Ethereum mainnet, discontinuing flash loans
2. **Balancer** - Considered for future: Variable fees, not all chains

---

### SC-002: Upgradability Pattern

**Decision:** UUPS (Universal Upgradeable Proxy Standard) proxy pattern

**Rationale:**

**UUPS Advantages:**
- Upgrade logic in implementation (gas efficient)
- Cheaper deployments than Transparent Proxy
- Modern standard (vs older patterns)
- Compatible with OpenZeppelin

**Safety Measures:**
- 48-hour timelock on upgrades
- Multi-sig requirement (3-of-5) for upgrade proposals
- Testnet deployment required before mainnet upgrade
- Emergency pause doesn't require upgrade

**Implementation:**
```solidity
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract FlashLoanArbitrage is UUPSUpgradeable, OwnableUpgradeable {

    function initialize(address _aavePool) public initializer {
        __Ownable_init();
        __UUPSUpgradeable_init();
        // initialization logic
    }

    function _authorizeUpgrade(address newImplementation)
        internal
        override
        onlyOwner
    {
        // Additional checks can be added here
        // Could require timelock or multi-sig
    }
}
```

**Alternatives Considered:**
1. **Transparent Proxy** - Rejected: Higher gas costs, upgrade logic in proxy
2. **Beacon Proxy** - Rejected: Overkill for single contract, more complex
3. **No Upgradability** - Rejected: Too risky for financial contract

---

### SC-003: On-Chain vs Off-Chain Validation

**Decision:** Hybrid - Critical validations on-chain, complex logic off-chain

**On-Chain Validations:**
- Profitability check (must profit after flash loan repayment)
- Slippage limits (amountOutMinimum)
- Reentrancy protection
- Access control (only owner can execute)
- Emergency pause state

**Off-Chain Validations:**
- Opportunity detection
- Chain selection
- Gas cost estimation
- Risk management rules
- Transaction simulation

**Rationale:**
- On-chain validation = trustless, but costs gas
- Off-chain validation = flexible, free, but requires trust in bot
- Hybrid approach balances security and cost

**Critical Invariant (On-Chain):**
```solidity
function executeOperation(...) external returns (bool) {
    uint256 amountOwed = amount + premium;
    uint256 finalBalance = IERC20(asset).balanceOf(address(this));

    // CRITICAL: Must have enough to repay + minimum profit
    uint256 minProfit = (amount * minProfitBps) / 10000;
    require(
        finalBalance >= initialBalance + amountOwed + minProfit,
        "Insufficient profit"
    );

    return true;
}
```

---

## Database Decisions

### DB-001: Schema Design Philosophy

**Decision:** Normalized schema with selective denormalization for performance

**Rationale:**

**Normalized:**
- Reduce data redundancy
- Easier to maintain consistency
- Clearer data model

**Selective Denormalization:**
- Store calculated fields for fast queries (e.g., net_profit_usd)
- Duplicate frequently accessed data to avoid joins
- Pre-aggregate time-series data

**Example:**
```sql
-- Normalized: Separate tables
CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    chain_id INT REFERENCES chains(id),
    token_in_id INT REFERENCES tokens(id),
    token_out_id INT REFERENCES tokens(id),
    -- other fields
);

-- Denormalized: Store token symbols directly for queries
CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    chain_id INT,
    chain_name TEXT,  -- Denormalized
    token_in TEXT,    -- Denormalized (address + symbol)
    token_out TEXT,   -- Denormalized
    token_in_symbol TEXT,  -- For display
    token_out_symbol TEXT, -- For display
    gross_profit_usd NUMERIC(12,2),  -- Calculated & stored
    net_profit_usd NUMERIC(12,2),    -- Calculated & stored
    -- other fields
);
```

**Trade-offs:**
- More storage, faster queries
- Denormalized fields updated on write
- Acceptable for append-mostly workload

---

### DB-002: Partitioning Strategy

**Decision:** Time-based partitioning for large tables using TimescaleDB hypertables

**Implementation:**
```sql
-- Convert to hypertable (auto-partitioning)
SELECT create_hypertable(
    'gas_price_history',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day'
);

SELECT create_hypertable(
    'price_snapshots',
    'timestamp',
    chunk_time_interval => INTERVAL '1 hour'
);

-- Retention policy (auto-delete old data)
SELECT add_retention_policy(
    'gas_price_history',
    INTERVAL '30 days'
);

-- Continuous aggregates (pre-computed views)
CREATE MATERIALIZED VIEW gas_price_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS hour,
    chain_id,
    AVG(gas_price_gwei) AS avg_gas_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gas_price_gwei) AS median_gas_price,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gas_price_gwei) AS p95_gas_price
FROM gas_price_history
GROUP BY hour, chain_id;
```

**Benefits:**
- Fast queries on recent data
- Automatic compression of old data
- Automatic retention management
- Pre-aggregated views for dashboards

---

## Infrastructure Decisions

### INFRA-001: Cloud Provider

**Decision:** Multi-cloud with primary on AWS

**Rationale:**

**AWS Primary:**
- Most mature DeFi infrastructure
- Best RPC provider integrations
- Strong PostgreSQL support (RDS)
- Extensive monitoring tools (CloudWatch)
- Cost-effective for compute (EC2, Fargate)

**Multi-Cloud Strategy:**
```
Production:
- AWS (Primary): Main bot, database, monitoring
- Vercel/Railway (Secondary): Dashboards, APIs

Development:
- Local: Docker Compose
- AWS: Staging environment

Disaster Recovery:
- GCP/Azure: Standby infrastructure (manual activation)
```

**Cost Estimates (Monthly):**
```
AWS Production:
- EC2 instances (2x t3.medium): $60
- RDS PostgreSQL (db.t3.small): $30
- ElastiCache Redis: $15
- Data transfer: $20
- CloudWatch: $10
Total: ~$135/month

+ Transaction gas costs: Variable ($500-5000/month)
```

**Alternatives Considered:**
1. **GCP** - Rejected: Less DeFi-friendly, higher costs
2. **Azure** - Rejected: Smallest Web3 ecosystem
3. **Dedicated Servers** - Rejected: Less flexibility, more maintenance

---

### INFRA-002: Container Strategy

**Decision:** Docker containers orchestrated with Docker Compose (MVP) → Kubernetes (scale)

**MVP (Docker Compose):**
```yaml
version: '3.8'
services:
  bot:
    build: .
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  postgres:
    image: timescale/timescaledb:latest-pg15
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
```

**Future (Kubernetes):**
- Auto-scaling based on opportunity volume
- Rolling deployments (zero downtime)
- Resource limits per service
- Better multi-chain isolation

**Why Docker Compose First:**
- Simpler operations
- Faster iteration
- Lower learning curve
- Sufficient for initial scale

**When to Migrate to K8s:**
- Need auto-scaling (>10 req/sec sustained)
- Multiple environments (dev, staging, prod)
- Team size >3 engineers
- Multi-region deployment

---

## Security Decisions

### SEC-001: Private Key Management

**Decision:** AWS KMS for production, encrypted files for development

**Production:**
```python
import boto3

class KMSKeySigner:
    def __init__(self, key_id: str):
        self.kms = boto3.client('kms')
        self.key_id = key_id

    async def sign_transaction(self, tx_hash: bytes) -> bytes:
        response = await self.kms.sign(
            KeyId=self.key_id,
            Message=tx_hash,
            MessageType='DIGEST',
            SigningAlgorithm='ECDSA_SHA_256'
        )
        return response['Signature']
```

**Development:**
```python
# Encrypted with project-specific passphrase
from eth_account import Account

with open('.keys/dev.json.enc') as f:
    encrypted = f.read()

private_key = decrypt_keyfile(encrypted, passphrase)
account = Account.from_key(private_key)
```

**Key Rotation:**
- Quarterly rotation schedule
- Separate keys per chain
- Multi-sig for large value operations
- Emergency rotation procedure

**Alternatives Considered:**
1. **Hardware Wallets (Ledger)** - Rejected: Latency too high for automated trading
2. **Environment Variables** - Rejected: Too easy to leak
3. **HashiCorp Vault** - Considered for future: More complex to operate

---

### SEC-002: API Security

**Decision:** JWT-based authentication with rate limiting

**Implementation:**
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/api/opportunities")
@limiter.limit("100/minute")
async def get_opportunities(user = Depends(verify_token)):
    # Only authenticated users can access
    return opportunities
```

**Security Layers:**
1. Network: VPC, security groups, no public DB access
2. Application: JWT auth, rate limiting, input validation
3. Database: Parameterized queries, least privilege principle
4. Secrets: KMS, encrypted environment variables

---

## Performance Decisions

### PERF-001: Optimization Strategy

**Decision:** Optimize for latency first, throughput second

**Latency Optimizations:**
1. **Async I/O** - Non-blocking RPC calls, database queries
2. **Caching** - Hot data in Redis, ultra-hot in memory
3. **Connection Pooling** - Reuse DB and RPC connections
4. **Parallel Execution** - Concurrent price fetching across DEXes

5. **Smart Batching** - Group RPC calls where possible

**Latency Budget:**
```
Total: 2000ms
├─ Opportunity Detection: 500ms
│  ├─ Price Fetch (parallel): 300ms
│  └─ Calculation: 200ms
├─ Validation: 300ms
├─ Simulation: 500ms
├─ Execution: 500ms
└─ Buffer: 200ms
```

**Throughput Optimizations:**
- Horizontal scaling (multiple opportunity scanners)
- Database read replicas
- Message queue for decoupling
- Metrics sampling (not every event)

**Monitoring:**
```python
import time
from functools import wraps

def measure_latency(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        latency_ms = (time.time() - start) * 1000

        metrics.record_histogram(
            f"{func.__name__}_latency_ms",
            latency_ms,
            tags={"function": func.__name__}
        )

        return result
    return wrapper

@measure_latency
async def fetch_prices():
    ...
```

---

### PERF-002: Database Query Optimization

**Decision:** Optimize for read-heavy workload with strategic indexes

**Indexing Strategy:**
```sql
-- Opportunities table
CREATE INDEX idx_opportunities_timestamp ON opportunities(created_at DESC);
CREATE INDEX idx_opportunities_chain ON opportunities(chain_id, created_at DESC);
CREATE INDEX idx_opportunities_status ON opportunities(status) WHERE status = 'pending';

-- Composite index for common queries
CREATE INDEX idx_opportunities_chain_status_time
ON opportunities(chain_id, status, created_at DESC);

-- Partial index for active opportunities only
CREATE INDEX idx_active_opportunities
ON opportunities(chain_id, created_at DESC)
WHERE status IN ('pending', 'executing');

-- Transactions table
CREATE INDEX idx_transactions_hash ON transactions(tx_hash);
CREATE INDEX idx_transactions_opportunity ON transactions(opportunity_id);
```

**Query Patterns:**
```sql
-- Optimized: Uses idx_opportunities_chain_status_time
SELECT * FROM opportunities
WHERE chain_id = 137
  AND status = 'completed'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 100;

-- Optimized: Uses partial index
SELECT * FROM opportunities
WHERE status = 'pending'
  AND chain_id = 137
ORDER BY created_at DESC;
```

**Connection Pooling:**
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,        # Normal connections
    max_overflow=20,     # Burst capacity
    pool_pre_ping=True,  # Verify connection before use
    pool_recycle=3600    # Recycle connections every hour
)
```

---

## Trade-offs & Alternatives Considered

### Summary Table

| Decision | Choice | Alternative | Rationale |
|----------|--------|-------------|-----------|
| **Architecture** | Modular Monolith → Microservices | Pure Microservices | Faster MVP, easier debugging |
| **Language** | Python | Rust | Development speed > performance for MVP |
| **Database** | PostgreSQL + TimescaleDB | MongoDB | ACID guarantees critical |
| **Flash Loans** | Aave V3 | dYdX | Aave available on all chains |
| **Simulation** | Tenderly | Foundry Anvil | Hosted service, less maintenance |
| **Proxy Pattern** | UUPS | Transparent | Lower gas costs |
| **Cloud** | AWS | GCP | Better DeFi ecosystem |
| **Container Orchestration** | Docker Compose → K8s | K8s from start | Simpler operations initially |
| **Key Management** | AWS KMS | Hardware Wallet | Automation vs security trade-off |
| **Testing** | Hardhat + Foundry | Hardhat only | Best of both tools |

---

## Next Steps from SDLC Perspective

Based on this technical foundation, the **optimal next step** is:

### **Step 1: Development Environment Setup** ✅
- Set up GitHub repository with proper .gitignore
- Configure development tools (Hardhat, Foundry, Python virtual env)
- Set up Docker Compose for local development
- Create CI/CD pipeline skeleton

### **Step 2: Smart Contract Development** (Critical Path)
- Implement FlashLoanArbitrage.sol
- Write comprehensive test suite (Foundry + Hardhat)
- Deploy to testnets (Mumbai, Goerli, etc.)
- Begin security audit preparation

### **Step 3: Core Backend Development** (Parallel to Step 2)
- Fix existing bugs in codebase
- Implement chain abstraction layer
- Build RPC management system
- Create database schema and migrations

### **Step 4: Integration** (After Steps 2 & 3)
- Connect Python backend to smart contracts
- End-to-end testing on testnets
- Performance testing and optimization
- Security review

### **Step 5: Deployment** (Final)
- Mainnet smart contract deployment
- Infrastructure provisioning (AWS)
- Monitoring setup (Grafana, alerts)
- Gradual rollout with increasing limits

---

**Document Status:** Complete
**Last Updated:** 2026-01-19
**Next Review:** After Phase 1 completion
