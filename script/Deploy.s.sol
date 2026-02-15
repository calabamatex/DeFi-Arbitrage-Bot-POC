// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/FlashLoanArbitrageV2.sol";
import "../contracts/adapters/UniswapV3Adapter.sol";
import "../contracts/adapters/UniswapV2Adapter.sol";
import "../contracts/adapters/CurveAdapter.sol";
import "../contracts/BalancerFlashLoan.sol";

/**
 * @title DeployAll
 * @notice Deploys FlashLoanArbitrageV2 + adapters, wires them together.
 *
 * Usage (encrypted keystore — recommended):
 *   # First, import your key into Foundry's keystore:
 *   cast wallet import deployer --interactive
 *
 *   # Dry run:
 *   forge script script/Deploy.s.sol:DeployAll --rpc-url $RPC_URL --account deployer -vvvv
 *
 *   # Broadcast to chain:
 *   forge script script/Deploy.s.sol:DeployAll --rpc-url $RPC_URL --account deployer --broadcast --verify -vvvv
 *
 * Required env vars:
 *   AAVE_POOL_PROVIDER       — Aave V3 PoolAddressesProvider
 *   UNISWAP_V3_ROUTER        — Uniswap V3 SwapRouter
 *   UNISWAP_V3_QUOTER        — Uniswap V3 QuoterV2
 *   V2_ROUTER                — Uniswap V2 / QuickSwap router
 *   V2_DEX_NAME              — Name for V2 adapter (e.g. "QuickSwap")
 *   MIN_PROFIT               — Minimum profit in token units (e.g. 100000 for 0.1 USDC)
 *   MAX_SLIPPAGE_BPS         — Max slippage in basis points (e.g. 200 for 2%)
 *
 * Key management: Use `--account <name>` (Foundry encrypted keystore) instead
 * of storing PRIVATE_KEY in .env files. See: cast wallet import --help
 */
contract DeployAll is Script {
    function run() external {
        // ── Load config from env ────────────────────────────────
        address aaveProvider = vm.envAddress("AAVE_POOL_PROVIDER");
        address v3Router = vm.envAddress("UNISWAP_V3_ROUTER");
        address v3Quoter = vm.envAddress("UNISWAP_V3_QUOTER");
        address v2Router = vm.envAddress("V2_ROUTER");
        string memory v2Name = vm.envOr("V2_DEX_NAME", string("QuickSwap"));
        uint256 minProfit = vm.envOr("MIN_PROFIT", uint256(100000));
        uint256 maxSlippageBps = vm.envOr("MAX_SLIPPAGE_BPS", uint256(200));
        address balancerVault = vm.envOr("BALANCER_VAULT", address(0xBA12222222228d8Ba445958a75a0704d566BF2C8));

        console.log("========================================");
        console.log("  FlashLoanArbitrageV2 Deployment");
        console.log("========================================");
        console.log("Deployer:", msg.sender);
        console.log("Chain ID:", block.chainid);
        console.log("Aave Provider:", aaveProvider);
        console.log("V3 Router:", v3Router);
        console.log("V3 Quoter:", v3Quoter);
        console.log("V2 Router:", v2Router);
        console.log("V2 Name:", v2Name);
        console.log("Min Profit:", minProfit);
        console.log("Max Slippage BPS:", maxSlippageBps);
        console.log("========================================");

        // Key is injected by Foundry via --account or --private-key flag.
        // No PRIVATE_KEY env var needed.
        vm.startBroadcast();

        // ── 1. Deploy V3 Adapter ────────────────────────────────
        UniswapV3Adapter v3Adapter = new UniswapV3Adapter(v3Router, v3Quoter);
        console.log("V3 Adapter deployed:", address(v3Adapter));

        // ── 2. Deploy V2 Adapter ────────────────────────────────
        UniswapV2Adapter v2Adapter = new UniswapV2Adapter(v2Router, v2Name);
        console.log("V2 Adapter deployed:", address(v2Adapter));

        // ── 3. Deploy Main Contract ─────────────────────────────
        FlashLoanArbitrageV2 arb = new FlashLoanArbitrageV2(
            aaveProvider,
            minProfit,
            maxSlippageBps
        );
        console.log("FlashLoanArbitrageV2 deployed:", address(arb));

        // ── 4. Deploy Curve Adapter ────────────────────────────
        CurveAdapter curveAdapter = new CurveAdapter();
        console.log("CurveAdapter deployed:", address(curveAdapter));

        // ── 5. Deploy Balancer Flash Loan (0% fee) ────────────
        BalancerFlashLoan balancerArb = new BalancerFlashLoan(
            balancerVault,
            minProfit,
            maxSlippageBps
        );
        console.log("BalancerFlashLoan deployed:", address(balancerArb));

        // ── 6. Register all adapters on both flash loan contracts ──
        arb.setAdapter(address(v3Adapter), true);
        arb.setAdapter(address(v2Adapter), true);
        arb.setAdapter(address(curveAdapter), true);
        balancerArb.setAdapter(address(v3Adapter), true);
        balancerArb.setAdapter(address(v2Adapter), true);
        balancerArb.setAdapter(address(curveAdapter), true);
        console.log("Adapters registered on both flash loan contracts");

        // ── 7. Authorize both flash loan contracts on adapters ──
        v3Adapter.setAuthorized(address(arb), true);
        v3Adapter.setAuthorized(address(balancerArb), true);
        v2Adapter.setAuthorized(address(arb), true);
        v2Adapter.setAuthorized(address(balancerArb), true);
        curveAdapter.setAuthorized(address(arb), true);
        curveAdapter.setAuthorized(address(balancerArb), true);
        console.log("Both contracts authorized on adapters");

        vm.stopBroadcast();

        // ── Summary ─────────────────────────────────────────────
        console.log("");
        console.log("========== DEPLOYMENT COMPLETE ==========");
        console.log("FlashLoanArbitrageV2:", address(arb));
        console.log("BalancerFlashLoan:   ", address(balancerArb));
        console.log("UniswapV3Adapter:    ", address(v3Adapter));
        console.log("UniswapV2Adapter:    ", address(v2Adapter));
        console.log("CurveAdapter:        ", address(curveAdapter));
        console.log("");
        console.log("Add these to your .env:");
        console.log("  FLASH_LOAN_ARBITRAGE_ADDRESS=", address(arb));
        console.log("  BALANCER_FLASH_LOAN_ADDRESS=", address(balancerArb));
        console.log("  UNISWAP_V3_ADAPTER_ADDRESS=", address(v3Adapter));
        console.log("  UNISWAP_V2_ADAPTER_ADDRESS=", address(v2Adapter));
        console.log("  CURVE_ADAPTER_ADDRESS=", address(curveAdapter));
        console.log("=========================================");
    }
}
