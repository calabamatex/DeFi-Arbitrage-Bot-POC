// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../contracts/BalancerFlashLoan.sol";
import "../../contracts/MockERC20.sol";

// ──────────────────────────────────────────────────────────────────────
// Mock Balancer Vault
// ──────────────────────────────────────────────────────────────────────

contract MockBalancerVault {
    /// @notice Simulates Balancer flash loan (0% fee)
    /// @dev Real Balancer Vault receives repayment via safeTransfer (push model),
    ///      not transferFrom (pull model). The callback must transfer tokens back.
    function flashLoan(
        address recipient,
        IERC20[] calldata tokens,
        uint256[] calldata amounts,
        bytes calldata userData
    ) external {
        // Record vault balance before
        uint256[] memory balancesBefore = new uint256[](tokens.length);
        for (uint256 i = 0; i < tokens.length; i++) {
            balancesBefore[i] = tokens[i].balanceOf(address(this));
        }

        // Mint tokens to recipient (simulate lending)
        for (uint256 i = 0; i < tokens.length; i++) {
            MockERC20(address(tokens[i])).mint(recipient, amounts[i]);
        }

        // 0% fee
        uint256[] memory feeAmounts = new uint256[](amounts.length);

        // Call callback (recipient must safeTransfer repayment during this call)
        IFlashLoanRecipient(recipient).receiveFlashLoan(
            tokens, amounts, feeAmounts, userData
        );

        // Verify repayment was received (push model)
        for (uint256 i = 0; i < tokens.length; i++) {
            uint256 balanceAfter = tokens[i].balanceOf(address(this));
            require(
                balanceAfter >= balancesBefore[i] + amounts[i],
                "MockVault: insufficient repayment"
            );
        }
    }
}

// ──────────────────────────────────────────────────────────────────────
// Mock DEX Adapter
// ──────────────────────────────────────────────────────────────────────

contract MockAdapter {
    uint256 public outputMultiplierBps; // e.g., 10100 = 1.01x output

    constructor(uint256 _outputMultiplierBps) {
        outputMultiplierBps = _outputMultiplierBps;
    }

    /// @dev Tokens are already transferred to this adapter before swapDirect is called
    function swapDirect(
        address,
        address tokenOut,
        uint256 amountIn,
        uint256,
        uint256,
        address recipient,
        bytes calldata
    ) external returns (uint256 amountOut) {
        amountOut = (amountIn * outputMultiplierBps) / 10000;
        MockERC20(tokenOut).mint(recipient, amountOut);
    }
}

// ──────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────

contract BalancerFlashLoanTest is Test {
    BalancerFlashLoan balancer;
    MockBalancerVault vault;
    MockAdapter profitableAdapter;
    MockAdapter unprofitableAdapter;
    MockERC20 tokenA;
    MockERC20 tokenB;

    address owner = address(this);
    address user = address(0xBEEF);

    function setUp() public {
        tokenA = new MockERC20("USDC", "USDC", 6);
        tokenB = new MockERC20("WETH", "WETH", 18);

        vault = new MockBalancerVault();
        balancer = new BalancerFlashLoan(
            address(vault),
            100000,  // minProfit: 0.1 USDC
            200      // maxSlippageBps: 2%
        );

        // Profitable adapter: 1.01x output (1% profit per swap)
        profitableAdapter = new MockAdapter(10100);
        // Unprofitable adapter: 0.99x output
        unprofitableAdapter = new MockAdapter(9900);

        // Register profitable adapter
        balancer.setAdapter(address(profitableAdapter), true);

        // Give adapter permission to transfer from balancer contract
        // (the contract uses safeTransfer so it works)
    }

    // ── Deployment ────────────────────────────────────────────────────

    function test_deployment() public view {
        assertEq(balancer.owner(), owner);
        assertEq(address(balancer.VAULT()), address(vault));
        assertEq(balancer.minProfit(), 100000);
        assertEq(balancer.maxSlippageBps(), 200);
        assertEq(balancer.executionCount(), 0);
    }

    // ── Adapter management ────────────────────────────────────────────

    function test_setAdapter() public {
        balancer.setAdapter(address(unprofitableAdapter), true);
        assertTrue(balancer.registeredAdapters(address(unprofitableAdapter)));

        balancer.setAdapter(address(unprofitableAdapter), false);
        assertFalse(balancer.registeredAdapters(address(unprofitableAdapter)));
    }

    function test_setAdapterOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        balancer.setAdapter(address(profitableAdapter), true);
    }

    // ── Min profit ────────────────────────────────────────────────────

    function test_setMinProfit() public {
        balancer.setMinProfit(500000);
        assertEq(balancer.minProfit(), 500000);
    }

    function test_setMinProfitOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        balancer.setMinProfit(0);
    }

    // ── Max slippage ──────────────────────────────────────────────────

    function test_setMaxSlippage() public {
        balancer.setMaxSlippage(500);
        assertEq(balancer.maxSlippageBps(), 500);
    }

    function test_setMaxSlippageTooHigh() public {
        vm.expectRevert("Slippage too high");
        balancer.setMaxSlippage(1001);
    }

    // ── Pause / Unpause ───────────────────────────────────────────────

    function test_pauseUnpause() public {
        balancer.pause();
        assertTrue(balancer.paused());
        balancer.unpause();
        assertFalse(balancer.paused());
    }

    // ── Successful arbitrage (0% fee) ─────────────────────────────────

    function test_successfulArbitrage() public {
        uint256 flashAmount = 10000 * 10**6; // 10,000 USDC
        uint256 deadline = block.timestamp + 300;

        // Build steps: A → B (1.01x) → A (1.01x) = ~1.0201x total
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](2);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(profitableAdapter),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });
        steps[1] = BalancerFlashLoan.SwapStep({
            adapter: address(profitableAdapter),
            tokenIn: address(tokenB),
            tokenOut: address(tokenA),
            minAmountOut: 0,
            data: ""
        });

        // Expected output: 10000 * 1.01 * 1.01 = 10201 USDC
        // Profit: 201 USDC (201 * 10^6 > minProfit 100000)
        uint256 expectedFinal = (flashAmount * 10100 / 10000) * 10100 / 10000;

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: flashAmount,
            flashLoanAsset: address(tokenA),
            minFinalAmount: flashAmount + 100000,
            deadline: deadline
        });

        balancer.executeArbitrage(params);

        // Verify profit tracked (0% fee means all profit is kept)
        uint256 profit = balancer.totalProfits(address(tokenA));
        assertEq(profit, expectedFinal - flashAmount);
        assertEq(balancer.executionCount(), 1);
    }

    // ── Revert: insufficient profit ───────────────────────────────────

    function test_revertInsufficientProfit() public {
        // Use unprofitable adapter
        balancer.setAdapter(address(unprofitableAdapter), true);

        uint256 flashAmount = 10000 * 10**6;
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](2);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(unprofitableAdapter),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });
        steps[1] = BalancerFlashLoan.SwapStep({
            adapter: address(unprofitableAdapter),
            tokenIn: address(tokenB),
            tokenOut: address(tokenA),
            minAmountOut: 0,
            data: ""
        });

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: flashAmount,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert(abi.encodeWithSelector(
            BalancerFlashLoan.InsufficientProfit.selector,
            0,
            100000
        ));
        balancer.executeArbitrage(params);
    }

    // ── Revert: deadline expired ──────────────────────────────────────

    function test_revertDeadlineExpired() public {
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](1);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(profitableAdapter),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp - 1
        });

        vm.expectRevert(BalancerFlashLoan.DeadlineExpired.selector);
        balancer.executeArbitrage(params);
    }

    // ── Revert: empty steps ───────────────────────────────────────────

    function test_revertEmptySteps() public {
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](0);
        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert(BalancerFlashLoan.InvalidPath.selector);
        balancer.executeArbitrage(params);
    }

    // ── Revert: unregistered adapter ──────────────────────────────────

    function test_revertUnregisteredAdapter() public {
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](1);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(0xDEAD),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert(abi.encodeWithSelector(
            BalancerFlashLoan.UnauthorizedAdapter.selector,
            address(0xDEAD)
        ));
        balancer.executeArbitrage(params);
    }

    // ── Revert: only owner ────────────────────────────────────────────

    function test_revertOnlyOwnerCanExecute() public {
        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](1);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(profitableAdapter),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp + 300
        });

        vm.prank(user);
        vm.expectRevert();
        balancer.executeArbitrage(params);
    }

    // ── Revert: when paused ───────────────────────────────────────────

    function test_revertWhenPaused() public {
        balancer.pause();

        BalancerFlashLoan.SwapStep[] memory steps = new BalancerFlashLoan.SwapStep[](1);
        steps[0] = BalancerFlashLoan.SwapStep({
            adapter: address(profitableAdapter),
            tokenIn: address(tokenA),
            tokenOut: address(tokenB),
            minAmountOut: 0,
            data: ""
        });

        BalancerFlashLoan.ArbitrageParams memory params = BalancerFlashLoan.ArbitrageParams({
            steps: steps,
            flashLoanAmount: 1000,
            flashLoanAsset: address(tokenA),
            minFinalAmount: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert();
        balancer.executeArbitrage(params);
    }

    // ── Withdraw profits ──────────────────────────────────────────────

    function test_withdrawProfits() public {
        // First execute a profitable arb
        test_successfulArbitrage();

        uint256 profit = balancer.totalProfits(address(tokenA));
        assertTrue(profit > 0);

        balancer.withdrawProfits(address(tokenA), profit, owner);
        assertEq(balancer.totalProfits(address(tokenA)), 0);
    }

    function test_withdrawProfitsExceedsBalance() public {
        vm.expectRevert("Insufficient profits");
        balancer.withdrawProfits(address(tokenA), 1, owner);
    }

    // ── Emergency withdraw ────────────────────────────────────────────

    function test_emergencyWithdraw() public {
        tokenA.mint(address(balancer), 1000);
        uint256 balBefore = tokenA.balanceOf(owner);
        balancer.emergencyWithdraw(address(tokenA), 1000, owner);
        assertEq(tokenA.balanceOf(owner) - balBefore, 1000);
    }

    // ── Unauthorized callback ─────────────────────────────────────────

    function test_revertUnauthorizedCallback() public {
        IERC20[] memory tokens = new IERC20[](0);
        uint256[] memory amounts = new uint256[](0);
        uint256[] memory fees = new uint256[](0);

        vm.prank(user);
        vm.expectRevert(BalancerFlashLoan.UnauthorizedCaller.selector);
        balancer.receiveFlashLoan(tokens, amounts, fees, "");
    }
}
