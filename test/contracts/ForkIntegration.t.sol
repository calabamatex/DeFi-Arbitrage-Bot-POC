// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../contracts/FlashLoanArbitrageV2.sol";
import "../../contracts/adapters/UniswapV3Adapter.sol";
import "../../contracts/adapters/UniswapV2Adapter.sol";

/**
 * @title ForkIntegrationTest
 * @notice Integration tests that run against a Polygon mainnet fork.
 * @dev Requires POLYGON_RPC_URL env var. Run with: forge test --match-contract ForkIntegrationTest -vvv
 */
contract ForkIntegrationTest is Test {
    // ── Polygon Mainnet Addresses ───────────────────────────────────
    address constant AAVE_POOL_PROVIDER = 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb;
    address constant UNISWAP_V3_ROUTER  = 0xE592427A0AEce92De3Edee1F18E0157C05861564;
    address constant UNISWAP_V3_QUOTER  = 0x61fFE014bA17989E743c5F6cB21bF9697530B21e;
    address constant QUICKSWAP_ROUTER   = 0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff;
    address constant USDC               = 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174;
    address constant WMATIC             = 0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270;
    address constant WETH               = 0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619;

    FlashLoanArbitrageV2 public arb;
    UniswapV3Adapter public v3Adapter;
    UniswapV2Adapter public v2Adapter;

    address deployer;

    function setUp() public {
        // Fork Polygon mainnet
        vm.createSelectFork(vm.envString("POLYGON_RPC_URL"));

        deployer = address(this);

        // Deploy adapters
        v3Adapter = new UniswapV3Adapter(UNISWAP_V3_ROUTER, UNISWAP_V3_QUOTER);
        v2Adapter = new UniswapV2Adapter(QUICKSWAP_ROUTER, "QuickSwap");

        // Deploy main contract
        arb = new FlashLoanArbitrageV2(
            AAVE_POOL_PROVIDER,
            0,    // minProfit = 0 for testing
            500   // maxSlippageBps = 5%
        );

        // Register adapters on main contract
        arb.setAdapter(address(v3Adapter), true);
        arb.setAdapter(address(v2Adapter), true);

        // Authorize main contract on adapters
        v3Adapter.setAuthorized(address(arb), true);
        v2Adapter.setAuthorized(address(arb), true);
    }

    // ── Deployment Validation ───────────────────────────────────────

    function testForkDeployment() public view {
        assertEq(arb.owner(), deployer);
        assertTrue(arb.registeredAdapters(address(v3Adapter)));
        assertTrue(arb.registeredAdapters(address(v2Adapter)));
        assertTrue(v3Adapter.authorized(address(arb)));
        assertTrue(v2Adapter.authorized(address(arb)));
    }

    function testAavePoolResolution() public view {
        // Verify Aave pool address resolves correctly on fork
        address poolAddr = address(arb.POOL());
        assertTrue(poolAddr != address(0), "Pool should not be zero");
    }

    // ── Adapter Access Control on Fork ──────────────────────────────

    function testV3AdapterRejectsUnauthorized() public {
        address attacker = address(0xDEAD);
        vm.prank(attacker);
        vm.expectRevert(UniswapV3Adapter.Unauthorized.selector);
        v3Adapter.swapDirect(USDC, WETH, 1000e6, 0, block.timestamp + 60, attacker, abi.encode(uint24(3000)));
    }

    function testV2AdapterRejectsUnauthorized() public {
        address attacker = address(0xDEAD);
        vm.prank(attacker);
        vm.expectRevert(UniswapV2Adapter.Unauthorized.selector);
        v2Adapter.swapDirect(USDC, WMATIC, 1000e6, 0, block.timestamp + 60, attacker, "");
    }

    // ── V3 Adapter Fee Validation ───────────────────────────────────

    function testV3InvalidFeeReverts() public {
        // Authorize this test contract to call swapDirect
        v3Adapter.setAuthorized(address(this), true);

        // Send some USDC to adapter (so it has tokens)
        deal(USDC, address(v3Adapter), 1000e6);

        // Invalid fee tier (100 is not 500/3000/10000)
        vm.expectRevert(abi.encodeWithSelector(UniswapV3Adapter.InvalidFee.selector, uint24(100)));
        v3Adapter.swapDirect(
            USDC, WETH, 1000e6, 0, block.timestamp + 60,
            address(this), abi.encode(uint24(100))
        );
    }

    function testV3InvalidDataLengthReverts() public {
        v3Adapter.setAuthorized(address(this), true);
        deal(USDC, address(v3Adapter), 1000e6);

        vm.expectRevert(UniswapV3Adapter.InvalidDataLength.selector);
        v3Adapter.swapDirect(
            USDC, WETH, 1000e6, 0, block.timestamp + 60,
            address(this), ""  // empty data
        );
    }

    // ── V3 Adapter Real Swap ────────────────────────────────────────

    function testV3AdapterRealSwap() public {
        v3Adapter.setAuthorized(address(this), true);

        // Give adapter some USDC
        deal(USDC, address(v3Adapter), 1000e6);

        uint256 balBefore = IERC20(WETH).balanceOf(address(this));

        uint256 amountOut = v3Adapter.swapDirect(
            USDC,
            WETH,
            1000e6,
            0,  // no min for test
            block.timestamp + 60,
            address(this),
            abi.encode(uint24(3000))
        );

        uint256 balAfter = IERC20(WETH).balanceOf(address(this));
        assertTrue(amountOut > 0, "Should receive WETH");
        assertEq(balAfter - balBefore, amountOut, "Balance should match amountOut");
    }

    // ── V2 Adapter Real Swap ────────────────────────────────────────

    function testV2AdapterRealSwap() public {
        v2Adapter.setAuthorized(address(this), true);

        deal(USDC, address(v2Adapter), 1000e6);

        uint256 balBefore = IERC20(WMATIC).balanceOf(address(this));

        uint256 amountOut = v2Adapter.swapDirect(
            USDC,
            WMATIC,
            1000e6,
            0,
            block.timestamp + 60,
            address(this),
            ""
        );

        uint256 balAfter = IERC20(WMATIC).balanceOf(address(this));
        assertTrue(amountOut > 0, "Should receive WMATIC");
        assertEq(balAfter - balBefore, amountOut, "Balance should match amountOut");
    }

    // ── V3 QuoterV2 ────────────────────────────────────────────────

    function testV3QuoterWorks() public {
        uint256 quote = v3Adapter.getQuote(USDC, WETH, 1000e6, 3000);
        assertTrue(quote > 0, "Quote should return non-zero");
    }

    function testV3FindBestFee() public {
        (uint24 bestFee, uint256 bestAmount) = v3Adapter.findBestFee(USDC, WETH, 1000e6);
        assertTrue(bestFee == 500 || bestFee == 3000 || bestFee == 10000, "Fee should be valid");
        assertTrue(bestAmount > 0, "Best amount should be positive");
    }

    // ── V2 Quoter ──────────────────────────────────────────────────

    function testV2QuoterWorks() public view {
        uint256 quote = v2Adapter.getQuote(USDC, WMATIC, 1000e6);
        assertTrue(quote > 0, "V2 quote should return non-zero");
    }

    // ── Full Flash Loan (likely reverts since no real arb) ──────────

    function testFlashLoanRevertsWithNoProfit() public {
        // Attempt a flash loan arb with real DEXes
        // This will revert because round-tripping USDC→WETH→USDC
        // through same-direction swaps loses money to fees

        FlashLoanArbitrageV2.SwapStep[] memory steps = new FlashLoanArbitrageV2.SwapStep[](2);

        // Step 1: V3 USDC → WETH
        steps[0] = FlashLoanArbitrageV2.SwapStep({
            adapter: address(v3Adapter),
            tokenIn: USDC,
            tokenOut: WETH,
            minAmountOut: 0,
            data: abi.encode(uint24(3000))
        });

        // Step 2: V2 WETH → USDC
        steps[1] = FlashLoanArbitrageV2.SwapStep({
            adapter: address(v2Adapter),
            tokenIn: WETH,
            tokenOut: USDC,
            minAmountOut: 0,
            data: ""
        });

        FlashLoanArbitrageV2.ArbitrageParams memory params = FlashLoanArbitrageV2.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000e6,
            flashLoanAsset: USDC,
            minFinalAmount: 0,
            deadline: block.timestamp + 1 hours
        });

        // Should revert with InsufficientProfit since round-tripping loses money
        vm.expectRevert();
        arb.executeArbitrage(params);
    }
}
