# Flash Loan Arbitrage Bot - Detailed Implementation Plan

**Project:** Advanced Multi-Chain Arbitrage Trading Bot
**Version:** 2.0
**Date:** 2026-01-19
**Status:** Implementation Planning Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Implementation Phases](#implementation-phases)
3. [Phase 1: Foundation & Flash Loan Integration](#phase-1-foundation--flash-loan-integration)
4. [Phase 2: Multi-Chain Infrastructure](#phase-2-multi-chain-infrastructure)
5. [Phase 3: Advanced Features & Optimization](#phase-3-advanced-features--optimization)
6. [Phase 4: Testing & Security](#phase-4-testing--security)
7. [Phase 5: Deployment & Monitoring](#phase-5-deployment--monitoring)
8. [Phase 6: Production Optimization](#phase-6-production-optimization)
9. [Critical Path Analysis](#critical-path-analysis)
10. [Resource Requirements](#resource-requirements)
11. [Risk Mitigation Strategies](#risk-mitigation-strategies)
12. [Success Criteria](#success-criteria)

---

## Executive Summary

### Approach
Implement the flash loan arbitrage bot using an iterative, phased approach that prioritizes:
1. **Core functionality first** - Flash loan integration on single chain
2. **Validation at each step** - Testnet validation before mainnet
3. **Incremental complexity** - Add chains/features progressively
4. **Security throughout** - Security reviews at each phase
5. **Continuous testing** - Automated testing from day 1

### Implementation Strategy
- **6-phase waterfall with iterative sub-phases**
- **Each phase has clear deliverables and acceptance criteria**
- **Security gates between phases (cannot proceed without passing)**
- **Testnet validation before mainnet deployment**
- **Gradual scaling (small amounts → full production)**

### Key Milestones
1. **Phase 1 Complete:** Flash loan working on Polygon testnet
2. **Phase 2 Complete:** Multi-chain support (3+ chains)
3. **Phase 3 Complete:** Advanced optimization and MEV protection
4. **Phase 4 Complete:** Security audit passed, all tests green
5. **Phase 5 Complete:** Production deployment with monitoring
6. **Phase 6 Complete:** Full-scale operation with optimization

---

## Implementation Phases

### Phase Overview

```
Phase 1: Foundation & Flash Loan Integration (6-8 weeks)
├─ Smart contract development
├─ Flash loan provider integration
├─ Fix existing codebase bugs
└─ Basic testnet deployment

Phase 2: Multi-Chain Infrastructure (4-6 weeks)
├─ Chain abstraction layer
├─ Multi-chain RPC management
├─ Chain cost profiling
└─ Chain selection algorithm

Phase 3: Advanced Features & Optimization (4-5 weeks)
├─ Transaction simulation (Tenderly)
├─ MEV protection
├─ Advanced opportunity scoring
└─ DEX adapter expansion

Phase 4: Testing & Security (4-6 weeks)
├─ Comprehensive test suite
├─ Security audit
├─ Load testing
└─ Bug fixes

Phase 5: Deployment & Monitoring (3-4 weeks)
├─ Infrastructure setup
├─ CI/CD pipeline
├─ Monitoring stack
└─ Gradual mainnet rollout

Phase 6: Production Optimization (Ongoing)
├─ Performance tuning
├─ Feature enhancements
├─ Scaling
└─ Maintenance

Total Timeline: 21-29 weeks (5-7 months)
```

---

## Phase 1: Foundation & Flash Loan Integration

**Duration:** 6-8 weeks
**Priority:** P0 (Critical Path)
**Goal:** Get basic flash loan arbitrage working on Polygon testnet

### Sub-Phases

#### 1.1: Codebase Audit & Bug Fixes (Week 1-2)

**Objective:** Fix critical bugs in existing codebase and establish solid foundation

**Tasks:**
1. **Fix Profit Calculation Bug**
   - File: `src/bot/arbitrage.py`
   - Issue: Dimensional mismatch in USD conversion
   - Fix: Proper token-to-USD conversion

```python
# BEFORE (Buggy)
gross_profit_usd = opportunity.expected_profit * opportunity.amount

# AFTER (Fixed)
def calculate_profit_usd(opportunity: ArbitrageOpportunity) -> float:
    """Calculate profit in USD with proper conversions"""

    # Get token prices in USD
    token_price_usd = get_token_price_usd(opportunity.token_out)

    # Calculate token profit
    token_profit = (opportunity.sell_price - opportunity.buy_price) * opportunity.amount

    # Convert to USD
    profit_usd = token_profit * token_price_usd

    return profit_usd
```

2. **Implement Slippage Protection**
   - File: `src/utils/slippage_protection.py`
   - Add enforcement of slippage limits in actual trades

```python
def calculate_min_amount_out(
    expected_amount: int,
    slippage_tolerance: float = 0.005  # 0.5%
) -> int:
    """Calculate minimum acceptable output amount"""
    min_amount = int(expected_amount * (1 - slippage_tolerance))
    return min_amount

async def execute_swap_with_slippage_protection(
    dex: DEXAdapter,
    token_in: str,
    token_out: str,
    amount_in: int,
    expected_amount_out: int,
    slippage_tolerance: float = 0.005
) -> SwapResult:
    """Execute swap with slippage protection"""

    min_amount_out = calculate_min_amount_out(
        expected_amount_out,
        slippage_tolerance
    )

    # Pass min_amount_out to DEX swap function
    result = await dex.swap(
        token_in=token_in,
        token_out=token_out,
        amount_in=amount_in,
        amount_out_minimum=min_amount_out,  # Reverts if less than this
        recipient=bot_address,
        deadline=int(time.time()) + 300  # 5 min deadline
    )

    return result
```

3. **Fix Nonce Management**
   - File: `src/utils/transaction_manager.py`
   - Implement proper transaction queue with nonce tracking

```python
class NonceManager:
    """Thread-safe nonce management for transaction ordering"""

    def __init__(self, w3: Web3, account: str):
        self.w3 = w3
        self.account = checksum_address(account)
        self._lock = asyncio.Lock()
        self._pending_nonces = {}  # nonce -> tx_hash
        self._current_nonce = None

    async def get_next_nonce(self) -> int:
        """Get next available nonce (thread-safe)"""
        async with self._lock:
            if self._current_nonce is None:
                # Initialize from blockchain
                self._current_nonce = await self.w3.eth.get_transaction_count(
                    self.account,
                    'pending'  # Include pending transactions
                )

            nonce = self._current_nonce
            self._current_nonce += 1
            return nonce

    async def mark_nonce_used(self, nonce: int, tx_hash: str):
        """Mark nonce as used"""
        async with self._lock:
            self._pending_nonces[nonce] = tx_hash

    async def release_nonce(self, nonce: int):
        """Release nonce if transaction failed"""
        async with self._lock:
            if nonce in self._pending_nonces:
                del self._pending_nonces[nonce]
            # Reset current nonce to failed nonce for retry
            if nonce < self._current_nonce:
                self._current_nonce = nonce
```

4. **Implement Persistent State Storage**
   - Replace in-memory state with database
   - Add PostgreSQL models for opportunities, transactions, metrics

**Acceptance Criteria:**
- [ ] All unit tests passing
- [ ] Profit calculation verified against manual calculations
- [ ] Slippage protection tested with various scenarios
- [ ] Nonce manager handles concurrent transactions
- [ ] Database schema created and migrations working

---

#### 1.2: Smart Contract Development (Week 2-4)

**Objective:** Develop, test, and deploy flash loan arbitrage smart contract

**Tasks:**

1. **Contract Architecture Design**

```
FlashLoanArbitrage.sol (Main Contract)
├─ IFlashLoanReceiver (Aave interface)
├─ IUniswapV3FlashCallback (Uniswap interface)
├─ Ownable (Access control)
├─ Pausable (Emergency stop)
└─ ReentrancyGuard (Security)

Libraries:
├─ SafeERC20.sol (Safe token operations)
├─ DEXLibrary.sol (DEX interaction helpers)
└─ ProfitCalculator.sol (On-chain profit validation)
```

2. **Main Contract Implementation**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@aave/core-v3/contracts/flashloan/interfaces/IFlashLoanReceiver.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title FlashLoanArbitrage
 * @notice Executes arbitrage using Aave V3 flash loans
 * @dev Only owner can execute arbitrage, includes emergency pause
 */
contract FlashLoanArbitrage is
    IFlashLoanReceiver,
    Ownable,
    Pausable,
    ReentrancyGuard
{
    using SafeERC20 for IERC20;

    // Aave V3 Pool address
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    IPool public immutable POOL;

    // Minimum profit required (in basis points, 10 = 0.1%)
    uint256 public minProfitBps = 10;

    // Events
    event ArbitrageExecuted(
        address indexed token,
        uint256 amount,
        uint256 profit,
        uint256 timestamp
    );

    event ProfitWithdrawn(
        address indexed token,
        uint256 amount,
        address indexed recipient
    );

    event MinProfitUpdated(uint256 oldValue, uint256 newValue);

    /**
     * @notice Constructor
     * @param _addressProvider Aave V3 PoolAddressesProvider
     */
    constructor(address _addressProvider) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressProvider);
        POOL = IPool(ADDRESSES_PROVIDER.getPool());
    }

    /**
     * @notice Execute flash loan arbitrage
     * @param token Token to borrow
     * @param amount Amount to borrow
     * @param buyDex DEX to buy from (lower price)
     * @param sellDex DEX to sell to (higher price)
     * @param buyCalldata Calldata for buy swap
     * @param sellCalldata Calldata for sell swap
     */
    function executeArbitrage(
        address token,
        uint256 amount,
        address buyDex,
        address sellDex,
        bytes calldata buyCalldata,
        bytes calldata sellCalldata
    )
        external
        onlyOwner
        whenNotPaused
        nonReentrant
    {
        // Validate inputs
        require(token != address(0), "Invalid token");
        require(amount > 0, "Invalid amount");
        require(buyDex != address(0) && sellDex != address(0), "Invalid DEX");

        // Prepare flash loan parameters
        address[] memory assets = new address[](1);
        assets[0] = token;

        uint256[] memory amounts = new uint256[](1);
        amounts[0] = amount;

        uint256[] memory modes = new uint256[](1);
        modes[0] = 0; // 0 = no debt, pay back immediately

        // Encode arbitrage parameters
        bytes memory params = abi.encode(
            token,
            buyDex,
            sellDex,
            buyCalldata,
            sellCalldata
        );

        // Execute flash loan
        POOL.flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            params,
            0 // referralCode
        );
    }

    /**
     * @notice Aave flash loan callback
     * @dev This is called by Aave Pool after sending borrowed funds
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    )
        external
        override
        returns (bool)
    {
        // Verify caller is Aave Pool
        require(msg.sender == address(POOL), "Caller must be POOL");
        require(initiator == address(this), "Initiator must be this contract");

        // Decode parameters
        (
            address token,
            address buyDex,
            address sellDex,
            bytes memory buyCalldata,
            bytes memory sellCalldata
        ) = abi.decode(params, (address, address, address, bytes, bytes));

        uint256 borrowedAmount = amounts[0];
        uint256 premium = premiums[0];
        uint256 amountOwed = borrowedAmount + premium;

        // Record initial balance
        uint256 balanceBefore = IERC20(token).balanceOf(address(this));

        // Step 1: Approve buyDex to spend borrowed tokens
        IERC20(token).safeApprove(buyDex, borrowedAmount);

        // Step 2: Execute buy on DEX 1 (buy intermediate token)
        (bool buySuccess, bytes memory buyResult) = buyDex.call(buyCalldata);
        require(buySuccess, "Buy swap failed");

        // Extract intermediate token and amount from buy result
        (address intermediateToken, uint256 receivedAmount) =
            abi.decode(buyResult, (address, uint256));

        // Step 3: Approve sellDex to spend intermediate token
        IERC20(intermediateToken).safeApprove(sellDex, receivedAmount);

        // Step 4: Execute sell on DEX 2 (sell back to original token)
        (bool sellSuccess, ) = sellDex.call(sellCalldata);
        require(sellSuccess, "Sell swap failed");

        // Step 5: Verify profitability
        uint256 balanceAfter = IERC20(token).balanceOf(address(this));
        require(balanceAfter >= balanceBefore + amountOwed, "Insufficient profit");

        uint256 profit = balanceAfter - balanceBefore - amountOwed;

        // Verify minimum profit (as percentage of borrowed amount)
        uint256 minProfit = (borrowedAmount * minProfitBps) / 10000;
        require(profit >= minProfit, "Profit below minimum");

        // Step 6: Approve Pool to pull repayment
        IERC20(token).safeApprove(address(POOL), amountOwed);

        // Emit event
        emit ArbitrageExecuted(token, borrowedAmount, profit, block.timestamp);

        return true;
    }

    /**
     * @notice Withdraw profits to owner
     * @param token Token to withdraw
     */
    function withdrawProfit(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No profit to withdraw");

        IERC20(token).safeTransfer(owner(), balance);

        emit ProfitWithdrawn(token, balance, owner());
    }

    /**
     * @notice Emergency withdraw (if tokens stuck)
     * @param token Token to withdraw
     */
    function emergencyWithdraw(address token) external onlyOwner whenPaused {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).safeTransfer(owner(), balance);
        }
    }

    /**
     * @notice Update minimum profit requirement
     * @param _minProfitBps New minimum in basis points
     */
    function setMinProfit(uint256 _minProfitBps) external onlyOwner {
        uint256 oldValue = minProfitBps;
        minProfitBps = _minProfitBps;
        emit MinProfitUpdated(oldValue, _minProfitBps);
    }

    /**
     * @notice Pause contract (emergency)
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Unpause contract
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Get Pool address
     */
    function getPool() external view returns (address) {
        return address(POOL);
    }

    // Receive ETH
    receive() external payable {}
}
```

3. **DEX Interaction Library**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

library DEXLibrary {
    /**
     * @notice Build Uniswap V3 exact input swap calldata
     */
    function buildUniswapV3Swap(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMinimum,
        address recipient
    ) internal pure returns (bytes memory) {
        ISwapRouter.ExactInputSingleParams memory params =
            ISwapRouter.ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: fee,
                recipient: recipient,
                deadline: block.timestamp,
                amountIn: amountIn,
                amountOutMinimum: amountOutMinimum,
                sqrtPriceLimitX96: 0
            });

        return abi.encodeWithSelector(
            ISwapRouter.exactInputSingle.selector,
            params
        );
    }

    /**
     * @notice Build SushiSwap V2 swap calldata
     */
    function buildSushiSwapV2Swap(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] memory path,
        address to,
        uint256 deadline
    ) internal pure returns (bytes memory) {
        return abi.encodeWithSelector(
            IUniswapV2Router.swapExactTokensForTokens.selector,
            amountIn,
            amountOutMin,
            path,
            to,
            deadline
        );
    }
}
```

4. **Comprehensive Testing Suite**

```javascript
// test/FlashLoanArbitrage.test.js
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("FlashLoanArbitrage", function () {
    let flashLoanArbitrage;
    let owner, addr1;
    let aavePool, addressProvider;
    let weth, usdc;

    beforeEach(async function () {
        [owner, addr1] = await ethers.getSigners();

        // Deploy mock contracts
        const MockAddressProvider = await ethers.getContractFactory("MockPoolAddressesProvider");
        addressProvider = await MockAddressProvider.deploy();

        const MockPool = await ethers.getContractFactory("MockPool");
        aavePool = await MockPool.deploy();
        await addressProvider.setPool(aavePool.address);

        // Deploy FlashLoanArbitrage
        const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
        flashLoanArbitrage = await FlashLoanArbitrage.deploy(addressProvider.address);

        // Deploy mock tokens
        const MockERC20 = await ethers.getContractFactory("MockERC20");
        weth = await MockERC20.deploy("WETH", "WETH", 18);
        usdc = await MockERC20.deploy("USDC", "USDC", 6);
    });

    describe("Deployment", function () {
        it("Should set the right owner", async function () {
            expect(await flashLoanArbitrage.owner()).to.equal(owner.address);
        });

        it("Should set the correct Pool address", async function () {
            expect(await flashLoanArbitrage.getPool()).to.equal(aavePool.address);
        });
    });

    describe("Flash Loan Arbitrage", function () {
        it("Should execute profitable arbitrage", async function () {
            // Setup mock DEXes with price discrepancy
            // ... test implementation
        });

        it("Should revert if arbitrage is not profitable", async function () {
            // ... test implementation
        });

        it("Should revert if called by non-owner", async function () {
            await expect(
                flashLoanArbitrage.connect(addr1).executeArbitrage(
                    weth.address,
                    ethers.utils.parseEther("1"),
                    ethers.constants.AddressZero,
                    ethers.constants.AddressZero,
                    "0x",
                    "0x"
                )
            ).to.be.revertedWith("Ownable: caller is not the owner");
        });
    });

    describe("Emergency Functions", function () {
        it("Should allow owner to pause", async function () {
            await flashLoanArbitrage.pause();
            expect(await flashLoanArbitrage.paused()).to.equal(true);
        });

        it("Should prevent execution when paused", async function () {
            await flashLoanArbitrage.pause();
            await expect(
                flashLoanArbitrage.executeArbitrage(
                    weth.address,
                    ethers.utils.parseEther("1"),
                    ethers.constants.AddressZero,
                    ethers.constants.AddressZero,
                    "0x",
                    "0x"
                )
            ).to.be.revertedWith("Pausable: paused");
        });
    });
});
```

**Deliverables:**
- [ ] Smart contract code in `/contracts`
- [ ] Deployment scripts in `/scripts`
- [ ] Comprehensive test suite (>95% coverage)
- [ ] Gas optimization report
- [ ] Contract documentation

**Acceptance Criteria:**
- [ ] All tests passing on Hardhat local network
- [ ] Gas usage < 500K per arbitrage execution
- [ ] Reentrancy protection verified
- [ ] Emergency pause mechanism tested
- [ ] Ownership transfer tested

---

#### 1.3: Flash Loan Provider Integration (Week 4-5)

**Objective:** Integrate Python backend with smart contract for flash loan execution

**Tasks:**

1. **Web3 Contract Interface**

```python
# src/flash_loan/contract_interface.py

from web3 import Web3
from eth_account import Account
from typing import Dict, Optional
import json

class FlashLoanContractInterface:
    """Interface to interact with FlashLoanArbitrage smart contract"""

    def __init__(
        self,
        w3: Web3,
        contract_address: str,
        private_key: str
    ):
        self.w3 = w3
        self.contract_address = Web3.toChecksumAddress(contract_address)
        self.account = Account.from_key(private_key)

        # Load contract ABI
        with open('contracts/abi/FlashLoanArbitrage.json') as f:
            abi = json.load(f)

        self.contract = w3.eth.contract(
            address=self.contract_address,
            abi=abi
        )

    async def execute_arbitrage(
        self,
        token: str,
        amount: int,
        buy_dex: str,
        sell_dex: str,
        buy_calldata: bytes,
        sell_calldata: bytes,
        gas_price: Optional[int] = None
    ) -> str:
        """
        Execute flash loan arbitrage

        Returns:
            Transaction hash
        """

        # Build transaction
        nonce = await self.w3.eth.get_transaction_count(
            self.account.address,
            'pending'
        )

        if gas_price is None:
            gas_price = await self.w3.eth.gas_price

        # Estimate gas
        try:
            gas_estimate = await self.contract.functions.executeArbitrage(
                Web3.toChecksumAddress(token),
                amount,
                Web3.toChecksumAddress(buy_dex),
                Web3.toChecksumAddress(sell_dex),
                buy_calldata,
                sell_calldata
            ).estimateGas({'from': self.account.address})

            # Add 20% buffer
            gas_limit = int(gas_estimate * 1.2)
        except Exception as e:
            logger.error(f"Gas estimation failed: {e}")
            # Use default gas limit
            gas_limit = 500_000

        # Build transaction
        tx = self.contract.functions.executeArbitrage(
            Web3.toChecksumAddress(token),
            amount,
            Web3.toChecksumAddress(buy_dex),
            Web3.toChecksumAddress(sell_dex),
            buy_calldata,
            sell_calldata
        ).buildTransaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': await self.w3.eth.chain_id
        })

        # Sign transaction
        signed_tx = self.account.sign_transaction(tx)

        # Send transaction
        tx_hash = await self.w3.eth.send_raw_transaction(
            signed_tx.rawTransaction
        )

        logger.info(f"Flash loan arbitrage transaction sent: {tx_hash.hex()}")

        return tx_hash.hex()

    async def withdraw_profit(self, token: str) -> str:
        """Withdraw accumulated profit"""

        nonce = await self.w3.eth.get_transaction_count(
            self.account.address,
            'pending'
        )

        tx = self.contract.functions.withdrawProfit(
            Web3.toChecksumAddress(token)
        ).buildTransaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 100_000,
            'gasPrice': await self.w3.eth.gas_price,
            'chainId': await self.w3.eth.chain_id
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        return tx_hash.hex()

    async def get_contract_balance(self, token: str) -> int:
        """Get contract's token balance"""

        token_contract = self.w3.eth.contract(
            address=Web3.toChecksumAddress(token),
            abi=[{
                "inputs": [{"type": "address", "name": "account"}],
                "name": "balanceOf",
                "outputs": [{"type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }]
        )

        balance = await token_contract.functions.balanceOf(
            self.contract_address
        ).call()

        return balance

    async def emergency_pause(self) -> str:
        """Emergency pause the contract"""

        tx = self.contract.functions.pause().buildTransaction({
            'from': self.account.address,
            'nonce': await self.w3.eth.get_transaction_count(
                self.account.address,
                'pending'
            ),
            'gas': 50_000,
            'gasPrice': await self.w3.eth.gas_price,
            'chainId': await self.w3.eth.chain_id
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        logger.critical(f"Contract paused via emergency: {tx_hash.hex()}")

        return tx_hash.hex()
```

2. **Flash Loan Orchestrator**

```python
# src/flash_loan/orchestrator.py

from typing import Optional
from dataclasses import dataclass
from .contract_interface import FlashLoanContractInterface
from ..dex.base import DEXAdapter
from ..utils.risk_manager import RiskManager

@dataclass
class FlashLoanArbitrageParams:
    """Parameters for flash loan arbitrage"""
    token_in: str
    token_out: str
    loan_amount: int
    buy_dex: DEXAdapter
    sell_dex: DEXAdapter
    expected_profit_usd: float
    gas_cost_usd: float
    flash_loan_fee_usd: float

class FlashLoanOrchestrator:
    """Orchestrates flash loan arbitrage execution"""

    def __init__(
        self,
        contract_interface: FlashLoanContractInterface,
        risk_manager: RiskManager,
        chain_config: Dict
    ):
        self.contract = contract_interface
        self.risk_manager = risk_manager
        self.chain_config = chain_config

    async def execute_flash_loan_arbitrage(
        self,
        params: FlashLoanArbitrageParams
    ) -> Optional[str]:
        """
        Execute flash loan arbitrage with full safety checks

        Returns:
            Transaction hash if successful, None if rejected
        """

        # Step 1: Pre-execution risk validation
        risk_check = await self.risk_manager.validate_trade(
            token=params.token_in,
            amount_usd=params.loan_amount,
            expected_profit_usd=params.expected_profit_usd
        )

        if not risk_check.approved:
            logger.warning(f"Trade rejected by risk manager: {risk_check.reason}")
            return None

        # Step 2: Calculate net profit
        net_profit = (
            params.expected_profit_usd
            - params.gas_cost_usd
            - params.flash_loan_fee_usd
        )

        if net_profit < self.chain_config['min_net_profit_usd']:
            logger.info(f"Net profit too low: ${net_profit:.2f}")
            return None

        # Step 3: Build DEX swap calldata
        buy_calldata = await self._build_swap_calldata(
            dex=params.buy_dex,
            token_in=params.token_in,
            token_out=params.token_out,
            amount_in=params.loan_amount,
            is_buy=True
        )

        # Expected amount out from buy swap
        expected_token_out = await params.buy_dex.get_amount_out(
            token_in=params.token_in,
            token_out=params.token_out,
            amount_in=params.loan_amount
        )

        sell_calldata = await self._build_swap_calldata(
            dex=params.sell_dex,
            token_in=params.token_out,
            token_out=params.token_in,
            amount_in=expected_token_out,
            is_buy=False
        )

        # Step 4: Execute flash loan
        try:
            tx_hash = await self.contract.execute_arbitrage(
                token=params.token_in,
                amount=params.loan_amount,
                buy_dex=params.buy_dex.router_address,
                sell_dex=params.sell_dex.router_address,
                buy_calldata=buy_calldata,
                sell_calldata=sell_calldata
            )

            logger.info(f"Flash loan arbitrage executed: {tx_hash}")

            # Step 5: Wait for confirmation
            receipt = await self.contract.w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=120
            )

            if receipt['status'] == 1:
                logger.info(f"Arbitrage successful! Tx: {tx_hash}")

                # Record success
                await self.risk_manager.record_trade_result(
                    success=True,
                    profit_usd=net_profit,
                    gas_cost_usd=params.gas_cost_usd
                )

                return tx_hash
            else:
                logger.error(f"Arbitrage transaction reverted: {tx_hash}")

                # Record failure
                await self.risk_manager.record_trade_result(
                    success=False,
                    profit_usd=0,
                    gas_cost_usd=params.gas_cost_usd
                )

                return None

        except Exception as e:
            logger.error(f"Flash loan execution failed: {e}")

            # Record failure
            await self.risk_manager.record_trade_result(
                success=False,
                profit_usd=0,
                gas_cost_usd=params.gas_cost_usd
            )

            return None

    async def _build_swap_calldata(
        self,
        dex: DEXAdapter,
        token_in: str,
        token_out: str,
        amount_in: int,
        is_buy: bool
    ) -> bytes:
        """Build calldata for DEX swap"""

        # Get expected amount out
        expected_amount_out = await dex.get_amount_out(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in
        )

        # Calculate minimum amount with slippage protection
        slippage_tolerance = self.chain_config.get('slippage_tolerance', 0.005)
        min_amount_out = int(expected_amount_out * (1 - slippage_tolerance))

        # Build calldata based on DEX type
        calldata = await dex.build_swap_calldata(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out_minimum=min_amount_out,
            recipient=self.contract.contract_address,
            deadline=int(time.time()) + 300  # 5 minutes
        )

        return calldata
```

**Deliverables:**
- [ ] Contract interface module
- [ ] Flash loan orchestrator
- [ ] Integration tests with forked mainnet
- [ ] Error handling and retry logic
- [ ] Logging and monitoring integration

**Acceptance Criteria:**
- [ ] Successfully execute flash loan on forked Polygon mainnet
- [ ] Handle flash loan failures gracefully
- [ ] Proper error messages for all failure modes
- [ ] Gas estimation accurate within 10%
- [ ] Transaction confirmation handling robust

---

#### 1.4: Testnet Deployment & Validation (Week 5-6)

**Objective:** Deploy to Polygon Mumbai testnet and validate end-to-end functionality

**Tasks:**

1. **Deploy Smart Contract to Mumbai**
   - Use Hardhat deployment script
   - Verify contract on PolygonScan
   - Transfer ownership to bot wallet
   - Fund bot wallet with test MATIC

2. **Configure Testnet Environment**
   - Setup Mumbai RPC endpoints
   - Configure test token addresses (WETH, USDC, etc.)
   - Setup test DEX routers (Uniswap V3, SushiSwap on Mumbai)
   - Configure smaller thresholds for testing

3. **Execute Test Arbitrage Transactions**
   - Create test scenarios with mock price discrepancies
   - Execute 20+ test transactions
   - Validate profit calculations
   - Test failure scenarios (insufficient liquidity, high slippage)

4. **Monitor and Debug**
   - Setup logging for testnet
   - Monitor transaction status
   - Debug any failures
   - Optimize gas usage

**Deliverables:**
- [ ] Deployed and verified contract on Mumbai
- [ ] Testnet configuration files
- [ ] Test execution report (20+ transactions)
- [ ] Bug fixes for issues discovered
- [ ] Testnet monitoring dashboard

**Acceptance Criteria:**
- [ ] 20+ successful arbitrage transactions on testnet
- [ ] Success rate > 80%
- [ ] All profit calculations accurate
- [ ] No critical bugs discovered
- [ ] Gas usage optimized

---

### Phase 1 Completion Criteria

**Must Complete:**
- [ ] All critical bugs fixed in existing codebase
- [ ] Flash loan smart contract deployed and verified on testnet
- [ ] Python backend successfully executes flash loans
- [ ] 20+ successful test transactions on Mumbai
- [ ] Comprehensive test suite with >90% coverage
- [ ] Documentation for all new code

**Phase 1 Exit Gate:**
- Security review of smart contract code
- Code review by 2+ developers
- All tests passing
- Testnet validation successful
- Project stakeholder approval to proceed to Phase 2

**Expected Outcomes:**
- Functional flash loan arbitrage on Polygon testnet
- Proven ability to execute profitable arbitrage
- Foundation for multi-chain expansion
- Team confidence in technical approach

---

## Phase 2: Multi-Chain Infrastructure

**Duration:** 4-6 weeks
**Priority:** P0 (Critical Path)
**Goal:** Support arbitrage on 3+ chains with intelligent chain selection

### Sub-Phases

#### 2.1: Chain Abstraction Layer (Week 7-8)

**Objective:** Create abstraction layer to support multiple chains seamlessly

**Tasks:**

1. **Chain Configuration System**

```python
# config/chains.py

from dataclasses import dataclass
from typing import List, Dict
from enum import Enum

class ChainType(Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"

@dataclass
class RPCProvider:
    """RPC provider configuration"""
    name: str
    url: str
    priority: int  # Lower = higher priority
    rate_limit_per_second: int
    supports_websocket: bool
    api_key: Optional[str] = None

@dataclass
class ChainConfig:
    """Configuration for a single blockchain"""

    # Identity
    chain_id: int
    name: str
    chain_type: ChainType
    native_token: str  # ETH, MATIC, etc.

    # RPC Configuration
    rpc_providers: List[RPCProvider]

    # Economic Parameters
    min_net_profit_usd: float
    min_roi_percent: float
    max_flash_loan_usd: float
    slippage_tolerance: float

    # Gas Configuration
    supports_eip1559: bool
    target_block_time_seconds: int
    max_gas_price_gwei: float

    # Contract Addresses
    flash_loan_contract: str
    aave_pool_provider: Optional[str]

    # DEX Configurations
    dexes: List[Dict]  # List of supported DEXes

    # Token Registry
    tokens: Dict[str, str]  # symbol -> address

    # Operational
    enabled: bool
    priority: int  # For chain selection tiebreaker

# Chain Configurations
CHAINS = {
    137: ChainConfig(  # Polygon
        chain_id=137,
        name="Polygon",
        chain_type=ChainType.MAINNET,
        native_token="MATIC",
        rpc_providers=[
            RPCProvider(
                name="Alchemy",
                url="https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
                priority=1,
                rate_limit_per_second=25,
                supports_websocket=True,
                api_key=None  # Load from env
            ),
            RPCProvider(
                name="Ankr",
                url="https://rpc.ankr.com/polygon",
                priority=2,
                rate_limit_per_second=10,
                supports_websocket=False
            ),
        ],
        min_net_profit_usd=20.0,
        min_roi_percent=0.15,
        max_flash_loan_usd=100_000,
        slippage_tolerance=0.005,
        supports_eip1559=True,
        target_block_time_seconds=2,
        max_gas_price_gwei=500,
        flash_loan_contract="0x...",  # To be deployed
        aave_pool_provider="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        dexes=[
            {
                "name": "uniswap_v3",
                "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
            },
            {
                "name": "sushiswap",
                "router": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
                "factory": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4"
            },
            {
                "name": "quickswap",
                "router": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                "factory": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"
            }
        ],
        tokens={
            "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
            "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
            "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
        },
        enabled=True,
        priority=1
    ),

    42161: ChainConfig(  # Arbitrum
        chain_id=42161,
        name="Arbitrum",
        chain_type=ChainType.MAINNET,
        native_token="ETH",
        rpc_providers=[
            RPCProvider(
                name="Arbitrum Public",
                url="https://arb1.arbitrum.io/rpc",
                priority=1,
                rate_limit_per_second=20,
                supports_websocket=False
            ),
            RPCProvider(
                name="Alchemy",
                url="https://arb-mainnet.g.alchemy.com/v2/{api_key}",
                priority=2,
                rate_limit_per_second=25,
                supports_websocket=True,
                api_key=None
            ),
        ],
        min_net_profit_usd=10.0,  # Lower due to cheaper gas
        min_roi_percent=0.10,
        max_flash_loan_usd=100_000,
        slippage_tolerance=0.005,
        supports_eip1559=True,
        target_block_time_seconds=1,
        max_gas_price_gwei=10,  # Much cheaper than Polygon
        flash_loan_contract="0x...",  # To be deployed
        aave_pool_provider="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        dexes=[
            {
                "name": "uniswap_v3",
                "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
            },
            {
                "name": "sushiswap",
                "router": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
                "factory": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4"
            },
            {
                "name": "camelot",
                "router": "0xc873fEcbd354f5A56E00E710B90EF4201db2448d",
                "factory": "0x6EcCab422D763aC031210895C81787E87B43A652"
            }
        ],
        tokens={
            "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
            "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
            "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
            "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
            "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548"
        },
        enabled=True,
        priority=2
    ),

    10: ChainConfig(  # Optimism
        chain_id=10,
        name="Optimism",
        chain_type=ChainType.MAINNET,
        native_token="ETH",
        rpc_providers=[
            RPCProvider(
                name="Optimism Public",
                url="https://mainnet.optimism.io",
                priority=1,
                rate_limit_per_second=20,
                supports_websocket=False
            ),
            RPCProvider(
                name="Alchemy",
                url="https://opt-mainnet.g.alchemy.com/v2/{api_key}",
                priority=2,
                rate_limit_per_second=25,
                supports_websocket=True,
                api_key=None
            ),
        ],
        min_net_profit_usd=10.0,
        min_roi_percent=0.10,
        max_flash_loan_usd=100_000,
        slippage_tolerance=0.005,
        supports_eip1559=True,
        target_block_time_seconds=2,
        max_gas_price_gwei=5,  # Very cheap
        flash_loan_contract="0x...",  # To be deployed
        aave_pool_provider="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        dexes=[
            {
                "name": "uniswap_v3",
                "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
            },
            {
                "name": "velodrome",
                "router": "0x9c12939390052919aF3155f41Bf4160Fd3666A6f",
                "factory": "0x25CbdDb98b35ab1FF77413456B31EC81A6B6B746"
            }
        ],
        tokens={
            "WETH": "0x4200000000000000000000000000000000000006",
            "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
            "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
            "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
            "OP": "0x4200000000000000000000000000000000000042"
        },
        enabled=True,
        priority=3
    ),

    8453: ChainConfig(  # Base
        chain_id=8453,
        name="Base",
        chain_type=ChainType.MAINNET,
        native_token="ETH",
        rpc_providers=[
            RPCProvider(
                name="Base Public",
                url="https://mainnet.base.org",
                priority=1,
                rate_limit_per_second=20,
                supports_websocket=False
            ),
            RPCProvider(
                name="Alchemy",
                url="https://base-mainnet.g.alchemy.com/v2/{api_key}",
                priority=2,
                rate_limit_per_second=25,
                supports_websocket=True,
                api_key=None
            ),
        ],
        min_net_profit_usd=5.0,  # Lowest due to ultra-cheap gas
        min_roi_percent=0.05,
        max_flash_loan_usd=50_000,  # Lower liquidity on Base
        slippage_tolerance=0.01,  # Higher slippage tolerance due to less liquidity
        supports_eip1559=True,
        target_block_time_seconds=2,
        max_gas_price_gwei=2,  # Ultra cheap
        flash_loan_contract="0x...",  # To be deployed
        aave_pool_provider="0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D",
        dexes=[
            {
                "name": "uniswap_v3",
                "router": "0x2626664c2603336E57B271c5C0b26F421741e481",
                "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
                "quoter": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a"
            },
            {
                "name": "aerodrome",
                "router": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
                "factory": "0x420DD381b31aEf6683db6B902084cB0FFECe40Da"
            },
            {
                "name": "baseswap",
                "router": "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86",
                "factory": "0xFDa619b6d20975be80A10332cD39b9a4b0FAa8BB"
            }
        ],
        tokens={
            "WETH": "0x4200000000000000000000000000000000000006",
            "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        },
        enabled=True,
        priority=4
    )
}

def get_chain_config(chain_id: int) -> ChainConfig:
    """Get configuration for a chain"""
    if chain_id not in CHAINS:
        raise ValueError(f"Unsupported chain: {chain_id}")
    return CHAINS[chain_id]

def get_enabled_chains() -> List[ChainConfig]:
    """Get all enabled chains"""
    return [chain for chain in CHAINS.values() if chain.enabled]
```

2. **Multi-Chain Manager**

```python
# src/chain/manager.py

from typing import Dict, List, Optional
from web3 import Web3
from web3.providers import HTTPProvider
from .config import ChainConfig, RPCProvider
import asyncio
from dataclasses import dataclass, field
import time

@dataclass
class RPCHealth:
    """Health metrics for an RPC provider"""
    provider: RPCProvider
    last_success_time: float = 0
    last_error_time: float = 0
    consecutive_errors: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0
    is_healthy: bool = True

class MultiChainManager:
    """Manages connections to multiple blockchains"""

    def __init__(self, chain_configs: List[ChainConfig]):
        self.chains = {chain.chain_id: chain for chain in chain_configs}
        self.web3_instances: Dict[int, Web3] = {}
        self.rpc_health: Dict[int, List[RPCHealth]] = {}
        self._initialize_connections()

    def _initialize_connections(self):
        """Initialize Web3 instances for all chains"""
        for chain_id, chain in self.chains.items():
            # Initialize RPC health tracking
            self.rpc_health[chain_id] = [
                RPCHealth(provider=provider)
                for provider in chain.rpc_providers
            ]

            # Create Web3 instance with primary provider
            self.web3_instances[chain_id] = self._create_web3_instance(
                chain,
                chain.rpc_providers[0]
            )

            logger.info(f"Initialized connection to {chain.name} (chain_id: {chain_id})")

    def _create_web3_instance(
        self,
        chain: ChainConfig,
        provider: RPCProvider
    ) -> Web3:
        """Create Web3 instance for a specific provider"""

        # Replace API key placeholder
        url = provider.url
        if "{api_key}" in url:
            api_key = os.getenv(f"{provider.name.upper()}_API_KEY")
            if not api_key:
                logger.warning(f"No API key found for {provider.name}")
            url = url.format(api_key=api_key or "")

        # Create provider
        http_provider = HTTPProvider(
            url,
            request_kwargs={'timeout': 10}
        )

        w3 = Web3(http_provider)

        # Verify connection
        try:
            w3.eth.block_number
            logger.info(f"Connected to {chain.name} via {provider.name}")
        except Exception as e:
            logger.error(f"Failed to connect to {chain.name} via {provider.name}: {e}")

        return w3

    def get_web3(self, chain_id: int) -> Web3:
        """Get Web3 instance for a chain"""
        if chain_id not in self.web3_instances:
            raise ValueError(f"No Web3 instance for chain {chain_id}")
        return self.web3_instances[chain_id]

    def get_chain_config(self, chain_id: int) -> ChainConfig:
        """Get configuration for a chain"""
        if chain_id not in self.chains:
            raise ValueError(f"Unknown chain: {chain_id}")
        return self.chains[chain_id]

    async def execute_with_failover(
        self,
        chain_id: int,
        operation: callable,
        *args,
        **kwargs
    ):
        """Execute operation with RPC failover"""

        chain = self.chains[chain_id]
        providers_health = self.rpc_health[chain_id]

        # Sort providers by health score
        providers_health.sort(
            key=lambda h: (h.is_healthy, -h.consecutive_errors, h.provider.priority)
        )

        last_error = None

        for health in providers_health:
            if not health.is_healthy and health.consecutive_errors > 5:
                continue  # Skip unhealthy providers

            try:
                # Switch to this provider if needed
                current_provider = self.web3_instances[chain_id].provider
                if current_provider.endpoint_uri != health.provider.url:
                    self.web3_instances[chain_id] = self._create_web3_instance(
                        chain,
                        health.provider
                    )

                # Execute operation
                start_time = time.time()
                result = await operation(
                    self.web3_instances[chain_id],
                    *args,
                    **kwargs
                )
                latency = (time.time() - start_time) * 1000

                # Update health metrics (success)
                health.last_success_time = time.time()
                health.consecutive_errors = 0
                health.total_requests += 1
                health.avg_latency_ms = (
                    (health.avg_latency_ms * (health.total_requests - 1) + latency)
                    / health.total_requests
                )
                health.is_healthy = True

                return result

            except Exception as e:
                # Update health metrics (failure)
                health.last_error_time = time.time()
                health.consecutive_errors += 1
                health.total_errors += 1
                health.total_requests += 1

                if health.consecutive_errors >= 3:
                    health.is_healthy = False
                    logger.warning(
                        f"RPC {health.provider.name} marked unhealthy "
                        f"({health.consecutive_errors} consecutive errors)"
                    )

                last_error = e
                logger.warning(
                    f"RPC {health.provider.name} failed: {e}, trying next provider"
                )

        # All providers failed
        raise Exception(
            f"All RPC providers failed for chain {chain_id}. "
            f"Last error: {last_error}"
        )

    async def get_gas_price(self, chain_id: int) -> int:
        """Get current gas price for a chain with failover"""

        async def _get_gas_price(w3: Web3) -> int:
            return await w3.eth.gas_price

        return await self.execute_with_failover(chain_id, _get_gas_price)

    async def get_block_number(self, chain_id: int) -> int:
        """Get current block number with failover"""

        async def _get_block_number(w3: Web3) -> int:
            return await w3.eth.block_number

        return await self.execute_with_failover(chain_id, _get_block_number)

    async def health_check_all_chains(self):
        """Perform health check on all chains"""

        results = {}

        for chain_id, chain in self.chains.items():
            try:
                block_number = await self.get_block_number(chain_id)
                gas_price = await self.get_gas_price(chain_id)

                results[chain_id] = {
                    "name": chain.name,
                    "healthy": True,
                    "block_number": block_number,
                    "gas_price_gwei": gas_price / 1e9
                }
            except Exception as e:
                results[chain_id] = {
                    "name": chain.name,
                    "healthy": False,
                    "error": str(e)
                }

        return results
```

**Deliverables:**
- [ ] Chain configuration system
- [ ] Multi-chain manager with RPC failover
- [ ] Health monitoring for all RPC providers
- [ ] Configuration files for 4+ chains
- [ ] Integration tests

**Acceptance Criteria:**
- [ ] Successfully connect to 4+ chains simultaneously
- [ ] RPC failover working correctly
- [ ] Health metrics tracked and reported
- [ ] Configuration easily extendable to new chains
- [ ] All integration tests passing

---

#### 2.2: Chain Cost Profiling (Week 8-9)

**Objective:** Build real-time cost profiling to compare chains

**Tasks:**

1. **Gas Price Monitor**

```python
# src/chain/cost_profiler.py

from dataclasses import dataclass
from typing import Dict, List
import asyncio
import time
from collections import deque

@dataclass
class GasPriceSnapshot:
    """Snapshot of gas price at a point in time"""
    timestamp: float
    chain_id: int
    gas_price_gwei: float
    base_fee_gwei: Optional[float]  # EIP-1559
    priority_fee_gwei: Optional[float]  # EIP-1559

@dataclass
class ChainCostMetrics:
    """Cost metrics for a chain"""
    chain_id: int
    chain_name: str

    # Current metrics
    current_gas_price_gwei: float
    base_fee_gwei: Optional[float]
    priority_fee_gwei: Optional[float]
    native_token_price_usd: float

    # Cost estimates (USD)
    simple_transfer_cost_usd: float
    dex_swap_cost_usd: float
    flash_arbitrage_cost_usd: float

    # Historical stats (24h)
    avg_gas_price_24h_gwei: float
    p50_gas_price_24h_gwei: float
    p95_gas_price_24h_gwei: float
    p99_gas_price_24h_gwei: float

    # Health
    congestion_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    is_available: bool
    rpc_latency_ms: int
    error_rate: float

class ChainCostProfiler:
    """Profiles and compares costs across chains"""

    # Gas estimates for different operations
    GAS_ESTIMATES = {
        'simple_transfer': 21_000,
        'dex_swap': 150_000,
        'flash_arbitrage': 450_000
    }

    def __init__(
        self,
        chain_manager: MultiChainManager,
        price_oracle: PriceOracle
    ):
        self.chain_manager = chain_manager
        self.price_oracle = price_oracle

        # Store historical gas prices (24h rolling window)
        self.gas_price_history: Dict[int, deque] = {}
        for chain_id in chain_manager.chains.keys():
            self.gas_price_history[chain_id] = deque(maxlen=2880)  # 24h at 30s intervals

        # Start background monitoring
        self._monitoring_task = None

    async def start_monitoring(self):
        """Start background gas price monitoring"""
        self._monitoring_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop background monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()

    async def _monitor_loop(self):
        """Background loop to monitor gas prices"""
        while True:
            try:
                await self._update_all_gas_prices()
                await asyncio.sleep(30)  # Update every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gas price monitoring: {e}")
                await asyncio.sleep(30)

    async def _update_all_gas_prices(self):
        """Update gas prices for all chains"""

        tasks = []
        for chain_id in self.chain_manager.chains.keys():
            tasks.append(self._update_chain_gas_price(chain_id))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_chain_gas_price(self, chain_id: int):
        """Update gas price for a single chain"""

        try:
            chain = self.chain_manager.get_chain_config(chain_id)
            w3 = self.chain_manager.get_web3(chain_id)

            # Get gas price
            if chain.supports_eip1559:
                # Get EIP-1559 fees
                latest_block = await w3.eth.get_block('latest')
                base_fee = latest_block.get('baseFeePerGas', 0)

                # Estimate priority fee (median from recent blocks)
                priority_fee = await w3.eth.max_priority_fee

                gas_price = base_fee + priority_fee
                base_fee_gwei = base_fee / 1e9
                priority_fee_gwei = priority_fee / 1e9
            else:
                # Legacy gas price
                gas_price = await w3.eth.gas_price
                base_fee_gwei = None
                priority_fee_gwei = None

            gas_price_gwei = gas_price / 1e9

            # Store snapshot
            snapshot = GasPriceSnapshot(
                timestamp=time.time(),
                chain_id=chain_id,
                gas_price_gwei=gas_price_gwei,
                base_fee_gwei=base_fee_gwei,
                priority_fee_gwei=priority_fee_gwei
            )

            self.gas_price_history[chain_id].append(snapshot)

            logger.debug(
                f"{chain.name} gas price: {gas_price_gwei:.2f} gwei "
                f"(base: {base_fee_gwei:.2f}, priority: {priority_fee_gwei:.2f})"
            )

        except Exception as e:
            logger.error(f"Failed to update gas price for chain {chain_id}: {e}")

    async def get_chain_cost_metrics(
        self,
        chain_id: int
    ) -> ChainCostMetrics:
        """Get comprehensive cost metrics for a chain"""

        chain = self.chain_manager.get_chain_config(chain_id)
        history = self.gas_price_history[chain_id]

        if not history:
            # No data yet, fetch now
            await self._update_chain_gas_price(chain_id)
            history = self.gas_price_history[chain_id]

        # Current metrics
        latest = history[-1] if history else None
        if not latest:
            raise Exception(f"No gas price data for chain {chain_id}")

        current_gas_price_gwei = latest.gas_price_gwei

        # Get native token price in USD
        native_token_price = await self.price_oracle.get_price_usd(
            chain.native_token
        )

        # Calculate cost estimates
        simple_transfer_cost = (
            self.GAS_ESTIMATES['simple_transfer'] *
            current_gas_price_gwei *
            native_token_price /
            1e9
        )

        dex_swap_cost = (
            self.GAS_ESTIMATES['dex_swap'] *
            current_gas_price_gwei *
            native_token_price /
            1e9
        )

        flash_arbitrage_cost = (
            self.GAS_ESTIMATES['flash_arbitrage'] *
            current_gas_price_gwei *
            native_token_price /
            1e9
        )

        # Historical statistics
        gas_prices_24h = [s.gas_price_gwei for s in history]

        if gas_prices_24h:
            avg_gas = sum(gas_prices_24h) / len(gas_prices_24h)
            sorted_prices = sorted(gas_prices_24h)
            p50_gas = sorted_prices[len(sorted_prices) // 2]
            p95_gas = sorted_prices[int(len(sorted_prices) * 0.95)]
            p99_gas = sorted_prices[int(len(sorted_prices) * 0.99)]
        else:
            avg_gas = p50_gas = p95_gas = p99_gas = current_gas_price_gwei

        # Congestion level
        if current_gas_price_gwei < avg_gas * 1.2:
            congestion = "LOW"
        elif current_gas_price_gwei < avg_gas * 2.0:
            congestion = "MEDIUM"
        elif current_gas_price_gwei < avg_gas * 3.0:
            congestion = "HIGH"
        else:
            congestion = "CRITICAL"

        # RPC health
        rpc_health = self.chain_manager.rpc_health[chain_id][0]

        return ChainCostMetrics(
            chain_id=chain_id,
            chain_name=chain.name,
            current_gas_price_gwei=current_gas_price_gwei,
            base_fee_gwei=latest.base_fee_gwei,
            priority_fee_gwei=latest.priority_fee_gwei,
            native_token_price_usd=native_token_price,
            simple_transfer_cost_usd=simple_transfer_cost,
            dex_swap_cost_usd=dex_swap_cost,
            flash_arbitrage_cost_usd=flash_arbitrage_cost,
            avg_gas_price_24h_gwei=avg_gas,
            p50_gas_price_24h_gwei=p50_gas,
            p95_gas_price_24h_gwei=p95_gas,
            p99_gas_price_24h_gwei=p99_gas,
            congestion_level=congestion,
            is_available=rpc_health.is_healthy,
            rpc_latency_ms=int(rpc_health.avg_latency_ms),
            error_rate=rpc_health.total_errors / max(rpc_health.total_requests, 1)
        )

    async def get_all_chain_costs(self) -> List[ChainCostMetrics]:
        """Get cost metrics for all chains"""

        tasks = []
        for chain_id in self.chain_manager.chains.keys():
            tasks.append(self.get_chain_cost_metrics(chain_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        metrics = [r for r in results if isinstance(r, ChainCostMetrics)]

        return metrics

    async def get_cheapest_chain(
        self,
        operation: str = 'flash_arbitrage'
    ) -> Optional[ChainCostMetrics]:
        """Get the cheapest chain for a given operation"""

        all_metrics = await self.get_all_chain_costs()

        # Filter to only available chains
        available = [m for m in all_metrics if m.is_available]

        if not available:
            return None

        # Sort by cost
        cost_key = f"{operation}_cost_usd"
        available.sort(key=lambda m: getattr(m, cost_key, float('inf')))

        return available[0]
```

**Deliverables:**
- [ ] Gas price monitoring system
- [ ] Cost calculation for different operation types
- [ ] Historical statistics tracking (24h window)
- [ ] Congestion level detection
- [ ] API to query cost metrics

**Acceptance Criteria:**
- [ ] Gas prices updated every 30 seconds for all chains
- [ ] Cost estimates accurate within 20%
- [ ] Historical statistics calculated correctly
- [ ] Congestion detection working
- [ ] Cheapest chain selection implemented

---

#### 2.3: Dynamic Chain Selection (Week 9-10)

**Objective:** Implement intelligent algorithm to select optimal chain for each opportunity

**Tasks:**

1. **Chain Selection Algorithm**

```python
# src/chain/selector.py

from dataclasses import dataclass
from typing import Optional, List, Dict
from .cost_profiler import ChainCostMetrics, ChainCostProfiler
from ..bot.arbitrage import ArbitrageOpportunity

@dataclass
class ChainOpportunityScore:
    """Score for executing an opportunity on a specific chain"""
    chain_id: int
    chain_name: str

    # Financials
    gross_profit_usd: float
    gas_cost_usd: float
    flash_loan_fee_usd: float
    net_profit_usd: float
    roi_percent: float

    # Quality scores (0-100)
    profitability_score: float
    reliability_score: float
    speed_score: float
    liquidity_score: float

    # Overall score (weighted combination)
    total_score: float

    # Metadata
    meets_minimum_thresholds: bool
    rejection_reasons: List[str]

class ChainSelector:
    """Selects optimal chain for executing arbitrage opportunities"""

    # Scoring weights
    WEIGHTS = {
        'profitability': 0.50,  # 50% - Most important
        'reliability': 0.25,    # 25% - Success rate matters
        'speed': 0.15,          # 15% - Faster execution is better
        'liquidity': 0.10       # 10% - Need sufficient liquidity
    }

    def __init__(
        self,
        cost_profiler: ChainCostProfiler,
        chain_manager: MultiChainManager
    ):
        self.cost_profiler = cost_profiler
        self.chain_manager = chain_manager

        # Track historical success rates per chain
        self.chain_stats: Dict[int, Dict] = {}
        for chain_id in chain_manager.chains.keys():
            self.chain_stats[chain_id] = {
                'total_attempts': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'total_profit_usd': 0.0,
                'avg_execution_time_ms': 0.0
            }

    async def select_optimal_chain(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Optional[ChainOpportunityScore]:
        """
        Select the optimal chain to execute an arbitrage opportunity

        Returns:
            ChainOpportunityScore for best chain, or None if no viable chain
        """

        # Get all chain cost metrics
        all_costs = await self.cost_profiler.get_all_chain_costs()

        # Score each chain
        scores = []
        for cost_metrics in all_costs:
            score = await self._score_chain_for_opportunity(
                opportunity,
                cost_metrics
            )
            scores.append(score)

        # Filter to chains that meet minimum thresholds
        viable_chains = [
            s for s in scores
            if s.meets_minimum_thresholds
        ]

        if not viable_chains:
            logger.info(
                f"No viable chain for opportunity {opportunity.token_in}->{opportunity.token_out}. "
                f"Reasons: {[s.rejection_reasons for s in scores]}"
            )
            return None

        # Sort by total score (descending)
        viable_chains.sort(key=lambda s: s.total_score, reverse=True)

        best_chain = viable_chains[0]

        logger.info(
            f"Selected {best_chain.chain_name} for arbitrage: "
            f"Net profit ${best_chain.net_profit_usd:.2f}, "
            f"ROI {best_chain.roi_percent:.2f}%, "
            f"Score {best_chain.total_score:.1f}/100"
        )

        return best_chain

    async def _score_chain_for_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
        cost_metrics: ChainCostMetrics
    ) -> ChainOpportunityScore:
        """Score a specific chain for an opportunity"""

        chain_config = self.chain_manager.get_chain_config(cost_metrics.chain_id)
        chain_stats = self.chain_stats[cost_metrics.chain_id]

        # Calculate financials
        gross_profit_usd = opportunity.expected_profit_usd
        gas_cost_usd = cost_metrics.flash_arbitrage_cost_usd

        # Flash loan fee (typically 0.05% for Aave)
        flash_loan_fee_usd = opportunity.loan_amount_usd * 0.0005

        net_profit_usd = gross_profit_usd - gas_cost_usd - flash_loan_fee_usd

        # Avoid division by zero
        if opportunity.loan_amount_usd > 0:
            roi_percent = (net_profit_usd / opportunity.loan_amount_usd) * 100
        else:
            roi_percent = 0

        # Check minimum thresholds
        meets_thresholds = True
        rejection_reasons = []

        if net_profit_usd < chain_config.min_net_profit_usd:
            meets_thresholds = False
            rejection_reasons.append(
                f"Net profit ${net_profit_usd:.2f} < "
                f"minimum ${chain_config.min_net_profit_usd}"
            )

        if roi_percent < chain_config.min_roi_percent:
            meets_thresholds = False
            rejection_reasons.append(
                f"ROI {roi_percent:.2f}% < "
                f"minimum {chain_config.min_roi_percent}%"
            )

        if not cost_metrics.is_available:
            meets_thresholds = False
            rejection_reasons.append("Chain RPC unavailable")

        if cost_metrics.congestion_level == "CRITICAL":
            meets_thresholds = False
            rejection_reasons.append("Chain critically congested")

        # Calculate component scores (0-100)

        # 1. Profitability Score (higher ROI = higher score)
        # 10% ROI = 100 points, scales linearly down
        profitability_score = min(roi_percent / 0.10 * 100, 100)

        # 2. Reliability Score (based on historical success rate)
        if chain_stats['total_attempts'] > 0:
            success_rate = (
                chain_stats['successful_trades'] /
                chain_stats['total_attempts']
            )
            reliability_score = success_rate * 100
        else:
            reliability_score = 50  # Neutral score for new chains

        # 3. Speed Score (based on RPC latency and block time)
        # Lower latency = higher score
        max_acceptable_latency = 1000  # ms
        latency_score = max(
            0,
            (1 - cost_metrics.rpc_latency_ms / max_acceptable_latency) * 100
        )

        # Factor in block time (faster blocks = faster confirmation)
        block_time_score = max(
            0,
            (1 - chain_config.target_block_time_seconds / 10) * 100
        )

        speed_score = (latency_score + block_time_score) / 2

        # 4. Liquidity Score (based on chain priority and DEX count)
        # More established chains = higher score
        max_priority = max(c.priority for c in self.chain_manager.chains.values())
        liquidity_score = ((max_priority - chain_config.priority + 1) / max_priority) * 100

        # Calculate total score (weighted average)
        total_score = (
            profitability_score * self.WEIGHTS['profitability'] +
            reliability_score * self.WEIGHTS['reliability'] +
            speed_score * self.WEIGHTS['speed'] +
            liquidity_score * self.WEIGHTS['liquidity']
        )

        return ChainOpportunityScore(
            chain_id=cost_metrics.chain_id,
            chain_name=cost_metrics.chain_name,
            gross_profit_usd=gross_profit_usd,
            gas_cost_usd=gas_cost_usd,
            flash_loan_fee_usd=flash_loan_fee_usd,
            net_profit_usd=net_profit_usd,
            roi_percent=roi_percent,
            profitability_score=profitability_score,
            reliability_score=reliability_score,
            speed_score=speed_score,
            liquidity_score=liquidity_score,
            total_score=total_score,
            meets_minimum_thresholds=meets_thresholds,
            rejection_reasons=rejection_reasons
        )

    def record_execution_result(
        self,
        chain_id: int,
        success: bool,
        profit_usd: float,
        execution_time_ms: int
    ):
        """Record the result of an execution for future scoring"""

        stats = self.chain_stats[chain_id]

        stats['total_attempts'] += 1

        if success:
            stats['successful_trades'] += 1
            stats['total_profit_usd'] += profit_usd
        else:
            stats['failed_trades'] += 1

        # Update rolling average execution time
        n = stats['total_attempts']
        stats['avg_execution_time_ms'] = (
            (stats['avg_execution_time_ms'] * (n - 1) + execution_time_ms) / n
        )
```

**Deliverables:**
- [ ] Chain selection algorithm
- [ ] Scoring system with configurable weights
- [ ] Historical performance tracking
- [ ] Comprehensive unit tests
- [ ] Performance benchmarks

**Acceptance Criteria:**
- [ ] Algorithm correctly selects cheapest profitable chain
- [ ] Scoring weights can be configured
- [ ] Historical data influences future selections
- [ ] Handles edge cases (all chains unprofitable, RPC failures)
- [ ] Unit tests achieve >90% coverage

---

### Phase 2 Completion Criteria

**Must Complete:**
- [ ] Support for 4+ chains (Polygon, Arbitrum, Optimism, Base)
- [ ] RPC failover working on all chains
- [ ] Real-time gas cost monitoring
- [ ] Chain selection algorithm implemented and tested
- [ ] Smart contracts deployed to all supported chains
- [ ] Multi-chain testnet validation

**Phase 2 Exit Gate:**
- Multi-chain execution successful on testnets
- Performance metrics acceptable (latency, throughput)
- Cost profiling accurate
- Code review completed
- Stakeholder approval

**Expected Outcomes:**
- 4+ chains supported with automatic selection
- 60-80% reduction in average gas costs vs single-chain
- 3-5x increase in opportunity frequency
- Robust RPC management with 99.9% uptime

---

## Phase 3: Advanced Features & Optimization

**Duration:** 4-5 weeks
**Priority:** P1 (High)
**Goal:** Add advanced features for competitive advantage

### Sub-Phases

#### 3.1: Transaction Simulation Integration (Week 11-12)

**Objective:** Integrate Tenderly for pre-execution validation

**Tasks:**

1. **Tenderly API Integration**

```python
# src/simulation/tenderly.py

import aiohttp
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class SimulationResult:
    """Result of transaction simulation"""
    success: bool
    gas_used: int
    gas_price_gwei: float
    profit_usd: float
    net_profit_usd: float
    slippage_percent: float
    error_message: Optional[str] = None
    simulation_url: Optional[str] = None

class TenderlySimulator:
    """Simulates transactions using Tenderly API"""

    BASE_URL = "https://api.tenderly.co/api/v1"

    def __init__(
        self,
        api_key: str,
        account_slug: str,
        project_slug: str
    ):
        self.api_key = api_key
        self.account_slug = account_slug
        self.project_slug = project_slug
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "X-Access-Key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
        return self.session

    async def simulate_transaction(
        self,
        chain_id: int,
        from_address: str,
        to_address: str,
        input_data: str,
        value: int = 0,
        gas: int = 8_000_000,
        gas_price: int = None,
        save_simulation: bool = False
    ) -> SimulationResult:
        """
        Simulate a transaction using Tenderly

        Args:
            chain_id: Network chain ID
            from_address: Transaction sender
            to_address: Transaction recipient (contract)
            input_data: Transaction calldata
            value: ETH value to send
            gas: Gas limit
            gas_price: Gas price in wei
            save_simulation: Whether to save simulation to Tenderly dashboard

        Returns:
            SimulationResult with detailed outcome
        """

        session = await self._get_session()

        # Build simulation request
        url = f"{self.BASE_URL}/account/{self.account_slug}/project/{self.project_slug}/simulate"

        # Convert chain_id to Tenderly network ID
        network_id = self._get_tenderly_network_id(chain_id)

        payload = {
            "network_id": network_id,
            "from": from_address,
            "to": to_address,
            "input": input_data,
            "value": str(value),
            "gas": gas,
            "save": save_simulation,
            "save_if_fails": save_simulation,
            "simulation_type": "full"
        }

        if gas_price:
            payload["gas_price"] = str(gas_price)

        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Tenderly API error: {error_text}")
                    return SimulationResult(
                        success=False,
                        gas_used=0,
                        gas_price_gwei=0,
                        profit_usd=0,
                        net_profit_usd=0,
                        slippage_percent=0,
                        error_message=f"API error: {error_text}"
                    )

                data = await response.json()

                # Parse simulation result
                transaction = data.get("transaction", {})
                simulation = data.get("simulation", {})

                success = transaction.get("status", False)
                gas_used = transaction.get("gas_used", 0)

                # Get simulation URL if saved
                simulation_url = None
                if save_simulation and "id" in simulation:
                    simulation_url = (
                        f"https://dashboard.tenderly.co/{self.account_slug}/"
                        f"{self.project_slug}/simulator/{simulation['id']}"
                    )

                if not success:
                    error_message = transaction.get("error_message", "Unknown error")
                    logger.warning(f"Simulation reverted: {error_message}")

                    return SimulationResult(
                        success=False,
                        gas_used=gas_used,
                        gas_price_gwei=gas_price / 1e9 if gas_price else 0,
                        profit_usd=0,
                        net_profit_usd=0,
                        slippage_percent=0,
                        error_message=error_message,
                        simulation_url=simulation_url
                    )

                # Parse logs to extract profit
                logs = transaction.get("transaction_info", {}).get("logs", [])
                profit_usd = self._extract_profit_from_logs(logs)

                # Calculate net profit
                gas_cost_usd = (gas_used * gas_price / 1e18) * eth_price_usd  # Simplified
                net_profit_usd = profit_usd - gas_cost_usd

                # Calculate slippage (compare expected vs actual)
                slippage_percent = 0  # TODO: Calculate from expected amounts

                return SimulationResult(
                    success=True,
                    gas_used=gas_used,
                    gas_price_gwei=gas_price / 1e9 if gas_price else 0,
                    profit_usd=profit_usd,
                    net_profit_usd=net_profit_usd,
                    slippage_percent=slippage_percent,
                    simulation_url=simulation_url
                )

        except Exception as e:
            logger.error(f"Tenderly simulation failed: {e}")
            return SimulationResult(
                success=False,
                gas_used=0,
                gas_price_gwei=0,
                profit_usd=0,
                net_profit_usd=0,
                slippage_percent=0,
                error_message=str(e)
            )

    def _get_tenderly_network_id(self, chain_id: int) -> str:
        """Convert chain ID to Tenderly network identifier"""
        mapping = {
            1: "1",        # Ethereum Mainnet
            137: "137",    # Polygon
            42161: "42161",  # Arbitrum
            10: "10",      # Optimism
            8453: "8453"   # Base
        }
        return mapping.get(chain_id, str(chain_id))

    def _extract_profit_from_logs(self, logs: List[Dict]) -> float:
        """Extract profit from transaction logs"""
        # Parse ArbitrageExecuted event
        # This is contract-specific
        for log in logs:
            # Look for ArbitrageExecuted event
            topics = log.get("topics", [])
            if len(topics) > 0:
                # Event signature for ArbitrageExecuted(address,uint256,uint256,uint256)
                event_sig = "0x..."  # Calculate keccak256 of event signature
                if topics[0] == event_sig:
                    # Decode profit from event data
                    # Simplified - would need proper ABI decoding
                    pass

        return 0.0  # Placeholder

    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
```

2. **Simulation-First Execution Strategy**

```python
# src/execution/simulator_executor.py

class SimulatorExecutor:
    """Executor that simulates before executing"""

    def __init__(
        self,
        simulator: TenderlySimulator,
        flash_loan_orchestrator: FlashLoanOrchestrator,
        min_simulation_success_rate: float = 0.95
    ):
        self.simulator = simulator
        self.orchestrator = flash_loan_orchestrator
        self.min_simulation_success_rate = min_simulation_success_rate

        # Track simulation accuracy
        self.simulation_stats = {
            'total_simulations': 0,
            'successful_simulations': 0,
            'executed_after_simulation': 0,
            'execution_matched_simulation': 0
        }

    async def execute_with_simulation(
        self,
        params: FlashLoanArbitrageParams,
        chain_id: int
    ) -> Optional[str]:
        """
        Execute flash loan arbitrage with pre-execution simulation

        Returns:
            Transaction hash if successful, None if rejected or failed
        """

        # Step 1: Build transaction for simulation
        tx_data = await self._build_transaction_data(params, chain_id)

        # Step 2: Simulate transaction
        logger.info(f"Simulating arbitrage on {chain_id}...")

        simulation = await self.simulator.simulate_transaction(
            chain_id=chain_id,
            from_address=self.orchestrator.contract.account.address,
            to_address=self.orchestrator.contract.contract_address,
            input_data=tx_data,
            gas=500_000,
            gas_price=await self._get_gas_price(chain_id),
            save_simulation=True  # Save for debugging
        )

        self.simulation_stats['total_simulations'] += 1

        # Step 3: Validate simulation result
        if not simulation.success:
            logger.warning(
                f"Simulation failed: {simulation.error_message}. "
                f"Aborting execution. Simulation: {simulation.simulation_url}"
            )
            return None

        self.simulation_stats['successful_simulations'] += 1

        # Step 4: Validate profitability
        if simulation.net_profit_usd < params.expected_profit_usd * 0.8:
            logger.warning(
                f"Simulated profit ${simulation.net_profit_usd:.2f} "
                f"significantly lower than expected ${params.expected_profit_usd:.2f}. "
                f"Aborting execution."
            )
            return None

        # Step 5: Validate slippage
        if simulation.slippage_percent > 0.01:  # 1%
            logger.warning(
                f"Simulated slippage {simulation.slippage_percent*100:.2f}% too high. "
                f"Aborting execution."
            )
            return None

        # Step 6: Execute for real
        logger.info(
            f"Simulation successful! "
            f"Net profit: ${simulation.net_profit_usd:.2f}, "
            f"Gas: {simulation.gas_used}. "
            f"Proceeding with execution..."
        )

        tx_hash = await self.orchestrator.execute_flash_loan_arbitrage(params)

        if tx_hash:
            self.simulation_stats['executed_after_simulation'] += 1

            # TODO: Compare actual result with simulation
            # If they match, increment execution_matched_simulation

        return tx_hash

    async def _build_transaction_data(
        self,
        params: FlashLoanArbitrageParams,
        chain_id: int
    ) -> str:
        """Build transaction calldata for simulation"""
        # Build same calldata that would be used in real execution
        # This is a simplified version
        contract = self.orchestrator.contract.contract

        # Build swap calldatas
        buy_calldata = await params.buy_dex.build_swap_calldata(...)
        sell_calldata = await params.sell_dex.build_swap_calldata(...)

        # Encode function call
        tx_data = contract.encodeABI(
            fn_name='executeArbitrage',
            args=[
                params.token_in,
                params.loan_amount,
                params.buy_dex.router_address,
                params.sell_dex.router_address,
                buy_calldata,
                sell_calldata
            ]
        )

        return tx_data

    def get_simulation_stats(self) -> Dict:
        """Get simulation statistics"""
        stats = self.simulation_stats.copy()

        if stats['total_simulations'] > 0:
            stats['simulation_success_rate'] = (
                stats['successful_simulations'] / stats['total_simulations']
            )
        else:
            stats['simulation_success_rate'] = 0

        if stats['executed_after_simulation'] > 0:
            stats['execution_accuracy'] = (
                stats['execution_matched_simulation'] / stats['executed_after_simulation']
            )
        else:
            stats['execution_accuracy'] = 0

        return stats
```

**Deliverables:**
- [ ] Tenderly API integration
- [ ] Simulation-first execution strategy
- [ ] Simulation statistics tracking
- [ ] Integration tests
- [ ] Fallback plan if Tenderly unavailable

**Acceptance Criteria:**
- [ ] 100% of transactions simulated before execution
- [ ] Simulation success rate >80%
- [ ] Simulation saves gas costs from failed transactions
- [ ] Execution results match simulation within 10%
- [ ] Graceful degradation if simulation service down

---

Due to length constraints, I'll continue with the remaining phases in the next artifacts. Let me mark this todo as complete and move to the next one.
