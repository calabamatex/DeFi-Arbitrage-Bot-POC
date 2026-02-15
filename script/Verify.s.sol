// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/FlashLoanArbitrageV2.sol";
import "../contracts/adapters/UniswapV3Adapter.sol";
import "../contracts/adapters/UniswapV2Adapter.sol";

/**
 * @title VerifyDeployment
 * @notice Post-deployment verification — checks all wiring is correct.
 *
 * Usage:
 *   forge script script/Verify.s.sol:VerifyDeployment --rpc-url $RPC_URL -vvvv
 *
 * Required env vars:
 *   FLASH_LOAN_ARBITRAGE_ADDRESS
 *   UNISWAP_V3_ADAPTER_ADDRESS
 *   UNISWAP_V2_ADAPTER_ADDRESS
 */
contract VerifyDeployment is Script {
    function run() external view {
        address arbAddr = vm.envAddress("FLASH_LOAN_ARBITRAGE_ADDRESS");
        address v3Addr = vm.envAddress("UNISWAP_V3_ADAPTER_ADDRESS");
        address v2Addr = vm.envAddress("UNISWAP_V2_ADAPTER_ADDRESS");

        FlashLoanArbitrageV2 arb = FlashLoanArbitrageV2(arbAddr);
        UniswapV3Adapter v3 = UniswapV3Adapter(v3Addr);
        UniswapV2Adapter v2 = UniswapV2Adapter(v2Addr);

        console.log("========== DEPLOYMENT VERIFICATION ==========");
        console.log("Chain ID:", block.chainid);
        console.log("");

        // ── Main Contract ───────────────────────────────────────
        console.log("--- FlashLoanArbitrageV2 ---");
        console.log("Address:", arbAddr);
        console.log("Owner:", arb.owner());
        console.log("Pool:", address(arb.POOL()));
        console.log("Paused:", arb.paused());
        console.log("Min Profit:", arb.minProfit());
        console.log("Max Slippage BPS:", arb.maxSlippageBps());
        console.log("Execution Count:", arb.executionCount());
        console.log("");

        // ── V3 Adapter ──────────────────────────────────────────
        console.log("--- UniswapV3Adapter ---");
        console.log("Address:", v3Addr);
        console.log("Owner:", v3.owner());
        console.log("Router:", address(v3.swapRouter()));
        console.log("Quoter:", address(v3.quoter()));
        console.log("");

        // ── V2 Adapter ──────────────────────────────────────────
        console.log("--- UniswapV2Adapter ---");
        console.log("Address:", v2Addr);
        console.log("Owner:", v2.owner());
        console.log("Router:", address(v2.router()));
        console.log("DEX Name:", v2.dexName());
        console.log("");

        // ── Wiring Checks ───────────────────────────────────────
        uint256 failures = 0;

        // Check adapters registered on main contract
        bool v3Registered = arb.registeredAdapters(v3Addr);
        bool v2Registered = arb.registeredAdapters(v2Addr);

        if (v3Registered) {
            console.log("[OK] V3 adapter registered on main contract");
        } else {
            console.log("[FAIL] V3 adapter NOT registered on main contract");
            failures++;
        }

        if (v2Registered) {
            console.log("[OK] V2 adapter registered on main contract");
        } else {
            console.log("[FAIL] V2 adapter NOT registered on main contract");
            failures++;
        }

        // Check main contract authorized on adapters
        bool v3Auth = v3.authorized(arbAddr);
        bool v2Auth = v2.authorized(arbAddr);

        if (v3Auth) {
            console.log("[OK] Main contract authorized on V3 adapter");
        } else {
            console.log("[FAIL] Main contract NOT authorized on V3 adapter");
            failures++;
        }

        if (v2Auth) {
            console.log("[OK] Main contract authorized on V2 adapter");
        } else {
            console.log("[FAIL] Main contract NOT authorized on V2 adapter");
            failures++;
        }

        // Check Aave pool resolves
        address poolAddr = address(arb.POOL());
        if (poolAddr != address(0)) {
            console.log("[OK] Aave Pool resolved:", poolAddr);
        } else {
            console.log("[FAIL] Aave Pool is zero address");
            failures++;
        }

        // Check not paused
        if (!arb.paused()) {
            console.log("[OK] Contract is not paused");
        } else {
            console.log("[WARN] Contract is paused");
        }

        console.log("");
        if (failures == 0) {
            console.log("ALL CHECKS PASSED");
        } else {
            console.log("FAILURES:", failures);
        }
        console.log("=============================================");
    }
}
