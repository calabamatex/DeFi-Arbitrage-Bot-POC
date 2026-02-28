// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IPoolAddressesProvider} from "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import {IPool} from "@aave/core-v3/contracts/interfaces/IPool.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title FlashLoanArbitrage
 * @notice Advanced flash loan arbitrage contract supporting multiple DEXes
 * @dev Executes triangular and multi-hop arbitrage using Aave V3 flash loans
 *
 * Security Features:
 * - Owner-only execution control
 * - Reentrancy protection
 * - Emergency pause functionality
 * - Minimum profit enforcement
 * - Slippage protection
 * - Whitelisted DEX routers
 */
contract FlashLoanArbitrage is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    /// @notice Aave V3 Pool Addresses Provider
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;

    /// @notice Aave V3 Pool
    IPool public immutable POOL;

    /// @notice Minimum profit required to execute arbitrage (in USD with 18 decimals)
    uint256 public minProfitUSD;

    /// @notice Maximum slippage allowed (in basis points, e.g., 200 = 2%)
    uint256 public maxSlippageBps;

    /// @notice Flash loan fee (Aave V3 is 0.05% = 5 basis points)
    uint256 public constant FLASH_LOAN_FEE_BPS = 5;

    /// @notice Basis points denominator (100% = 10000 bps)
    uint256 public constant BPS_DENOMINATOR = 10000;

    /// @notice Whitelisted DEX routers
    mapping(address => bool) public whitelistedDEXs;

    /// @notice Emergency withdrawal allowed addresses
    mapping(address => bool) public emergencyWithdrawers;

    /// @notice Total profits earned (per token)
    mapping(address => uint256) public totalProfits;

    /// @notice Arbitrage execution counter
    uint256 public executionCount;

    /**
     * @notice Struct containing arbitrage path information
     * @param dexRouters Array of DEX router addresses to use for each swap
     * @param path Token path for the arbitrage (e.g., [USDC, WETH, WBTC, USDC])
     * @param amountIn Amount to borrow via flash loan
     * @param minAmountOut Minimum amount expected after all swaps (slippage protection)
     * @param deadline Transaction deadline
     */
    struct ArbitrageParams {
        address[] dexRouters;
        address[] path;
        uint256 amountIn;
        uint256 minAmountOut;
        uint256 deadline;
    }

    /// @notice Events
    event ArbitrageExecuted(
        address indexed token,
        uint256 amountBorrowed,
        uint256 profit,
        uint256 timestamp
    );
    event DEXWhitelisted(address indexed dex, bool status);
    event MinProfitUpdated(uint256 oldValue, uint256 newValue);
    event MaxSlippageUpdated(uint256 oldValue, uint256 newValue);
    event EmergencyWithdrawal(address indexed token, uint256 amount, address indexed to);
    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);

    /// @notice Errors
    error UnauthorizedDEX(address dex);
    error InsufficientProfit(uint256 actual, uint256 required);
    error SlippageExceeded(uint256 amountOut, uint256 minAmountOut);
    error DeadlineExpired(uint256 deadline, uint256 currentTime);
    error FlashLoanFailed();
    error InvalidPath();
    error Unauthorized();

    /**
     * @notice Constructor
     * @param _addressProvider Aave V3 Pool Addresses Provider
     * @param _minProfitUSD Minimum profit in USD (18 decimals)
     * @param _maxSlippageBps Maximum slippage in basis points
     */
    constructor(
        address _addressProvider,
        uint256 _minProfitUSD,
        uint256 _maxSlippageBps
    ) Ownable(msg.sender) {
        require(_addressProvider != address(0), "Invalid address provider");
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressProvider);
        POOL = IPool(ADDRESSES_PROVIDER.getPool());
        minProfitUSD = _minProfitUSD;
        maxSlippageBps = _maxSlippageBps;

        // Grant owner emergency withdraw permission
        emergencyWithdrawers[msg.sender] = true;
    }

    /**
     * @notice Execute flash loan arbitrage
     * @param params Arbitrage parameters containing DEX path and amounts
     */
    function executeArbitrage(ArbitrageParams calldata params)
        external
        onlyOwner
        nonReentrant
        whenNotPaused
    {
        // Validate deadline
        if (block.timestamp > params.deadline) {
            revert DeadlineExpired(params.deadline, block.timestamp);
        }

        // Validate path (must start and end with same token)
        if (params.path.length < 3 || params.path[0] != params.path[params.path.length - 1]) {
            revert InvalidPath();
        }

        // Validate DEX routers count matches path segments
        require(params.dexRouters.length == params.path.length - 1, "Router/path length mismatch");

        // Validate DEX routers are whitelisted
        for (uint256 i = 0; i < params.dexRouters.length; i++) {
            if (!whitelistedDEXs[params.dexRouters[i]]) {
                revert UnauthorizedDEX(params.dexRouters[i]);
            }
        }

        // Prepare flash loan
        address receiverAddress = address(this);
        address asset = params.path[0];
        uint256 amount = params.amountIn;

        // Mode 0 = no debt, flash loan must be repaid in same transaction
        uint256 mode = 0;

        // Encode params for the flash loan callback
        bytes memory encodedParams = abi.encode(params);

        // Create flash loan assets and amounts arrays
        address[] memory assets = new address[](1);
        assets[0] = asset;

        uint256[] memory amounts = new uint256[](1);
        amounts[0] = amount;

        uint256[] memory modes = new uint256[](1);
        modes[0] = mode;

        // Execute flash loan
        POOL.flashLoan(
            receiverAddress,
            assets,
            amounts,
            modes,
            address(this),
            encodedParams,
            0 // referral code
        );

        executionCount++;
    }

    /**
     * @notice Aave V3 flash loan callback
     * @dev This function is called by Aave after receiving the flash loan
     * @param assets The addresses of the flash-borrowed assets
     * @param amounts The amounts of the flash-borrowed assets
     * @param premiums The fees of the flash-borrowed assets
     * @param initiator The address that initiated the flash loan
     * @param params Encoded arbitrage parameters
     * @return True if execution was successful
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        // Verify caller is Aave Pool
        require(msg.sender == address(POOL), "Caller must be Aave Pool");
        require(initiator == address(this), "Initiator must be this contract");

        // Decode parameters
        ArbitrageParams memory arbParams = abi.decode(params, (ArbitrageParams));

        // Execute arbitrage swaps
        uint256 finalAmount = _executeSwaps(arbParams);

        // Calculate total amount to repay (borrowed + premium)
        uint256 amountOwed = amounts[0] + premiums[0];

        // Verify profit after repayment
        if (finalAmount <= amountOwed) {
            revert InsufficientProfit(0, minProfitUSD);
        }

        uint256 profit = finalAmount - amountOwed;

        // Verify minimum profit threshold
        // Note: In production, convert to USD using price oracle
        if (profit < minProfitUSD) {
            revert InsufficientProfit(profit, minProfitUSD);
        }

        // Track profits
        totalProfits[assets[0]] += profit;

        // Approve Aave Pool to pull the owed amount
        IERC20(assets[0]).forceApprove(address(POOL), amountOwed);

        emit ArbitrageExecuted(assets[0], amounts[0], profit, block.timestamp);

        return true;
    }

    /**
     * @notice Execute the swap sequence across multiple DEXes
     * @dev Internal function that performs the actual token swaps
     * @param params Arbitrage parameters
     * @return Final amount received after all swaps
     */
    function _executeSwaps(ArbitrageParams memory params) internal returns (uint256) {
        uint256 currentAmount = params.amountIn;

        // Execute swaps through each DEX in sequence
        for (uint256 i = 0; i < params.dexRouters.length; i++) {
            address tokenIn = params.path[i];
            address tokenOut = params.path[i + 1];
            address dexRouter = params.dexRouters[i];

            // Approve DEX router to spend tokens
            IERC20(tokenIn).forceApprove(dexRouter, currentAmount);

            // Execute swap on DEX
            // Note: This is a simplified interface - actual implementation
            // would use specific DEX router interfaces (Uniswap V3, etc.)
            currentAmount = _swapOnDEX(
                dexRouter,
                tokenIn,
                tokenOut,
                currentAmount,
                0, // minAmountOut calculated per swap
                params.deadline
            );

            // Reset approval to 0 for security
            IERC20(tokenIn).forceApprove(dexRouter, 0);
        }

        // Verify slippage protection
        if (currentAmount < params.minAmountOut) {
            revert SlippageExceeded(currentAmount, params.minAmountOut);
        }

        return currentAmount;
    }

    /**
     * @notice Execute swap on a specific DEX
     * @dev This is a placeholder - actual implementation depends on DEX
     * @param router DEX router address
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Amount to swap
     * @param minAmountOut Minimum output amount
     * @param deadline Transaction deadline
     * @return Amount received from swap
     */
    function _swapOnDEX(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 deadline
    ) internal returns (uint256) {
        // TODO: Implement specific DEX logic
        // This will be implemented in the DEXLibrary
        // For now, return amountIn as placeholder
        revert("DEX swap not implemented - use DEXLibrary");
    }

    /**
     * @notice Whitelist or remove a DEX router
     * @param dex DEX router address
     * @param status True to whitelist, false to remove
     */
    function setDEXWhitelist(address dex, bool status) external onlyOwner {
        require(dex != address(0), "Invalid DEX address");
        whitelistedDEXs[dex] = status;
        emit DEXWhitelisted(dex, status);
    }

    /**
     * @notice Update minimum profit threshold
     * @param _minProfitUSD New minimum profit in USD (18 decimals)
     */
    function setMinProfit(uint256 _minProfitUSD) external onlyOwner {
        uint256 oldValue = minProfitUSD;
        minProfitUSD = _minProfitUSD;
        emit MinProfitUpdated(oldValue, _minProfitUSD);
    }

    /**
     * @notice Update maximum slippage
     * @param _maxSlippageBps New maximum slippage in basis points
     */
    function setMaxSlippage(uint256 _maxSlippageBps) external onlyOwner {
        require(_maxSlippageBps <= 1000, "Slippage too high"); // Max 10%
        uint256 oldValue = maxSlippageBps;
        maxSlippageBps = _maxSlippageBps;
        emit MaxSlippageUpdated(oldValue, _maxSlippageBps);
    }

    /**
     * @notice Pause contract (emergency)
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
     * @notice Grant emergency withdrawal permission
     * @param account Address to grant permission
     */
    function grantEmergencyWithdrawer(address account) external onlyOwner {
        emergencyWithdrawers[account] = true;
    }

    /**
     * @notice Revoke emergency withdrawal permission
     * @param account Address to revoke permission
     */
    function revokeEmergencyWithdrawer(address account) external onlyOwner {
        emergencyWithdrawers[account] = false;
    }

    /**
     * @notice Withdraw profits earned from arbitrage
     * @param token Token to withdraw
     * @param amount Amount to withdraw
     * @param to Recipient address
     */
    function withdrawProfits(
        address token,
        uint256 amount,
        address to
    ) external onlyOwner nonReentrant {
        require(to != address(0), "Invalid recipient");
        require(amount <= totalProfits[token], "Insufficient profits");

        totalProfits[token] -= amount;
        IERC20(token).safeTransfer(to, amount);

        emit ProfitWithdrawn(token, amount, to);
    }

    /**
     * @notice Emergency withdrawal (only authorized addresses)
     * @param token Token to withdraw
     * @param amount Amount to withdraw
     * @param to Recipient address
     */
    function emergencyWithdraw(
        address token,
        uint256 amount,
        address to
    ) external nonReentrant {
        require(to != address(0), "Invalid recipient");
        if (!emergencyWithdrawers[msg.sender]) {
            revert Unauthorized();
        }

        IERC20(token).safeTransfer(to, amount);

        if (totalProfits[token] > amount) {
            totalProfits[token] -= amount;
        } else {
            totalProfits[token] = 0;
        }

        emit EmergencyWithdrawal(token, amount, to);
    }

    /**
     * @notice Get contract balance of a token
     * @param token Token address
     * @return Balance
     */
    function getBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }

    /**
     * @notice Estimate flash loan fee for a given amount
     * @param amount Borrow amount
     * @return fee Flash loan fee
     */
    function estimateFlashLoanFee(uint256 amount) external pure returns (uint256 fee) {
        fee = (amount * FLASH_LOAN_FEE_BPS) / BPS_DENOMINATOR;
    }
}
