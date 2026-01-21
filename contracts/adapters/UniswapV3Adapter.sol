// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title ISwapRouter
 * @notice Uniswap V3 Router interface
 */
interface ISwapRouter {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }

    function exactInputSingle(ExactInputSingleParams calldata params)
        external
        payable
        returns (uint256 amountOut);

    struct ExactInputParams {
        bytes path;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
    }

    function exactInput(ExactInputParams calldata params)
        external
        payable
        returns (uint256 amountOut);
}

/**
 * @title IQuoterV2
 * @notice Uniswap V3 Quoter interface for price quotes
 */
interface IQuoterV2 {
    function quoteExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint160 sqrtPriceLimitX96
    ) external returns (uint256 amountOut);
}

/**
 * @title UniswapV3Adapter
 * @notice Adapter for executing swaps on Uniswap V3
 */
contract UniswapV3Adapter {
    using SafeERC20 for IERC20;

    /// @notice Uniswap V3 Router address
    ISwapRouter public immutable swapRouter;

    /// @notice Uniswap V3 Quoter address
    IQuoterV2 public immutable quoter;

    /// @notice Fee tiers
    uint24 public constant FEE_LOW = 500; // 0.05%
    uint24 public constant FEE_MEDIUM = 3000; // 0.3%
    uint24 public constant FEE_HIGH = 10000; // 1%

    constructor(address _swapRouter, address _quoter) {
        swapRouter = ISwapRouter(_swapRouter);
        quoter = IQuoterV2(_quoter);
    }

    /**
     * @notice Execute a swap on Uniswap V3
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output amount
     * @param fee Pool fee tier
     * @param deadline Transaction deadline
     * @return amountOut Amount received
     */
    function swap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint24 fee,
        uint256 deadline
    ) external returns (uint256 amountOut) {
        // Transfer tokens from caller
        IERC20(tokenIn).safeTransferFrom(msg.sender, address(this), amountIn);

        // Approve router
        IERC20(tokenIn).forceApprove(address(swapRouter), amountIn);

        // Execute swap
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: fee,
            recipient: msg.sender,
            deadline: deadline,
            amountIn: amountIn,
            amountOutMinimum: minAmountOut,
            sqrtPriceLimitX96: 0
        });

        amountOut = swapRouter.exactInputSingle(params);

        // Reset approval
        IERC20(tokenIn).forceApprove(address(swapRouter), 0);
    }

    /**
     * @notice Swap directly (called from main contract that already has tokens)
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param fee Pool fee
     * @param deadline Deadline
     * @param recipient Recipient of output tokens
     * @return amountOut Amount received
     */
    function swapDirect(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint24 fee,
        uint256 deadline,
        address recipient
    ) external returns (uint256 amountOut) {
        // Caller should have already transferred tokens to this contract

        // Approve router
        IERC20(tokenIn).forceApprove(address(swapRouter), amountIn);

        // Execute swap
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: fee,
            recipient: recipient,
            deadline: deadline,
            amountIn: amountIn,
            amountOutMinimum: minAmountOut,
            sqrtPriceLimitX96: 0
        });

        amountOut = swapRouter.exactInputSingle(params);

        // Reset approval
        IERC20(tokenIn).forceApprove(address(swapRouter), 0);
    }

    /**
     * @notice Get quote for a swap
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @param fee Pool fee
     * @return amountOut Expected output amount
     */
    function getQuote(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint24 fee
    ) external returns (uint256 amountOut) {
        return quoter.quoteExactInputSingle(tokenIn, tokenOut, fee, amountIn, 0);
    }

    /**
     * @notice Try to find best fee tier for a swap
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @return bestFee Best fee tier
     * @return bestAmountOut Best output amount
     */
    function findBestFee(
        address tokenIn,
        address tokenOut,
        uint256 amountIn
    ) external returns (uint24 bestFee, uint256 bestAmountOut) {
        uint24[3] memory fees = [FEE_LOW, FEE_MEDIUM, FEE_HIGH];
        bestAmountOut = 0;
        bestFee = FEE_MEDIUM; // Default

        for (uint256 i = 0; i < fees.length; i++) {
            try quoter.quoteExactInputSingle(tokenIn, tokenOut, fees[i], amountIn, 0) returns (
                uint256 amountOut
            ) {
                if (amountOut > bestAmountOut) {
                    bestAmountOut = amountOut;
                    bestFee = fees[i];
                }
            } catch {
                // Pool doesn't exist for this fee tier, continue
                continue;
            }
        }
    }
}
