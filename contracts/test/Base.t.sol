// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {PointsToken} from "../src/PointsToken.sol";
import {RewardsVault} from "../src/RewardsVault.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";

/// @dev Shared setup: one brand with a US operator and a Singapore operator.
abstract contract BaseTest is Test {
    uint256 internal constant USDC = 1e6; // $1.00 in USDC units

    MockUSDC internal usdc;
    PointsToken internal token;
    RewardsVault internal vault;

    address internal network = makeAddr("network"); // contract owner, held by the backend
    address internal usOperator = makeAddr("usOperator");
    address internal sgOperator = makeAddr("sgOperator");
    address internal usSettlement = makeAddr("usSettlement");
    address internal sgSettlement = makeAddr("sgSettlement");
    address internal customer = makeAddr("customer");

    bytes32 internal constant BRAND_US = keccak256("brand-us");
    bytes32 internal constant BRAND_SG = keccak256("brand-sg");
    bytes32 internal constant BRANCH_SG = keccak256("brand-sg-orchard");

    function setUp() public virtual {
        usdc = new MockUSDC();
        vm.startPrank(network);
        token = new PointsToken(network);
        vault = new RewardsVault(network, usdc, token);
        token.setVault(address(vault));
        vault.addBrand(BRAND_US, usSettlement, "USD");
        vault.addBrand(BRAND_SG, sgSettlement, "SGD");
        vm.stopPrank();

        usdc.mint(usOperator, 10_000 * USDC);
        usdc.mint(sgOperator, 10_000 * USDC);
    }

    function _fund(address funder, bytes32 brandId, uint256 amount) internal {
        vm.startPrank(funder);
        usdc.approve(address(vault), amount);
        vault.fundBrand(brandId, amount);
        vm.stopPrank();
    }

    function _issue(bytes32 brandId, address user, uint256 pts) internal {
        vm.prank(network);
        vault.issueReward(brandId, user, pts);
    }

    function _spend(address user, bytes32 brandId, string memory orderCode, uint256 pts) internal {
        vm.prank(user);
        vault.spendAtBrand(brandId, BRANCH_SG, keccak256(bytes(orderCode)), pts);
    }
}
