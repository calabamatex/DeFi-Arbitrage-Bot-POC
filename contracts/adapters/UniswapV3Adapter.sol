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
}

/**
 * @title IQuoterV2
 * @notice Uniswap V3 QuoterV2 interface (struct-based, matches deployed contract)
 */
interface IQuoterV2 {
    struct QuoteExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint256 amountIn;
        uint24 fee;
        uint160 sqrtPriceLimitX96;
    }

    function quoteExactInputSingle(QuoteExactInputSingleParams calldata params)
        external
        returns (
            uint256 amountOut,
            uint160 sqrtPriceX96After,
            uint32 initializedTicksCrossed,
            uint256 gasEstimate
        );
}

/**
 * @title UniswapV3Adapter
 * @notice Adapter for executing swaps on Uniswap V3
 * @dev Implements IDEXAdapter interface with access control (C-01, C-02)
 */
contract UniswapV3Adapter {
    using SafeERC20 for IERC20;

    /// @notice Contract owner
    address public owner;

    /// @notice Authorized callers (e.g., FlashLoanArbitrageV2)
    mapping(address => bool) public authorized;

    /// @notice Uniswap V3 Router address
    ISwapRouter public immutable swapRouter;

    /// @notice Uniswap V3 Quoter address
    IQuoterV2 public immutable quoter;

    /// @notice Fee tiers
    uint24 public constant FEE_LOW = 500;    // 0.05%
    uint24 public constant FEE_MEDIUM = 3000; // 0.3%
    uint24 public constant FEE_HIGH = 10000;  // 1%

    /// @notice Events
    event AuthorizedUpdated(address indexed account, bool status);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    /// @notice Errors
    error Unauthorized();
    error InvalidFee(uint24 fee);
    error InvalidDataLength();

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert Unauthorized();
        _;
    }

    constructor(address _swapRouter, address _quoter) {
        swapRouter = ISwapRouter(_swapRouter);
        quoter = IQuoterV2(_quoter);
        owner = msg.sender;
        authorized[msg.sender] = true;
    }

    /**
     * @notice Set authorized status for an address
     * @param account Address to authorize/deauthorize
     * @param status True to authorize, false to revoke
     */
    function setAuthorized(address account, bool status) external onlyOwner {
        authorized[account] = status;
        emit AuthorizedUpdated(account, status);
    }

    /**
     * @notice Transfer ownership
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /**
     * @notice Swap directly — matches IDEXAdapter interface
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param deadline Transaction deadline
     * @param recipient Recipient of output tokens
     * @param data ABI-encoded uint24 fee tier
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
        // Decode fee from data
        if (data.length < 32) revert InvalidDataLength();
        uint24 fee = abi.decode(data, (uint24));

        // Validate fee tier
        if (fee != FEE_LOW && fee != FEE_MEDIUM && fee != FEE_HIGH) {
            revert InvalidFee(fee);
        }

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
        IQuoterV2.QuoteExactInputSingleParams memory params = IQuoterV2.QuoteExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            amountIn: amountIn,
            fee: fee,
            sqrtPriceLimitX96: 0
        });
        (amountOut,,,) = quoter.quoteExactInputSingle(params);
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
            IQuoterV2.QuoteExactInputSingleParams memory params = IQuoterV2.QuoteExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                amountIn: amountIn,
                fee: fees[i],
                sqrtPriceLimitX96: 0
            });
            try quoter.quoteExactInputSingle(params) returns (
                uint256 amountOut, uint160, uint32, uint256
            ) {
                if (amountOut > bestAmountOut) {
                    bestAmountOut = amountOut;
                    bestFee = fees[i];
                }
            } catch {
                continue;
            }
        }
    }
}
