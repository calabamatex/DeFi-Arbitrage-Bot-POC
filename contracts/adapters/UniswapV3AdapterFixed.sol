// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

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
}

/**
 * @title UniswapV3AdapterFixed
 * @notice Simple adapter with fixed fee tier (0.05%) for testing
 */
contract UniswapV3AdapterFixed {
    using SafeERC20 for IERC20;

    ISwapRouter public immutable swapRouter;
    uint24 public constant FEE = 500; // 0.05%

    constructor(address _swapRouter) {
        swapRouter = ISwapRouter(_swapRouter);
    }

    /**
     * @notice Swap tokens (matches IDEXAdapter interface)
     */
    function swapDirect(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline,
        address recipient
    ) external returns (uint256 amountOut) {
        // Approve router
        IERC20(tokenIn).forceApprove(address(swapRouter), amountIn);

        // Execute swap
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: FEE,
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
}
