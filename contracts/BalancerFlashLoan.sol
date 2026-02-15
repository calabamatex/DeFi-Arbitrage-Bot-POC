// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title IBalancerVault
 * @notice Balancer V2 Vault flash loan interface
 */
interface IBalancerVault {
    function flashLoan(
        address recipient,
        IERC20[] calldata tokens,
        uint256[] calldata amounts,
        bytes calldata userData
    ) external;
}

/**
 * @title IFlashLoanRecipient
 * @notice Balancer V2 flash loan callback interface
 */
interface IFlashLoanRecipient {
    function receiveFlashLoan(
        IERC20[] calldata tokens,
        uint256[] calldata amounts,
        uint256[] calldata feeAmounts,
        bytes calldata userData
    ) external;
}

import {IDEXAdapter} from "./interfaces/IDEXAdapter.sol";

/**
 * @title BalancerFlashLoan
 * @notice Arbitrage contract using Balancer V2 flash loans (0% fee)
 * @dev Mirrors FlashLoanArbitrageV2 interface but uses Balancer callback.
 *      Key difference: Balancer charges 0% fee vs Aave's 0.05%.
 *      Repayment is via safeTransfer to vault (not approve).
 */
contract BalancerFlashLoan is IFlashLoanRecipient, Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    /// @notice Balancer V2 Vault (same address on all chains)
    IBalancerVault public immutable VAULT;

    /// @notice Minimum profit required (in base token)
    uint256 public minProfit;

    /// @notice Maximum slippage allowed (in basis points)
    uint256 public maxSlippageBps;

    /// @notice Registered DEX adapters
    mapping(address => bool) public registeredAdapters;

    /// @notice Total profits earned (per token)
    mapping(address => uint256) public totalProfits;

    /// @notice Execution counter
    uint256 public executionCount;

    /**
     * @notice Swap step (same struct as FlashLoanArbitrageV2)
     */
    struct SwapStep {
        address adapter;
        address tokenIn;
        address tokenOut;
        uint256 minAmountOut;
        bytes data;
    }

    /**
     * @notice Arbitrage parameters (same struct as FlashLoanArbitrageV2)
     */
    struct ArbitrageParams {
        SwapStep[] steps;
        uint256 flashLoanAmount;
        address flashLoanAsset;
        uint256 minFinalAmount;
        uint256 deadline;
    }

    /// @notice Events
    event ArbitrageExecuted(
        address indexed token,
        uint256 amountBorrowed,
        uint256 profit,
        uint256 gasUsed
    );
    event AdapterRegistered(address indexed adapter, bool status);
    event MinProfitUpdated(uint256 oldValue, uint256 newValue);
    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);

    /// @notice Errors
    error UnauthorizedAdapter(address adapter);
    error InsufficientProfit(uint256 actual, uint256 required);
    error DeadlineExpired();
    error InvalidPath();
    error SwapFailed(uint256 stepIndex);
    error UnauthorizedCaller();

    constructor(
        address _vault,
        uint256 _minProfit,
        uint256 _maxSlippageBps
    ) Ownable(msg.sender) {
        VAULT = IBalancerVault(_vault);
        minProfit = _minProfit;
        maxSlippageBps = _maxSlippageBps;
    }

    /**
     * @notice Execute flash loan arbitrage via Balancer (0% fee)
     * @param params Arbitrage parameters (same format as FlashLoanArbitrageV2)
     */
    function executeArbitrage(ArbitrageParams calldata params)
        external
        onlyOwner
        nonReentrant
        whenNotPaused
    {
        uint256 gasStart = gasleft();

        if (block.timestamp > params.deadline) revert DeadlineExpired();
        if (params.steps.length == 0) revert InvalidPath();

        // Validate all adapters
        for (uint256 i = 0; i < params.steps.length; i++) {
            if (!registeredAdapters[params.steps[i].adapter]) {
                revert UnauthorizedAdapter(params.steps[i].adapter);
            }
        }

        // Prepare Balancer flash loan arrays
        IERC20[] memory tokens = new IERC20[](1);
        tokens[0] = IERC20(params.flashLoanAsset);

        uint256[] memory amounts = new uint256[](1);
        amounts[0] = params.flashLoanAmount;

        // Encode params for callback
        bytes memory userData = abi.encode(params);

        // Execute Balancer flash loan
        VAULT.flashLoan(address(this), tokens, amounts, userData);

        executionCount++;

        uint256 gasUsed = gasStart - gasleft();
        emit ArbitrageExecuted(
            params.flashLoanAsset,
            params.flashLoanAmount,
            totalProfits[params.flashLoanAsset],
            gasUsed
        );
    }

    /**
     * @notice Balancer V2 flash loan callback
     * @dev Called by the Vault during flashLoan. Must repay via transfer.
     */
    function receiveFlashLoan(
        IERC20[] calldata tokens,
        uint256[] calldata amounts,
        uint256[] calldata feeAmounts,
        bytes calldata userData
    ) external override {
        if (msg.sender != address(VAULT)) revert UnauthorizedCaller();

        // Decode params
        ArbitrageParams memory arbParams = abi.decode(userData, (ArbitrageParams));

        // Execute swaps
        uint256 currentAmount = amounts[0];
        address currentToken = address(tokens[0]);

        for (uint256 i = 0; i < arbParams.steps.length; i++) {
            SwapStep memory step = arbParams.steps[i];

            uint256 balanceBefore = IERC20(step.tokenOut).balanceOf(address(this));

            // Transfer tokens to adapter
            IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);

            // Execute swap
            try
                IDEXAdapter(step.adapter).swapDirect(
                    step.tokenIn,
                    step.tokenOut,
                    currentAmount,
                    step.minAmountOut,
                    arbParams.deadline,
                    address(this),
                    step.data
                )
            returns (uint256) {
                uint256 balanceAfter = IERC20(step.tokenOut).balanceOf(address(this));
                uint256 actualReceived = balanceAfter - balanceBefore;
                require(actualReceived >= step.minAmountOut, "Balance verification failed");

                currentAmount = actualReceived;
                currentToken = step.tokenOut;
            } catch {
                revert SwapFailed(i);
            }
        }

        // Verify we ended with the flash loan asset
        require(currentToken == address(tokens[0]), "Invalid path: must return to start token");

        // Balancer fee is 0, but honor feeAmounts in case it changes
        uint256 amountOwed = amounts[0] + feeAmounts[0];

        // Check profit
        require(currentAmount >= arbParams.minFinalAmount, "Slippage check failed");

        if (currentAmount <= amountOwed) {
            revert InsufficientProfit(0, minProfit);
        }

        uint256 profit = currentAmount - amountOwed;
        if (profit < minProfit) {
            revert InsufficientProfit(profit, minProfit);
        }

        // Track profit
        totalProfits[address(tokens[0])] += profit;

        // Repay Balancer: transfer amount + fee back to Vault
        IERC20(address(tokens[0])).safeTransfer(address(VAULT), amountOwed);
    }

    // ------------------------------------------------------------------
    // Admin functions (identical to FlashLoanArbitrageV2)
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

    function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
        require(_maxSlippageBps <= 1000, "Slippage too high");
        maxSlippageBps = _maxSlippageBps;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function withdrawProfits(
        address token,
        uint256 amount,
        address to
    ) external onlyOwner nonReentrant {
        require(amount <= totalProfits[token], "Insufficient profits");
        totalProfits[token] -= amount;
        IERC20(token).safeTransfer(to, amount);
        emit ProfitWithdrawn(token, amount, to);
    }

    function emergencyWithdraw(
        address token,
        uint256 amount,
        address to
    ) external onlyOwner nonReentrant {
        IERC20(token).safeTransfer(to, amount);
    }

    function getBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }
}
