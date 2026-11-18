// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC20Errors} from "@openzeppelin/contracts/interfaces/draft-IERC6093.sol";
import {RewardsVault} from "../src/RewardsVault.sol";
import {BaseTest} from "./Base.t.sol";

contract RewardsVaultTest is BaseTest {
    // ------------------------------------------------------------ brands

    function test_AddBrandStoresDetails() public view {
        RewardsVault.Brand memory b = vault.getBrand(BRAND_SG);
        assertEq(b.settlement, sgSettlement);
        assertEq(b.currency, "SGD");
        assertTrue(b.active);
        assertTrue(b.exists);
        assertEq(b.budget, 0);
        assertEq(vault.brandCount(), 2);
    }

    function test_AddBrandRevertsForNonOwner() public {
        vm.prank(customer);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, customer));
        vault.addBrand(keccak256("new"), usSettlement, "USD");
    }

    function test_AddBrandRevertsForDuplicateId() public {
        vm.prank(network);
        vm.expectRevert(RewardsVault.BrandExists.selector);
        vault.addBrand(BRAND_US, usSettlement, "USD");
    }

    function test_AddBrandRevertsForZeroSettlement() public {
        vm.prank(network);
        vm.expectRevert(RewardsVault.ZeroAddress.selector);
        vault.addBrand(keccak256("new"), address(0), "USD");
    }

    function test_SetBrandSettlement() public {
        address newAddr = makeAddr("newSettlement");
        vm.prank(network);
        vault.setBrandSettlement(BRAND_SG, newAddr);
        assertEq(vault.getBrand(BRAND_SG).settlement, newAddr);
    }

    // ----------------------------------------------------------- funding

    function test_FundBrandMovesUsdcAndRaisesBudget() public {
        vm.startPrank(usOperator);
        usdc.approve(address(vault), 500 * USDC);
        vm.expectEmit(address(vault));
        emit RewardsVault.BrandFunded(BRAND_US, usOperator, 500 * USDC);
        vault.fundBrand(BRAND_US, 500 * USDC);
        vm.stopPrank();

        assertEq(usdc.balanceOf(address(vault)), 500 * USDC);
        assertEq(usdc.balanceOf(usOperator), 9_500 * USDC);
        assertEq(vault.getBrand(BRAND_US).budget, 500 * USDC);
    }

    function test_FundBrandRevertsForUnknownBrand() public {
        vm.startPrank(usOperator);
        usdc.approve(address(vault), 1 * USDC);
        vm.expectRevert(RewardsVault.UnknownBrand.selector);
        vault.fundBrand(keccak256("nope"), 1 * USDC);
        vm.stopPrank();
    }

    function test_FundBrandRevertsWithoutApproval() public {
        vm.prank(usOperator);
        vm.expectRevert(
            abi.encodeWithSelector(IERC20Errors.ERC20InsufficientAllowance.selector, address(vault), 0, 1 * USDC)
        );
        vault.fundBrand(BRAND_US, 1 * USDC);
    }

    function test_FundBrandRevertsForZero() public {
        vm.prank(usOperator);
        vm.expectRevert(RewardsVault.ZeroAmount.selector);
        vault.fundBrand(BRAND_US, 0);
    }

    // ----------------------------------------------------------- issuing

    function test_IssueRewardMintsAndLowersBudget() public {
        _fund(usOperator, BRAND_US, 500 * USDC);

        vm.expectEmit(address(vault));
        emit RewardsVault.RewardIssued(BRAND_US, customer, 250, 2_500_000);
        _issue(BRAND_US, customer, 250);

        assertEq(token.balanceOf(customer), 250);
        assertEq(vault.getBrand(BRAND_US).budget, 500 * USDC - 2_500_000); // $497.50
        assertEq(usdc.balanceOf(address(vault)), 500 * USDC); // USDC stays in the vault
    }

    function test_IssueRewardRevertsForNonOwner() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        vm.prank(customer);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, customer));
        vault.issueReward(BRAND_US, customer, 250);
    }

    function test_IssueRewardRevertsForUnknownBrand() public {
        vm.prank(network);
        vm.expectRevert(RewardsVault.UnknownBrand.selector);
        vault.issueReward(keccak256("nope"), customer, 250);
    }

    function test_IssueRewardRevertsForPausedBrand() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        vm.startPrank(network);
        vault.setBrandActive(BRAND_US, false);
        vm.expectRevert(RewardsVault.BrandInactive.selector);
        vault.issueReward(BRAND_US, customer, 250);
        vm.stopPrank();
    }

    function test_IssueRewardRevertsForZeroPoints() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        vm.prank(network);
        vm.expectRevert(RewardsVault.ZeroAmount.selector);
        vault.issueReward(BRAND_US, customer, 0);
    }

    function test_IssueRewardRevertsForZeroUser() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        vm.prank(network);
        vm.expectRevert(RewardsVault.ZeroAddress.selector);
        vault.issueReward(BRAND_US, address(0), 250);
    }

    function test_IssueRewardRevertsWhenBudgetTooSmallAndChangesNothing() public {
        _fund(usOperator, BRAND_US, 2 * USDC); // budget covers 200 points
        vm.prank(network);
        vm.expectRevert(abi.encodeWithSelector(RewardsVault.InsufficientBudget.selector, 2_500_000, 2 * USDC));
        vault.issueReward(BRAND_US, customer, 250);

        assertEq(token.balanceOf(customer), 0);
        assertEq(vault.getBrand(BRAND_US).budget, 2 * USDC);
        assertEq(usdc.balanceOf(address(vault)), 2 * USDC);
    }

    // ---------------------------------------------------------- spending

    function test_SpendBurnsPointsAndPaysSettlement() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 2_650);

        bytes32 orderId = keccak256("7K2M9Q");
        vm.expectEmit(address(vault));
        emit RewardsVault.Spent(customer, BRAND_SG, BRANCH_SG, orderId, 600, 6 * USDC);
        _spend(customer, BRAND_SG, "7K2M9Q", 600);

        assertEq(token.balanceOf(customer), 2_050);
        assertEq(usdc.balanceOf(sgSettlement), 6 * USDC);
        assertTrue(vault.orderPaid(orderId));
    }

    /// The demo story: points earned from the US operator's budget are spent at the
    /// Singapore operator, and the Singapore operator is the one paid.
    function test_CrossBorderSpendPaysSingaporeFromUsBudget() public {
        _fund(usOperator, BRAND_US, 476 * USDC);
        _fund(sgOperator, BRAND_SG, 300 * USDC);
        _issue(BRAND_US, customer, 2_400);
        _issue(BRAND_US, customer, 250);

        uint256 vaultBefore = usdc.balanceOf(address(vault));
        _spend(customer, BRAND_SG, "SG-0001", 600);

        assertEq(usdc.balanceOf(sgSettlement), 6 * USDC);
        assertEq(usdc.balanceOf(usSettlement), 0);
        assertEq(usdc.balanceOf(address(vault)), vaultBefore - 6 * USDC);
        assertEq(vault.getBrand(BRAND_US).budget, 476 * USDC - 26_500_000); // $449.50
        assertEq(vault.getBrand(BRAND_SG).budget, 300 * USDC); // untouched
        assertTrue(vault.isFullyBacked());
    }

    function test_SpendRevertsWithTooFewPoints() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 500);
        vm.prank(customer);
        vm.expectRevert(abi.encodeWithSelector(RewardsVault.InsufficientPoints.selector, 600, 500));
        vault.spendAtBrand(BRAND_SG, BRANCH_SG, keccak256("A"), 600);
    }

    function test_SpendRevertsForUnknownBrand() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 600);
        vm.prank(customer);
        vm.expectRevert(RewardsVault.UnknownBrand.selector);
        vault.spendAtBrand(keccak256("nope"), BRANCH_SG, keccak256("A"), 600);
    }

    function test_SpendRevertsForPausedBrand() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 600);
        vm.prank(network);
        vault.setBrandActive(BRAND_SG, false);
        vm.prank(customer);
        vm.expectRevert(RewardsVault.BrandInactive.selector);
        vault.spendAtBrand(BRAND_SG, BRANCH_SG, keccak256("A"), 600);
    }

    function test_SpendRevertsForZeroPoints() public {
        vm.prank(customer);
        vm.expectRevert(RewardsVault.ZeroAmount.selector);
        vault.spendAtBrand(BRAND_SG, BRANCH_SG, keccak256("A"), 0);
    }

    function test_SpendRevertsForEmptyOrderId() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 600);
        vm.prank(customer);
        vm.expectRevert(RewardsVault.InvalidOrder.selector);
        vault.spendAtBrand(BRAND_SG, BRANCH_SG, bytes32(0), 600);
    }

    function test_SpendRevertsForOrderAlreadyPaid() public {
        _fund(usOperator, BRAND_US, 500 * USDC);
        _issue(BRAND_US, customer, 1_200);
        _spend(customer, BRAND_SG, "7K2M9Q", 600);

        vm.prank(customer);
        vm.expectRevert(RewardsVault.OrderAlreadyPaid.selector);
        vault.spendAtBrand(BRAND_SG, BRANCH_SG, keccak256("7K2M9Q"), 600);
        assertEq(token.balanceOf(customer), 600);
    }

    // ------------------------------------------------------ the demo run

    /// Mirrors the acceptance test in the development plan, step by step.
    function test_AcceptanceScriptNumbers() public {
        // Seed: US budget $476 after 2,400 seeded points, SG budget $300, vault $800
        _fund(usOperator, BRAND_US, 500 * USDC);
        _fund(sgOperator, BRAND_SG, 300 * USDC);
        _issue(BRAND_US, customer, 2_400);
        assertEq(vault.getBrand(BRAND_US).budget, 476 * USDC);
        assertEq(usdc.balanceOf(address(vault)), 800 * USDC);

        // Step 2: pay $50 at the US store at 5 points per $1
        _issue(BRAND_US, customer, 250);
        assertEq(token.balanceOf(customer), 2_650);
        assertEq(vault.getBrand(BRAND_US).budget, 473_500_000); // $473.50
        assertEq(usdc.balanceOf(address(vault)), 800 * USDC);

        // Step 5: pay S$7.80 (= $6.00) with 600 points in Singapore
        _spend(customer, BRAND_SG, "7K2M9Q", 600);
        assertEq(token.balanceOf(customer), 2_050);
        assertEq(usdc.balanceOf(sgSettlement), 6 * USDC);
        assertEq(usdc.balanceOf(address(vault)), 794 * USDC);
        assertEq(vault.totalLiabilities(), 794 * USDC);
    }
}
