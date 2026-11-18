// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PointsToken} from "../src/PointsToken.sol";
import {RewardsVault} from "../src/RewardsVault.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";

/// @dev Drives random sequences of fund, issue and spend against the vault.
contract VaultHandler is Test {
    MockUSDC internal usdc;
    PointsToken internal token;
    RewardsVault internal vault;
    address internal network;
    bytes32[2] internal brands;
    address[3] internal users;
    uint256 internal nextOrder = 1;

    constructor(MockUSDC usdc_, PointsToken token_, RewardsVault vault_, address network_, bytes32[2] memory brands_) {
        usdc = usdc_;
        token = token_;
        vault = vault_;
        network = network_;
        brands = brands_;
        users = [makeAddr("u0"), makeAddr("u1"), makeAddr("u2")];
    }

    function fund(uint256 brandSeed, uint256 amount) external {
        amount = bound(amount, 1, 1_000_000e6);
        bytes32 brandId = brands[brandSeed % 2];
        usdc.mint(address(this), amount);
        usdc.approve(address(vault), amount);
        vault.fundBrand(brandId, amount);
    }

    function issue(uint256 brandSeed, uint256 userSeed, uint256 pts) external {
        bytes32 brandId = brands[brandSeed % 2];
        uint256 maxPts = vault.getBrand(brandId).budget / vault.POINT_VALUE();
        if (maxPts == 0) return;
        pts = bound(pts, 1, maxPts);
        vm.prank(network);
        vault.issueReward(brandId, users[userSeed % 3], pts);
    }

    function spend(uint256 brandSeed, uint256 userSeed, uint256 pts) external {
        address user = users[userSeed % 3];
        uint256 bal = token.balanceOf(user);
        if (bal == 0) return;
        pts = bound(pts, 1, bal);
        vm.prank(user);
        vault.spendAtBrand(brands[brandSeed % 2], bytes32(0), bytes32(nextOrder++), pts);
    }
}

contract VaultInvariantTest is Test {
    MockUSDC internal usdc;
    PointsToken internal token;
    RewardsVault internal vault;
    VaultHandler internal handler;
    address internal network = makeAddr("network");

    function setUp() public {
        usdc = new MockUSDC();
        vm.startPrank(network);
        token = new PointsToken(network);
        vault = new RewardsVault(network, usdc, token);
        token.setVault(address(vault));
        bytes32[2] memory brands = [keccak256("brand-us"), keccak256("brand-sg")];
        vault.addBrand(brands[0], makeAddr("usSettlement"), "USD");
        vault.addBrand(brands[1], makeAddr("sgSettlement"), "SGD");
        vm.stopPrank();

        handler = new VaultHandler(usdc, token, vault, network, brands);
        targetContract(address(handler));
    }

    /// Vault USDC = sum of brand budgets + points outstanding x $0.01, after every step.
    function invariant_VaultExactlyBacksBudgetsAndPoints() public view {
        assertEq(usdc.balanceOf(address(vault)), vault.totalLiabilities());
    }
}
