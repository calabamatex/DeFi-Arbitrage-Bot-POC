// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../contracts/adapters/CurveAdapter.sol";
import "../../contracts/MockERC20.sol";

// ──────────────────────────────────────────────────────────────────────
// Mock Curve Pool
// ──────────────────────────────────────────────────────────────────────

contract MockCurvePool {
    // token index → address
    mapping(int128 => address) public coins;
    uint256 public exchangeRate; // output per input, scaled by 1e6

    constructor(address _tokenA, address _tokenB, int128 _indexA, int128 _indexB) {
        coins[_indexA] = _tokenA;
        coins[_indexB] = _tokenB;
        exchangeRate = 1e6; // 1:1 default
    }

    function setExchangeRate(uint256 rate) external {
        exchangeRate = rate;
    }

    function exchange(
        int128 i,
        int128 j,
        uint256 dx,
        uint256 min_dy
    ) external returns (uint256 dy) {
        dy = (dx * exchangeRate) / 1e6;
        require(dy >= min_dy, "Slippage");

        IERC20(coins[i]).transferFrom(msg.sender, address(this), dx);
        MockERC20(coins[j]).mint(msg.sender, dy);
    }

    function get_dy(int128 i, int128 j, uint256 dx) external view returns (uint256) {
        return (dx * exchangeRate) / 1e6;
    }
}

// ──────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────

contract CurveAdapterTest is Test {
    CurveAdapter adapter;
    MockCurvePool pool;
    MockERC20 tokenA;
    MockERC20 tokenB;

    address owner = address(this);
    address user = address(0xBEEF);

    function setUp() public {
        tokenA = new MockERC20("DAI", "DAI", 18);
        tokenB = new MockERC20("USDC", "USDC", 6);

        pool = new MockCurvePool(address(tokenA), address(tokenB), 0, 1);

        adapter = new CurveAdapter();
        adapter.registerPool(address(pool), address(tokenA), address(tokenB), 0, 1);
    }

    // ── Deployment ────────────────────────────────────────────────────

    function test_owner() public view {
        assertEq(adapter.owner(), owner);
    }

    function test_ownerIsAuthorized() public view {
        assertTrue(adapter.authorized(owner));
    }

    // ── Pool Registry ─────────────────────────────────────────────────

    function test_poolRegistered() public view {
        assertTrue(adapter.hasPool(address(tokenA), address(tokenB)));
        assertTrue(adapter.hasPool(address(tokenB), address(tokenA)));
    }

    function test_poolNotRegistered() public view {
        assertFalse(adapter.hasPool(address(tokenA), address(1)));
    }

    function test_registerPoolZeroAddress() public {
        vm.expectRevert("Invalid pool");
        adapter.registerPool(address(0), address(tokenA), address(tokenB), 0, 1);
    }

    function test_registerPoolOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        adapter.registerPool(address(pool), address(tokenA), address(tokenB), 0, 1);
    }

    // ── Authorization ─────────────────────────────────────────────────

    function test_setAuthorized() public {
        adapter.setAuthorized(user, true);
        assertTrue(adapter.authorized(user));

        adapter.setAuthorized(user, false);
        assertFalse(adapter.authorized(user));
    }

    function test_setAuthorizedOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        adapter.setAuthorized(user, true);
    }

    // ── Ownership ─────────────────────────────────────────────────────

    function test_transferOwnership() public {
        // Ownable2Step: transferOwnership sets pending owner, not immediate
        adapter.transferOwnership(user);
        // Owner is still the original until acceptOwnership is called
        assertEq(adapter.owner(), owner);
        assertEq(adapter.pendingOwner(), user);

        // Complete the transfer via acceptOwnership
        vm.prank(user);
        adapter.acceptOwnership();
        assertEq(adapter.owner(), user);
    }

    function test_transferOwnershipOnlyOwner() public {
        vm.prank(user);
        vm.expectRevert();
        adapter.transferOwnership(user);
    }

    function test_acceptOwnershipOnlyPendingOwner() public {
        adapter.transferOwnership(user);

        // A random address cannot accept
        vm.prank(address(0xDEAD));
        vm.expectRevert();
        adapter.acceptOwnership();
    }

    // ── Get Quote ─────────────────────────────────────────────────────

    function test_getQuote() public view {
        uint256 amountIn = 1000 * 1e18;
        uint256 quote = adapter.getQuote(address(tokenA), address(tokenB), amountIn);
        assertEq(quote, amountIn); // 1:1 default rate
    }

    function test_getQuoteCustomRate() public {
        pool.setExchangeRate(990000); // 0.99 rate
        uint256 amountIn = 1000 * 1e18;
        uint256 quote = adapter.getQuote(address(tokenA), address(tokenB), amountIn);
        assertEq(quote, (amountIn * 990000) / 1e6);
    }

    function test_getQuoteUnregistered() public {
        vm.expectRevert(abi.encodeWithSelector(
            CurveAdapter.PoolNotRegistered.selector,
            address(tokenA),
            address(1)
        ));
        adapter.getQuote(address(tokenA), address(1), 1e18);
    }

    // ── Swap Direct ───────────────────────────────────────────────────

    function test_swapDirect() public {
        uint256 amountIn = 1000 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        uint256 balBefore = tokenB.balanceOf(address(this));

        uint256 amountOut = adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            0,
            block.timestamp + 300,
            address(this),
            ""
        );

        assertEq(amountOut, amountIn);
        assertEq(tokenB.balanceOf(address(this)) - balBefore, amountIn);
    }

    function test_swapDirectToRecipient() public {
        uint256 amountIn = 500 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            0,
            block.timestamp + 300,
            user,
            ""
        );

        assertEq(tokenB.balanceOf(user), amountIn);
        assertEq(tokenB.balanceOf(address(adapter)), 0);
    }

    function test_swapDirectToSelf() public {
        uint256 amountIn = 500 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            0,
            block.timestamp + 300,
            address(adapter),
            ""
        );

        // When recipient is self, no extra transfer
        assertEq(tokenB.balanceOf(address(adapter)), amountIn);
    }

    function test_swapDirectSlippageProtection() public {
        pool.setExchangeRate(500000); // 0.5 rate
        uint256 amountIn = 1000 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        // Require 900 output (more than 0.5 rate would give)
        vm.expectRevert("Slippage");
        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            900 * 1e18,
            block.timestamp + 300,
            address(this),
            ""
        );
    }

    function test_swapDirectUnauthorized() public {
        vm.prank(user);
        vm.expectRevert(CurveAdapter.Unauthorized.selector);
        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            1e18,
            0,
            block.timestamp + 300,
            user,
            ""
        );
    }

    function test_swapDirectUnregisteredPool() public {
        tokenA.mint(address(adapter), 1e18);
        vm.expectRevert(abi.encodeWithSelector(
            CurveAdapter.PoolNotRegistered.selector,
            address(tokenA),
            address(1)
        ));
        adapter.swapDirect(
            address(tokenA),
            address(1),
            1e18,
            0,
            block.timestamp + 300,
            address(this),
            ""
        );
    }

    function test_swapDirectResetsApproval() public {
        uint256 amountIn = 1000 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            0,
            block.timestamp + 300,
            address(this),
            ""
        );

        // Approval should be reset to 0
        assertEq(tokenA.allowance(address(adapter), address(pool)), 0);
    }

    // ── Deadline Enforcement ────────────────────────────────────────────

    function test_swapDirectDeadlineExpired() public {
        uint256 amountIn = 1000 * 1e18;
        tokenA.mint(address(adapter), amountIn);

        vm.expectRevert("Deadline expired");
        adapter.swapDirect(
            address(tokenA),
            address(tokenB),
            amountIn,
            0,
            block.timestamp - 1, // expired deadline
            address(this),
            ""
        );
    }

    // ── Reverse Direction ─────────────────────────────────────────────

    function test_swapReverseDirection() public {
        uint256 amountIn = 500 * 1e18;
        tokenB.mint(address(adapter), amountIn);

        uint256 balBefore = tokenA.balanceOf(address(this));

        uint256 amountOut = adapter.swapDirect(
            address(tokenB),
            address(tokenA),
            amountIn,
            0,
            block.timestamp + 300,
            address(this),
            ""
        );

        assertEq(amountOut, amountIn);
        assertEq(tokenA.balanceOf(address(this)) - balBefore, amountIn);
    }
}
