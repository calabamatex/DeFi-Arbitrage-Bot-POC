// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title IUniswapV2Router02
 * @notice Uniswap V2 Router interface (also works for SushiSwap, QuickSwap, etc.)
 */
interface IUniswapV2Router02 {
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

    function getAmountsIn(uint256 amountOut, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

/**
 * @title UniswapV2Adapter
 * @notice Adapter for executing swaps on Uniswap V2 and forks (SushiSwap, QuickSwap)
 */
contract UniswapV2Adapter {
    using SafeERC20 for IERC20;

    /// @notice Router address
    IUniswapV2Router02 public immutable router;

    /// @notice DEX name for identification
    string public dexName;

    constructor(address _router, string memory _dexName) {
        router = IUniswapV2Router02(_router);
        dexName = _dexName;
    }

    /**
     * @notice Execute a swap on Uniswap V2
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output amount
     * @param deadline Transaction deadline
     * @return amountOut Amount received
     */
    function swap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline
    ) external returns (uint256 amountOut) {
        // Transfer tokens from caller
        IERC20(tokenIn).safeTransferFrom(msg.sender, address(this), amountIn);

        // Approve router
        IERC20(tokenIn).forceApprove(address(router), amountIn);

        // Create path
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        // Execute swap
        uint256[] memory amounts = router.swapExactTokensForTokens(
            amountIn,
            minAmountOut,
            path,
            msg.sender,
            deadline
        );

        amountOut = amounts[amounts.length - 1];

        // Reset approval
        IERC20(tokenIn).forceApprove(address(router), 0);
    }

    /**
     * @notice Swap directly (called from main contract that already has tokens)
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param deadline Deadline
     * @param recipient Recipient of output tokens
     * @return amountOut Amount received
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
        IERC20(tokenIn).forceApprove(address(router), amountIn);

        // Create path
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        // Execute swap
        uint256[] memory amounts = router.swapExactTokensForTokens(
            amountIn,
            minAmountOut,
            path,
            recipient,
            deadline
        );

        amountOut = amounts[amounts.length - 1];

        // Reset approval
        IERC20(tokenIn).forceApprove(address(router), 0);
    }

    /**
     * @notice Swap with multi-hop path
     * @param path Token path (e.g., [USDC, WETH, DAI])
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param deadline Deadline
     * @param recipient Recipient
     * @return amountOut Amount received
     */
    function swapMultiHop(
        address[] memory path,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline,
        address recipient
    ) external returns (uint256 amountOut) {
        require(path.length >= 2, "Invalid path");

        // Approve router
        IERC20(path[0]).forceApprove(address(router), amountIn);

        // Execute swap
        uint256[] memory amounts = router.swapExactTokensForTokens(
            amountIn,
            minAmountOut,
            path,
            recipient,
            deadline
        );

        amountOut = amounts[amounts.length - 1];

        // Reset approval
        IERC20(path[0]).forceApprove(address(router), 0);
    }

    /**
     * @notice Get quote for a swap
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @return amountOut Expected output amount
     */
    function getQuote(
        address tokenIn,
        address tokenOut,
        uint256 amountIn
    ) external view returns (uint256 amountOut) {
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256[] memory amounts = router.getAmountsOut(amountIn, path);
        amountOut = amounts[amounts.length - 1];
    }

    /**
     * @notice Get quote for multi-hop swap
     * @param path Token path
     * @param amountIn Input amount
     * @return amountOut Expected output amount
     */
    function getQuoteMultiHop(address[] memory path, uint256 amountIn)
        external
        view
        returns (uint256 amountOut)
    {
        require(path.length >= 2, "Invalid path");

        uint256[] memory amounts = router.getAmountsOut(amountIn, path);
        amountOut = amounts[amounts.length - 1];
    }

    /**
     * @notice Calculate price impact
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @return priceImpactBps Price impact in basis points
     */
    function calculatePriceImpact(
        address tokenIn,
        address tokenOut,
        uint256 amountIn
    ) external view returns (uint256 priceImpactBps) {
        // Get quote for small amount (for baseline price)
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256 smallAmount = amountIn / 100; // 1% of amount
        if (smallAmount == 0) smallAmount = 1;

        uint256[] memory smallAmounts = router.getAmountsOut(smallAmount, path);
        uint256 baselinePrice = (smallAmounts[1] * 1e18) / smallAmount;

        // Get quote for actual amount
        uint256[] memory actualAmounts = router.getAmountsOut(amountIn, path);
        uint256 actualPrice = (actualAmounts[1] * 1e18) / amountIn;

        // Calculate impact
        if (actualPrice >= baselinePrice) {
            return 0; // No negative impact
        }

        uint256 priceDiff = baselinePrice - actualPrice;
        priceImpactBps = (priceDiff * 10000) / baselinePrice;
    }
}
