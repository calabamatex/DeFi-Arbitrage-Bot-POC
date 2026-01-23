// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title MockDEX
 * @notice Simple mock DEX for testing arbitrage
 * @dev Provides fixed exchange rates to create predictable arbitrage opportunities
 */
contract MockDEX {
    string public name;

    // Fixed exchange rate (token0 per token1, scaled by 1e18)
    uint256 public exchangeRate;

    constructor(string memory _name, uint256 _exchangeRate) {
        name = _name;
        exchangeRate = _exchangeRate; // e.g., 1.1e18 means 1.1 token0 per 1 token1
    }

    /**
     * @notice Swap tokenIn for tokenOut
     * @param tokenIn Input token address
     * @param tokenOut Output token address
     * @param amountIn Amount of input tokens
     * @return amountOut Amount of output tokens
     */
    function swap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn
    ) external returns (uint256 amountOut) {
        require(amountIn > 0, "Amount must be > 0");

        // Transfer tokens from sender
        IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);

        // Calculate output amount based on exchange rate
        // Simple: amountOut = amountIn * exchangeRate / 1e18
        amountOut = (amountIn * exchangeRate) / 1e18;

        // Transfer output tokens
        IERC20(tokenOut).transfer(msg.sender, amountOut);

        return amountOut;
    }

    /**
     * @notice Get quote for swap (view function, doesn't execute)
     * @param amountIn Amount of input tokens
     * @return amountOut Amount of output tokens that would be received
     */
    function getAmountOut(
        address, /* tokenIn */
        address, /* tokenOut */
        uint256 amountIn
    ) external view returns (uint256 amountOut) {
        amountOut = (amountIn * exchangeRate) / 1e18;
    }

    /**
     * @notice Fund this DEX with tokens for swaps
     */
    function fund(address token, uint256 amount) external {
        IERC20(token).transferFrom(msg.sender, address(this), amount);
    }

    /**
     * @notice Withdraw tokens (owner only for testing)
     */
    function withdraw(address token, uint256 amount) external {
        IERC20(token).transfer(msg.sender, amount);
    }
}
