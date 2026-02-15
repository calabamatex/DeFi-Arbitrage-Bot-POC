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
 * @title FlashLoanArbitrageV2
 * @notice Improved flash loan arbitrage contract with adapter pattern
 * @dev Uses DEX adapters for flexibility and cleaner code
 */
contract FlashLoanArbitrageV2 is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    /// @notice Aave V3 Pool Addresses Provider
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;

    /// @notice Aave V3 Pool
    IPool public immutable POOL;

    /// @notice Minimum profit required (in base token)
    uint256 public minProfit;

    /// @notice Maximum slippage allowed (in basis points)
    uint256 public maxSlippageBps;

    /// @notice Flash loan fee (0.05% = 5 bps)
    uint256 public constant FLASH_LOAN_FEE_BPS = 5;
    uint256 public constant BPS_DENOMINATOR = 10000;

    /// @notice Registered DEX adapters
    mapping(address => bool) public registeredAdapters;

    /// @notice Total profits earned (per token)
    mapping(address => uint256) public totalProfits;

    /// @notice Execution counter
    uint256 public executionCount;

    /**
     * @notice Swap step information
     * @param adapter DEX adapter address
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param minAmountOut Minimum output
     * @param data Extra data for adapter (e.g., fee tier for Uniswap V3)
     */
    struct SwapStep {
        address adapter;
        address tokenIn;
        address tokenOut;
        uint256 minAmountOut;
        bytes data;
    }

    /**
     * @notice Arbitrage parameters
     * @param steps Array of swap steps
     * @param flashLoanAmount Amount to borrow
     * @param flashLoanAsset Asset to borrow
     * @param minFinalAmount Minimum amount after all swaps
     * @param deadline Transaction deadline
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

    constructor(
        address _addressProvider,
        uint256 _minProfit,
        uint256 _maxSlippageBps
    ) Ownable(msg.sender) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressProvider);
        POOL = IPool(ADDRESSES_PROVIDER.getPool());
        minProfit = _minProfit;
        maxSlippageBps = _maxSlippageBps;
    }

    /**
     * @notice Execute flash loan arbitrage
     * @param params Arbitrage parameters
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

        // Validate all adapters are registered
        for (uint256 i = 0; i < params.steps.length; i++) {
            if (!registeredAdapters[params.steps[i].adapter]) {
                revert UnauthorizedAdapter(params.steps[i].adapter);
            }
        }

        // Encode params for flash loan callback
        bytes memory encodedParams = abi.encode(params);

        // Prepare flash loan arrays
        address[] memory assets = new address[](1);
        assets[0] = params.flashLoanAsset;

        uint256[] memory amounts = new uint256[](1);
        amounts[0] = params.flashLoanAmount;

        uint256[] memory modes = new uint256[](1);
        modes[0] = 0; // No debt

        // Execute flash loan
        POOL.flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            encodedParams,
            0
        );

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
     * @notice Aave V3 flash loan callback
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

        // Decode params
        ArbitrageParams memory arbParams = abi.decode(params, (ArbitrageParams));

        // Execute swaps
        uint256 currentAmount = amounts[0];
        address currentToken = assets[0];

        for (uint256 i = 0; i < arbParams.steps.length; i++) {
            SwapStep memory step = arbParams.steps[i];

            // Record balance before swap for verification
            uint256 balanceBefore = IERC20(step.tokenOut).balanceOf(address(this));

            // Transfer tokens to adapter
            IERC20(step.tokenIn).safeTransfer(step.adapter, currentAmount);

            // Execute swap (pass step.data for adapter-specific params like V3 fee tier)
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
            returns (uint256 amountOut) {
                // Verify actual balance change matches reported amountOut (C-04)
                uint256 balanceAfter = IERC20(step.tokenOut).balanceOf(address(this));
                uint256 actualReceived = balanceAfter - balanceBefore;
                require(actualReceived >= step.minAmountOut, "Balance verification failed");

                currentAmount = actualReceived; // Use actual received, not adapter's claim
                currentToken = step.tokenOut;
            } catch {
                revert SwapFailed(i);
            }
        }

        // Verify we ended with the flash loan asset
        require(currentToken == assets[0], "Invalid path: must return to start token");

        // Calculate repayment
        uint256 amountOwed = amounts[0] + premiums[0];

        // Check final amount
        require(currentAmount >= arbParams.minFinalAmount, "Slippage check failed");

        // Check profit
        if (currentAmount <= amountOwed) {
            revert InsufficientProfit(0, minProfit);
        }

        uint256 profit = currentAmount - amountOwed;
        if (profit < minProfit) {
            revert InsufficientProfit(profit, minProfit);
        }

        // Track profit
        totalProfits[assets[0]] += profit;

        // Approve repayment
        IERC20(assets[0]).forceApprove(address(POOL), amountOwed);

        return true;
    }

    /**
     * @notice Register or unregister a DEX adapter
     * @param adapter Adapter address
     * @param status True to register, false to unregister
     */
    function setAdapter(address adapter, bool status) external onlyOwner {
        registeredAdapters[adapter] = status;
        emit AdapterRegistered(adapter, status);
    }

    /**
     * @notice Update minimum profit
     * @param _minProfit New minimum profit
     */
    function setMinProfit(uint256 _minProfit) external onlyOwner {
        uint256 oldValue = minProfit;
        minProfit = _minProfit;
        emit MinProfitUpdated(oldValue, _minProfit);
    }

    /**
     * @notice Update maximum slippage
     * @param _maxSlippageBps New max slippage in bps
     */
    function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
        require(_maxSlippageBps <= 1000, "Slippage too high");
        maxSlippageBps = _maxSlippageBps;
    }

    /**
     * @notice Pause contract
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
     * @notice Withdraw profits
     * @param token Token to withdraw
     * @param amount Amount to withdraw
     * @param to Recipient
     */
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

    /**
     * @notice Emergency withdrawal
     * @param token Token to withdraw
     * @param amount Amount
     * @param to Recipient
     */
    function emergencyWithdraw(
        address token,
        uint256 amount,
        address to
    ) external onlyOwner nonReentrant {
        IERC20(token).safeTransfer(to, amount);
    }

    /**
     * @notice Get token balance
     * @param token Token address
     * @return Balance
     */
    function getBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }

    /**
     * @notice Estimate flash loan fee
     * @param amount Loan amount
     * @return fee Fee amount
     */
    function estimateFlashLoanFee(uint256 amount) external pure returns (uint256 fee) {
        fee = (amount * FLASH_LOAN_FEE_BPS) / BPS_DENOMINATOR;
    }
}
