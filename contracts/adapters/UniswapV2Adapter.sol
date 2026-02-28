// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

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
 * @dev Implements IDEXAdapter interface with access control (C-01, C-02)
 */
contract UniswapV2Adapter is Ownable2Step {
    using SafeERC20 for IERC20;

    /// @notice Authorized callers (e.g., FlashLoanArbitrageV2)
    mapping(address => bool) public authorized;

    /// @notice Router address
    IUniswapV2Router02 public immutable router;

    /// @notice DEX name for identification
    string public dexName;

    /// @notice Events
    event AuthorizedUpdated(address indexed account, bool status);

    /// @notice Errors
    error Unauthorized();

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert Unauthorized();
        _;
    }

    constructor(address _router, string memory _dexName) Ownable(msg.sender) {
        require(_router != address(0), "Invalid router");
        router = IUniswapV2Router02(_router);
        dexName = _dexName;
        authorized[msg.sender] = true;
    }

    /**
     * @notice Set authorized status for an address
     * @param account Address to authorize/deauthorize
     * @param status True to authorize, false to revoke
     */
    function setAuthorized(address account, bool status) external onlyOwner {
        require(account != address(0), "Invalid account");
        authorized[account] = status;
        emit AuthorizedUpdated(account, status);
    }

    /**
     * @notice Swap directly — matches IDEXAdapter interface
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param deadline Transaction deadline
     * @param recipient Recipient of output tokens
     * @param data Unused for V2 (kept for interface compatibility)
     * @return amountOut Amount received
     */
    function swapDirect(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline,
        address recipient,
        bytes calldata data
    ) external onlyAuthorized returns (uint256 amountOut) {
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
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256 smallAmount = amountIn / 100;
        if (smallAmount == 0) smallAmount = 1;

        uint256[] memory smallAmounts = router.getAmountsOut(smallAmount, path);
        uint256 baselinePrice = (smallAmounts[1] * 1e18) / smallAmount;

        uint256[] memory actualAmounts = router.getAmountsOut(amountIn, path);
        uint256 actualPrice = (actualAmounts[1] * 1e18) / amountIn;

        if (actualPrice >= baselinePrice) {
            return 0;
        }

        uint256 priceDiff = baselinePrice - actualPrice;
        priceImpactBps = (priceDiff * 10000) / baselinePrice;
    }
}
