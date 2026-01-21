// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

// Uniswap V3 interfaces
interface IUniswapV3Router {
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
}

// Uniswap V2 interfaces (SushiSwap, QuickSwap, etc.)
interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

/**
 * @title DEXLibrary
 * @notice Library for executing swaps across multiple DEX protocols
 * @dev Supports Uniswap V2/V3, SushiSwap, QuickSwap, and other forks
 */
library DEXLibrary {
    using SafeERC20 for IERC20;

    /// @notice DEX types
    enum DEXType {
        UNISWAP_V2,
        UNISWAP_V3,
        SUSHISWAP,
        QUICKSWAP,
        CURVE
    }

    /// @notice Standard Uniswap V3 fee tiers
    uint24 public constant FEE_LOW = 500; // 0.05%
    uint24 public constant FEE_MEDIUM = 3000; // 0.3%
    uint24 public constant FEE_HIGH = 10000; // 1%

    /**
     * @notice Execute swap on Uniswap V3
     * @param router Uniswap V3 router address
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount of input tokens
     * @param minAmountOut Minimum amount of output tokens
     * @param fee Pool fee tier (500, 3000, or 10000)
     * @param deadline Transaction deadline
     * @return amountOut Amount of output tokens received
     */
    function swapUniswapV3(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint24 fee,
        uint256 deadline
    ) internal returns (uint256 amountOut) {
        // Approve router
        IERC20(tokenIn).forceApprove(router, amountIn);

        // Prepare swap parameters
        IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router
            .ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: fee,
                recipient: address(this),
                deadline: deadline,
                amountIn: amountIn,
                amountOutMinimum: minAmountOut,
                sqrtPriceLimitX96: 0 // No price limit
            });

        // Execute swap
        amountOut = IUniswapV3Router(router).exactInputSingle(params);

        // Reset approval
        IERC20(tokenIn).forceApprove(router, 0);
    }

    /**
     * @notice Execute swap on Uniswap V2 or forks (SushiSwap, QuickSwap)
     * @param router Router address
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount of input tokens
     * @param minAmountOut Minimum amount of output tokens
     * @param deadline Transaction deadline
     * @return amountOut Amount of output tokens received
     */
    function swapUniswapV2(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline
    ) internal returns (uint256 amountOut) {
        // Approve router
        IERC20(tokenIn).forceApprove(router, amountIn);

        // Create swap path
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        // Execute swap
        uint256[] memory amounts = IUniswapV2Router(router).swapExactTokensForTokens(
            amountIn,
            minAmountOut,
            path,
            address(this),
            deadline
        );

        amountOut = amounts[amounts.length - 1];

        // Reset approval
        IERC20(tokenIn).forceApprove(router, 0);
    }

    /**
     * @notice Execute swap based on DEX type
     * @param dexType Type of DEX
     * @param router Router address
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount of input tokens
     * @param minAmountOut Minimum amount of output tokens
     * @param deadline Transaction deadline
     * @return amountOut Amount of output tokens received
     */
    function executeSwap(
        DEXType dexType,
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline
    ) internal returns (uint256 amountOut) {
        if (dexType == DEXType.UNISWAP_V3) {
            // Try medium fee tier first (most common)
            amountOut = swapUniswapV3(
                router,
                tokenIn,
                tokenOut,
                amountIn,
                minAmountOut,
                FEE_MEDIUM,
                deadline
            );
        } else if (
            dexType == DEXType.UNISWAP_V2 ||
            dexType == DEXType.SUSHISWAP ||
            dexType == DEXType.QUICKSWAP
        ) {
            amountOut = swapUniswapV2(
                router,
                tokenIn,
                tokenOut,
                amountIn,
                minAmountOut,
                deadline
            );
        } else {
            revert("Unsupported DEX type");
        }
    }

    /**
     * @notice Get expected output amount for a V2 swap (for simulation)
     * @param router Router address
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @return amountOut Expected output amount
     */
    function getAmountOutV2(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn
    ) internal view returns (uint256 amountOut) {
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256[] memory amounts = IUniswapV2Router(router).getAmountsOut(amountIn, path);
        amountOut = amounts[amounts.length - 1];
    }

    /**
     * @notice Calculate minimum amount with slippage protection
     * @param amount Expected amount
     * @param slippageBps Slippage in basis points (e.g., 100 = 1%)
     * @return minAmount Minimum acceptable amount
     */
    function calculateMinAmountOut(uint256 amount, uint256 slippageBps)
        internal
        pure
        returns (uint256 minAmount)
    {
        require(slippageBps <= 10000, "Invalid slippage");
        minAmount = (amount * (10000 - slippageBps)) / 10000;
    }

    /**
     * @notice Calculate price impact
     * @param amountIn Input amount
     * @param expectedOut Expected output (from reserves)
     * @param actualOut Actual output received
     * @return impactBps Price impact in basis points
     */
    function calculatePriceImpact(
        uint256 amountIn,
        uint256 expectedOut,
        uint256 actualOut
    ) internal pure returns (uint256 impactBps) {
        if (actualOut >= expectedOut) {
            return 0; // No negative impact
        }

        uint256 difference = expectedOut - actualOut;
        impactBps = (difference * 10000) / expectedOut;
    }
}
