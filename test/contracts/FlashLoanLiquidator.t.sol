// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../contracts/FlashLoanLiquidator.sol";
import "../../contracts/MockERC20.sol";

// ──────────────────────────────────────────────────────────────────────
// Mock contracts
// ──────────────────────────────────────────────────────────────────────

/// @notice Mock Pool that implements flashLoan and liquidationCall
contract MockLiqPool {
    uint256 public constant PREMIUM_BPS = 5;

    // Simulated liquidation: give 105% of debt in collateral (5% bonus)
    uint256 public liquidationBonusBps = 500; // 5%
    bool public liquidationShouldFail;

    function setLiquidationBonusBps(uint256 bps) external {
        liquidationBonusBps = bps;
    }

    function setLiquidationShouldFail(bool fail) external {
        liquidationShouldFail = fail;
    }

    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata,
        address,
        bytes calldata params,
        uint16
    ) external {
        // Mint flash loaned tokens
        for (uint256 i = 0; i < assets.length; i++) {
            MockERC20(assets[i]).mint(receiverAddress, amounts[i]);
        }

        uint256[] memory premiums = new uint256[](amounts.length);
        for (uint256 i = 0; i < amounts.length; i++) {
            premiums[i] = (amounts[i] * PREMIUM_BPS) / 10000;
        }

        (bool success,) = receiverAddress.call(
            abi.encodeWithSignature(
                "executeOperation(address[],uint256[],uint256[],address,bytes)",
                assets, amounts, premiums, receiverAddress, params
            )
        );
        require(success, "executeOperation failed");

        // Pull repayment
        for (uint256 i = 0; i < assets.length; i++) {
            uint256 owed = amounts[i] + premiums[i];
            IERC20(assets[i]).transferFrom(receiverAddress, address(this), owed);
        }
    }

    /// @notice Mock liquidationCall — burns debt, mints collateral with bonus
    function liquidationCall(
        address collateralAsset,
        address debtAsset,
        address,
        uint256 debtToCover,
        bool
    ) external returns (uint256, uint256) {
        if (liquidationShouldFail) return (0, 0);

        // Take debt from caller
        IERC20(debtAsset).transferFrom(msg.sender, address(this), debtToCover);

        // Give collateral with bonus
        uint256 collateralAmount = debtToCover + (debtToCover * liquidationBonusBps) / 10000;
        MockERC20(collateralAsset).mint(msg.sender, collateralAmount);

        return (collateralAmount, debtToCover);
    }
}

/// @notice Mock Aave PoolAddressesProvider
contract MockLiqProvider {
    address public pool;
    constructor(address _pool) { pool = _pool; }
    function getPool() external view returns (address) { return pool; }
}

/// @notice Mock DEX adapter for liquidation tests
contract MockLiqAdapter {
    uint256 public rate; // output per input, scaled 1e6

    constructor(uint256 _rate) { rate = _rate; }

    function swapDirect(
        address,
        address tokenOut,
        uint256 amountIn,
        uint256,
        uint256,
        address recipient,
        bytes calldata
    ) external returns (uint256 amountOut) {
        amountOut = (amountIn * rate) / 1e6;
        MockERC20(tokenOut).mint(recipient, amountOut);
    }
}

// ──────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────

contract FlashLoanLiquidatorTest is Test {
    FlashLoanLiquidator liquidator;
    MockLiqPool pool;
    MockLiqProvider provider;
    MockLiqAdapter adapter;
    MockERC20 debtToken;
    MockERC20 collateralToken;

    address owner = address(this);
    address user = address(0xBEEF);
    address borrower = address(0xDEAD);

    function setUp() public {
        debtToken = new MockERC20("USDC", "USDC", 6);
        collateralToken = new MockERC20("WETH", "WETH", 18);

        pool = new MockLiqPool();
        provider = new MockLiqProvider(address(pool));

        liquidator = new FlashLoanLiquidator(
            address(provider),
            100000 // min profit: 0.1 USDC
        );

        // Adapter: 1:1 swap rate
        adapter = new MockLiqAdapter(1e6);
        liquidator.setAdapter(address(adapter), true);
    }

    // ── Deployment ────────────────────────────────────────────────────

    function test_deployment() public view {
        assertEq(liquidator.owner(), owner);
        assertEq(address(liquidator.POOL()), address(pool));
        assertEq(liquidator.minProfit(), 100000);
        assertEq(liquidator.liquidationCount(), 0);
    }

    // ── Successful liquidation ────────────────────────────────────────

    function test_successfulLiquidation() public {
        uint256 debtAmount = 10000 * 10**6; // 10,000 USDC

        // Pool gives 5% bonus in collateral: 10,500 collateral
        // Adapter swaps 10,500 collateral → 10,500 debt token (1:1)
        // Flash loan fee: 10000 * 0.05% = 5 USDC
        // Profit: 10,500 - 10,000 - 5 = 495 USDC = 495 * 10^6

        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: debtAmount,
            adapter: address(adapter),
            swapData: "",
            minProfit: 100000,
            minSwapAmountOut: 0,
            deadline: block.timestamp + 300
        });

        liquidator.executeLiquidation(params);

        uint256 profit = liquidator.totalProfits(address(debtToken));
        // 10,500 - 10,005 = 495 USDC
        assertEq(profit, 495 * 10**6);
        assertEq(liquidator.liquidationCount(), 1);
    }

    // ── Insufficient profit ───────────────────────────────────────────

    function test_revertInsufficientProfit() public {
        // Set low bonus (0.01%) — won't cover flash loan fee
        pool.setLiquidationBonusBps(1);

        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: 10000 * 10**6,
            adapter: address(adapter),
            swapData: "",
            minProfit: 100000,
            minSwapAmountOut: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert(); // InsufficientProfit
        liquidator.executeLiquidation(params);
    }

    // ── Deadline expired ──────────────────────────────────────────────

    function test_revertDeadlineExpired() public {
        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: 1000,
            adapter: address(adapter),
            swapData: "",
            minProfit: 0,
            minSwapAmountOut: 0,
            deadline: block.timestamp - 1
        });

        vm.expectRevert(FlashLoanLiquidator.DeadlineExpired.selector);
        liquidator.executeLiquidation(params);
    }

    // ── Unregistered adapter ──────────────────────────────────────────

    function test_revertUnregisteredAdapter() public {
        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: 1000,
            adapter: address(0xDEAD),
            swapData: "",
            minProfit: 0,
            minSwapAmountOut: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert(abi.encodeWithSelector(
            FlashLoanLiquidator.UnauthorizedAdapter.selector,
            address(0xDEAD)
        ));
        liquidator.executeLiquidation(params);
    }

    // ── Only owner ────────────────────────────────────────────────────

    function test_revertOnlyOwner() public {
        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: 1000,
            adapter: address(adapter),
            swapData: "",
            minProfit: 0,
            minSwapAmountOut: 0,
            deadline: block.timestamp + 300
        });

        vm.prank(user);
        vm.expectRevert();
        liquidator.executeLiquidation(params);
    }

    // ── Paused ────────────────────────────────────────────────────────

    function test_revertWhenPaused() public {
        liquidator.pause();

        FlashLoanLiquidator.LiquidationParams memory params = FlashLoanLiquidator.LiquidationParams({
            collateralAsset: address(collateralToken),
            debtAsset: address(debtToken),
            user: borrower,
            debtToCover: 1000,
            adapter: address(adapter),
            swapData: "",
            minProfit: 0,
            minSwapAmountOut: 0,
            deadline: block.timestamp + 300
        });

        vm.expectRevert();
        liquidator.executeLiquidation(params);
    }

    // ── Admin functions ───────────────────────────────────────────────

    function test_setAdapter() public {
        liquidator.setAdapter(user, true);
        assertTrue(liquidator.registeredAdapters(user));
    }

    function test_setMinProfit() public {
        liquidator.setMinProfit(500000);
        assertEq(liquidator.minProfit(), 500000);
    }

    function test_withdrawProfits() public {
        test_successfulLiquidation();
        uint256 profit = liquidator.totalProfits(address(debtToken));
        liquidator.withdrawProfits(address(debtToken), profit, owner);
        assertEq(liquidator.totalProfits(address(debtToken)), 0);
    }

    function test_emergencyWithdraw() public {
        debtToken.mint(address(liquidator), 1000);
        uint256 balBefore = debtToken.balanceOf(owner);
        liquidator.emergencyWithdraw(address(debtToken), 1000, owner);
        assertEq(debtToken.balanceOf(owner) - balBefore, 1000);
    }

    // ── Zero-address constructor ───────────────────────────────────

    function test_revertZeroAddressConstructor() public {
        vm.expectRevert("Invalid address provider");
        new FlashLoanLiquidator(address(0), 100000);
    }
}
