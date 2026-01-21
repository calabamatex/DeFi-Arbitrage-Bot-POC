// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../contracts/FlashLoanArbitrage.sol";

/**
 * @title FlashLoanArbitrageTest
 * @notice Comprehensive test suite for FlashLoanArbitrage contract
 */
contract FlashLoanArbitrageTest is Test {
    FlashLoanArbitrage public arbitrage;

    // Polygon Mainnet addresses
    address constant AAVE_POOL_ADDRESS_PROVIDER = 0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb;
    address constant USDC = 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174;
    address constant WETH = 0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619;

    address owner = address(this);
    address user = address(0x1);

    uint256 constant MIN_PROFIT_USD = 10e18; // $10
    uint256 constant MAX_SLIPPAGE_BPS = 200; // 2%

    event ArbitrageExecuted(
        address indexed token,
        uint256 amountBorrowed,
        uint256 profit,
        uint256 timestamp
    );
    event DEXWhitelisted(address indexed dex, bool status);
    event MinProfitUpdated(uint256 oldValue, uint256 newValue);
    event MaxSlippageUpdated(uint256 oldValue, uint256 newValue);

    function setUp() public {
        // Fork Polygon mainnet for testing
        vm.createSelectFork(vm.envString("POLYGON_RPC_URL"));

        // Deploy contract
        arbitrage = new FlashLoanArbitrage(
            AAVE_POOL_ADDRESS_PROVIDER,
            MIN_PROFIT_USD,
            MAX_SLIPPAGE_BPS
        );
    }

    function testDeployment() public view {
        assertEq(address(arbitrage.ADDRESSES_PROVIDER()), AAVE_POOL_ADDRESS_PROVIDER);
        assertEq(arbitrage.minProfitUSD(), MIN_PROFIT_USD);
        assertEq(arbitrage.maxSlippageBps(), MAX_SLIPPAGE_BPS);
        assertEq(arbitrage.owner(), owner);
    }

    function testSetDEXWhitelist() public {
        address dexRouter = address(0x123);

        vm.expectEmit(true, false, false, true);
        emit DEXWhitelisted(dexRouter, true);

        arbitrage.setDEXWhitelist(dexRouter, true);

        assertTrue(arbitrage.whitelistedDEXs(dexRouter));
    }

    function testSetDEXWhitelistUnauthorized() public {
        address dexRouter = address(0x123);

        vm.prank(user);
        vm.expectRevert("Ownable: caller is not the owner");
        arbitrage.setDEXWhitelist(dexRouter, true);
    }

    function testSetMinProfit() public {
        uint256 newMinProfit = 20e18;

        vm.expectEmit(false, false, false, true);
        emit MinProfitUpdated(MIN_PROFIT_USD, newMinProfit);

        arbitrage.setMinProfit(newMinProfit);

        assertEq(arbitrage.minProfitUSD(), newMinProfit);
    }

    function testSetMaxSlippage() public {
        uint256 newMaxSlippage = 300; // 3%

        vm.expectEmit(false, false, false, true);
        emit MaxSlippageUpdated(MAX_SLIPPAGE_BPS, newMaxSlippage);

        arbitrage.setMaxSlippage(newMaxSlippage);

        assertEq(arbitrage.maxSlippageBps(), newMaxSlippage);
    }

    function testSetMaxSlippageTooHigh() public {
        uint256 newMaxSlippage = 1500; // 15% - too high

        vm.expectRevert("Slippage too high");
        arbitrage.setMaxSlippage(newMaxSlippage);
    }

    function testPauseUnpause() public {
        // Pause
        arbitrage.pause();
        assertTrue(arbitrage.paused());

        // Unpause
        arbitrage.unpause();
        assertFalse(arbitrage.paused());
    }

    function testEstimateFlashLoanFee() public view {
        uint256 amount = 1000e6; // 1000 USDC
        uint256 expectedFee = (amount * 5) / 10000; // 0.05%

        uint256 fee = arbitrage.estimateFlashLoanFee(amount);

        assertEq(fee, expectedFee);
    }

    function testEmergencyWithdrawer() public {
        address withdrawer = address(0x456);

        // Grant permission
        arbitrage.grantEmergencyWithdrawer(withdrawer);
        assertTrue(arbitrage.emergencyWithdrawers(withdrawer));

        // Revoke permission
        arbitrage.revokeEmergencyWithdrawer(withdrawer);
        assertFalse(arbitrage.emergencyWithdrawers(withdrawer));
    }

    function testGetBalance() public {
        // Contract should have 0 balance initially
        uint256 balance = arbitrage.getBalance(USDC);
        assertEq(balance, 0);
    }

    // TODO: Add integration tests for actual flash loan execution
    // These require forking mainnet and dealing with real DEXes
    // Will be implemented in Phase 1 development

    function testCannotExecuteArbitrageWhenPaused() public {
        arbitrage.pause();

        FlashLoanArbitrage.ArbitrageParams memory params = FlashLoanArbitrage.ArbitrageParams({
            dexRouters: new address[](2),
            path: new address[](3),
            amountIn: 1000e6,
            minAmountOut: 1001e6,
            deadline: block.timestamp + 1 hours
        });

        vm.expectRevert("Pausable: paused");
        arbitrage.executeArbitrage(params);
    }

    function testCannotExecuteArbitrageWithExpiredDeadline() public {
        FlashLoanArbitrage.ArbitrageParams memory params = FlashLoanArbitrage.ArbitrageParams({
            dexRouters: new address[](2),
            path: new address[](3),
            amountIn: 1000e6,
            minAmountOut: 1001e6,
            deadline: block.timestamp - 1 // Expired
        });

        vm.expectRevert(
            abi.encodeWithSelector(
                FlashLoanArbitrage.DeadlineExpired.selector,
                block.timestamp - 1,
                block.timestamp
            )
        );
        arbitrage.executeArbitrage(params);
    }
}
