// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {PointsToken} from "../src/PointsToken.sol";
import {BaseTest} from "./Base.t.sol";

contract PointsTokenTest is BaseTest {
    function test_DecimalsIsZero() public view {
        assertEq(token.decimals(), 0);
    }

    function test_NameAndSymbol() public view {
        assertEq(token.name(), "Reward Points");
        assertEq(token.symbol(), "PTS");
    }

    function test_OnlyVaultCanMint() public {
        vm.prank(network); // even the owner cannot mint directly
        vm.expectRevert(PointsToken.OnlyVault.selector);
        token.mint(customer, 100);

        vm.prank(customer);
        vm.expectRevert(PointsToken.OnlyVault.selector);
        token.mint(customer, 100);

        vm.prank(address(vault));
        token.mint(customer, 100);
        assertEq(token.balanceOf(customer), 100);
    }

    function test_OnlyVaultCanBurn() public {
        vm.prank(address(vault));
        token.mint(customer, 100);

        vm.prank(customer);
        vm.expectRevert(PointsToken.OnlyVault.selector);
        token.burn(customer, 100);

        vm.prank(address(vault));
        token.burn(customer, 40);
        assertEq(token.balanceOf(customer), 60);
    }

    function test_SetVaultOnlyOnce() public {
        vm.prank(network);
        vm.expectRevert(PointsToken.VaultAlreadySet.selector);
        token.setVault(makeAddr("otherVault"));
    }

    function test_SetVaultOnlyOwner() public {
        PointsToken fresh = new PointsToken(network);
        vm.prank(customer);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, customer));
        fresh.setVault(address(vault));
    }

    function test_SetVaultRejectsZeroAddress() public {
        PointsToken fresh = new PointsToken(network);
        vm.prank(network);
        vm.expectRevert(PointsToken.ZeroAddress.selector);
        fresh.setVault(address(0));
    }

    function test_TransferBetweenUsersReverts() public {
        vm.prank(address(vault));
        token.mint(customer, 100);

        vm.prank(customer);
        vm.expectRevert(PointsToken.TransfersDisabled.selector);
        token.transfer(makeAddr("friend"), 10);
    }

    function test_TransferFromBetweenUsersReverts() public {
        address friend = makeAddr("friend");
        vm.prank(address(vault));
        token.mint(customer, 100);

        vm.prank(customer);
        token.approve(friend, 10);
        vm.prank(friend);
        vm.expectRevert(PointsToken.TransfersDisabled.selector);
        token.transferFrom(customer, friend, 10);
    }
}
