// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IDEXAdapter
 * @notice Interface for DEX adapters (shared by FlashLoanArbitrageV2 and BalancerFlashLoan)
 */
interface IDEXAdapter {
    function swapDirect(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline,
        address recipient,
        bytes calldata data
    ) external returns (uint256 amountOut);
}
