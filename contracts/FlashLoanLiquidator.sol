// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IPoolAddressesProvider} from "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import {IPool} from "@aave/core-v3/contracts/interfaces/IPool.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {IDEXAdapter} from "./interfaces/IDEXAdapter.sol";

/**
 * @title FlashLoanLiquidator
 * @notice Executes profitable liquidations using Aave V3 flash loans.
 *
 * Flow:
 * 1. Flash loan the debt token
 * 2. Call IPool.liquidationCall() to repay user's debt and receive collateral
 * 3. Swap collateral → debt token via DEX adapter
 * 4. Repay flash loan, keep profit (liquidation bonus minus fees)
 */
contract FlashLoanLiquidator is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    /// @notice Aave V3 Pool
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    IPool public immutable POOL;

    /// @notice Minimum profit required
    uint256 public minProfit;

    /// @notice Flash loan fee (0.05% = 5 bps)
    uint256 public constant FLASH_LOAN_FEE_BPS = 5;
    uint256 public constant BPS_DENOMINATOR = 10000;

    /// @notice Registered DEX adapters
    mapping(address => bool) public registeredAdapters;

    /// @notice Total liquidation profits (per token)
    mapping(address => uint256) public totalProfits;

    /// @notice Execution counter
    uint256 public liquidationCount;

    /**
     * @notice Liquidation parameters
     * @param collateralAsset The collateral token to receive
     * @param debtAsset The debt token to repay
     * @param user The borrower to liquidate
     * @param debtToCover Amount of debt to cover
     * @param adapter DEX adapter for collateral → debt swap
     * @param swapData Extra data for adapter (e.g., V3 fee tier)
     * @param minProfit Minimum profit after all fees
     * @param deadline Transaction deadline
     */
    struct LiquidationParams {
        address collateralAsset;
        address debtAsset;
        address user;
        uint256 debtToCover;
        address adapter;
        bytes swapData;
        uint256 minProfit;
        uint256 deadline;
    }

    /// @notice Events
    event LiquidationExecuted(
        address indexed user,
        address indexed debtAsset,
        address indexed collateralAsset,
        uint256 debtCovered,
        uint256 collateralReceived,
        uint256 profit,
        uint256 gasUsed
    );
    event AdapterRegistered(address indexed adapter, bool status);
    event MinProfitUpdated(uint256 oldValue, uint256 newValue);

    /// @notice Errors
    error UnauthorizedAdapter(address adapter);
    error InsufficientProfit(uint256 actual, uint256 required);
    error DeadlineExpired();
    error LiquidationFailed();
    error SwapFailed();

    constructor(
        address _addressProvider,
        uint256 _minProfit
    ) Ownable(msg.sender) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressProvider);
        POOL = IPool(ADDRESSES_PROVIDER.getPool());
        minProfit = _minProfit;
    }

    /**
     * @notice Execute a flash-loan-powered liquidation
     */
    function executeLiquidation(LiquidationParams calldata params)
        external
        onlyOwner
        nonReentrant
        whenNotPaused
    {
        uint256 gasStart = gasleft();

        if (block.timestamp > params.deadline) revert DeadlineExpired();
        if (!registeredAdapters[params.adapter]) revert UnauthorizedAdapter(params.adapter);

        // Encode params for callback
        bytes memory encodedParams = abi.encode(params);

        // Flash loan the debt token
        address[] memory assets = new address[](1);
        assets[0] = params.debtAsset;
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = params.debtToCover;
        uint256[] memory modes = new uint256[](1);
        modes[0] = 0; // No debt

        POOL.flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            encodedParams,
            0
        );

        liquidationCount++;

        uint256 gasUsed = gasStart - gasleft();
        emit LiquidationExecuted(
            params.user,
            params.debtAsset,
            params.collateralAsset,
            params.debtToCover,
            0, // filled in callback
            totalProfits[params.debtAsset],
            gasUsed
        );
    }

    /**
     * @notice Aave flash loan callback
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        require(msg.sender == address(POOL), "Caller must be Pool");
        require(initiator == address(this), "Initiator must be this");

        LiquidationParams memory liqParams = abi.decode(params, (LiquidationParams));

        // 1. Approve Pool to spend the debt token for liquidation
        IERC20(liqParams.debtAsset).forceApprove(address(POOL), liqParams.debtToCover);

        // 2. Execute liquidation — receive collateral
        uint256 collateralBefore = IERC20(liqParams.collateralAsset).balanceOf(address(this));

        // liquidationCall(collateral, debt, user, debtToCover, receiveAToken=false)
        POOL.liquidationCall(
            liqParams.collateralAsset,
            liqParams.debtAsset,
            liqParams.user,
            liqParams.debtToCover,
            false // receive underlying, not aToken
        );

        uint256 collateralReceived = IERC20(liqParams.collateralAsset).balanceOf(address(this)) - collateralBefore;
        if (collateralReceived == 0) revert LiquidationFailed();

        // 3. Swap collateral → debt token via adapter
        IERC20(liqParams.collateralAsset).safeTransfer(liqParams.adapter, collateralReceived);

        uint256 debtBefore = IERC20(liqParams.debtAsset).balanceOf(address(this));

        try IDEXAdapter(liqParams.adapter).swapDirect(
            liqParams.collateralAsset,
            liqParams.debtAsset,
            collateralReceived,
            0, // min out — we check profit below
            liqParams.deadline,
            address(this),
            liqParams.swapData
        ) returns (uint256) {
            // ok
        } catch {
            revert SwapFailed();
        }

        uint256 swapReceived = IERC20(liqParams.debtAsset).balanceOf(address(this)) - debtBefore;

        // 4. Calculate repayment and profit
        uint256 amountOwed = amounts[0] + premiums[0];

        if (swapReceived + amounts[0] <= amountOwed) {
            // amounts[0] was the flash loan we still hold (minus what was spent on liquidation)
            // Actually we spent amounts[0] on liquidation, got collateral, swapped to debt token
            // Current debt token balance = swapReceived + whatever was left
            revert InsufficientProfit(0, liqParams.minProfit);
        }

        // Total debt token we have = original balance (0 pre-flash) + flash loan + swapReceived
        // We spent debtToCover on liquidation, so available = amounts[0] - debtToCover + swapReceived
        // But debtToCover == amounts[0], so available = swapReceived
        // Actually the flash loan gave us amounts[0], we approved & liquidation took debtToCover from us.
        // debtToCover == amounts[0]. So after liquidation we have 0 debt tokens.
        // After swap we have swapReceived debt tokens.
        // We need to repay amountOwed = amounts[0] + premiums[0].

        if (swapReceived < amountOwed) {
            revert InsufficientProfit(0, liqParams.minProfit);
        }

        uint256 profit = swapReceived - amountOwed;
        if (profit < liqParams.minProfit) {
            revert InsufficientProfit(profit, liqParams.minProfit);
        }

        // Track profit
        totalProfits[liqParams.debtAsset] += profit;

        // Approve repayment
        IERC20(assets[0]).forceApprove(address(POOL), amountOwed);

        return true;
    }

    // ------------------------------------------------------------------
    // Admin
    // ------------------------------------------------------------------

    function setAdapter(address adapter, bool status) external onlyOwner {
        registeredAdapters[adapter] = status;
        emit AdapterRegistered(adapter, status);
    }

    function setMinProfit(uint256 _minProfit) external onlyOwner {
        uint256 oldValue = minProfit;
        minProfit = _minProfit;
        emit MinProfitUpdated(oldValue, _minProfit);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function withdrawProfits(address token, uint256 amount, address to) external onlyOwner nonReentrant {
        require(amount <= totalProfits[token], "Insufficient profits");
        totalProfits[token] -= amount;
        IERC20(token).safeTransfer(to, amount);
    }

    function emergencyWithdraw(address token, uint256 amount, address to) external onlyOwner nonReentrant {
        IERC20(token).safeTransfer(to, amount);
    }

    function getBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }
}
