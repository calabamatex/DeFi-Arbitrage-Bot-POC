// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

/**
 * @title ICurvePool
 * @notice Minimal Curve StableSwap pool interface
 */
interface ICurvePool {
    function exchange(
        int128 i,
        int128 j,
        uint256 dx,
        uint256 min_dy
    ) external returns (uint256);

    function get_dy(
        int128 i,
        int128 j,
        uint256 dx
    ) external view returns (uint256);
}

/**
 * @title CurveAdapter
 * @notice Adapter for executing swaps on Curve StableSwap pools
 * @dev Implements IDEXAdapter interface with access control and pool registry
 */
contract CurveAdapter is Ownable2Step {
    using SafeERC20 for IERC20;

    /// @notice Authorized callers (e.g., FlashLoanArbitrageV2)
    mapping(address => bool) public authorized;

    /// @notice Pool registry: keccak256(tokenA, tokenB) -> PoolInfo
    struct PoolInfo {
        address pool;
        int128 indexA;
        int128 indexB;
    }

    /// @notice Mapping from token pair hash to pool info
    mapping(bytes32 => PoolInfo) public poolRegistry;

    /// @notice Events
    event AuthorizedUpdated(address indexed account, bool status);
    event PoolRegistered(address indexed pool, address tokenA, address tokenB, int128 indexA, int128 indexB);

    /// @notice Errors
    error Unauthorized();
    error PoolNotRegistered(address tokenIn, address tokenOut);

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert Unauthorized();
        _;
    }

    constructor() Ownable(msg.sender) {
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
     * @notice Register a Curve pool for a token pair
     * @param pool Curve pool address
     * @param tokenA First token address
     * @param tokenB Second token address
     * @param indexA Curve pool index for tokenA
     * @param indexB Curve pool index for tokenB
     */
    function registerPool(
        address pool,
        address tokenA,
        address tokenB,
        int128 indexA,
        int128 indexB
    ) external onlyOwner {
        require(pool != address(0), "Invalid pool");
        require(tokenA != address(0) && tokenB != address(0), "Invalid token");

        // Register both directions
        bytes32 keyAB = _pairKey(tokenA, tokenB);
        poolRegistry[keyAB] = PoolInfo(pool, indexA, indexB);

        bytes32 keyBA = _pairKey(tokenB, tokenA);
        poolRegistry[keyBA] = PoolInfo(pool, indexB, indexA);

        emit PoolRegistered(pool, tokenA, tokenB, indexA, indexB);
    }

    /**
     * @notice Swap directly — matches IDEXAdapter interface
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output
     * @param deadline Transaction deadline
     * @param recipient Recipient of output tokens
     * @param data Unused for Curve (kept for interface compatibility)
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
        require(block.timestamp <= deadline, "Deadline expired");

        PoolInfo memory info = _getPool(tokenIn, tokenOut);

        // Approve pool
        IERC20(tokenIn).forceApprove(info.pool, amountIn);

        // Execute swap
        amountOut = ICurvePool(info.pool).exchange(
            info.indexA,
            info.indexB,
            amountIn,
            minAmountOut
        );

        // Transfer output to recipient
        if (recipient != address(this)) {
            IERC20(tokenOut).safeTransfer(recipient, amountOut);
        }

        // Reset approval
        IERC20(tokenIn).forceApprove(info.pool, 0);
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
        PoolInfo memory info = _getPool(tokenIn, tokenOut);
        amountOut = ICurvePool(info.pool).get_dy(info.indexA, info.indexB, amountIn);
    }

    /**
     * @notice Check if a pool is registered for a token pair
     */
    function hasPool(address tokenIn, address tokenOut) external view returns (bool) {
        bytes32 key = _pairKey(tokenIn, tokenOut);
        return poolRegistry[key].pool != address(0);
    }

    // ------------------------------------------------------------------
    // Internal
    // ------------------------------------------------------------------

    function _pairKey(address a, address b) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(a, b));
    }

    function _getPool(address tokenIn, address tokenOut) internal view returns (PoolInfo memory info) {
        bytes32 key = _pairKey(tokenIn, tokenOut);
        info = poolRegistry[key];
        if (info.pool == address(0)) {
            revert PoolNotRegistered(tokenIn, tokenOut);
        }
    }
}
