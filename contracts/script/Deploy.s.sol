// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {VmSafe} from "forge-std/Vm.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {PointsToken} from "../src/PointsToken.sol";
import {RewardsVault} from "../src/RewardsVault.sol";

/// @notice Deploys PointsToken + RewardsVault, links them, registers the two brand
///         operators and optionally funds their reward budgets.
///
/// Reads from the environment (see .env.example):
///   DEPLOYER_PRIVATE_KEY  becomes the owner (the network wallet the backend holds)
///   USDC_ADDRESS          defaults to Arc's USDC ERC-20 interface
///   BRAND_US_SLUG, BRAND_SG_SLUG          defaults "brand-a-us", "cafe-sg" (match backend/brands.json)
///   US_SETTLEMENT, SG_SETTLEMENT          where each operator gets paid (required)
///   FUND_US_USDC, FUND_SG_USDC            budget to deposit, in USDC units (default 0)
///   ARC_RPC_URL, ARC_EXPLORER_URL         copied into deployments.json for the backend
///
/// Writes deployments.json when run with --broadcast.
contract Deploy is Script {
    address internal constant ARC_USDC = 0x3600000000000000000000000000000000000000;

    struct BrandCfg {
        string slug;
        bytes32 id;
        string currency;
        address settlement;
        uint256 funding;
    }

    address internal owner;
    IERC20 internal usdc;
    PointsToken internal token;
    RewardsVault internal vault;
    uint256 internal startBlock;
    BrandCfg internal us;
    BrandCfg internal sg;

    function run() external {
        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        owner = vm.addr(pk);
        usdc = IERC20(vm.envOr("USDC_ADDRESS", ARC_USDC));
        us = _brand("BRAND_US_SLUG", "brand-a-us", "USD", "US_SETTLEMENT", "FUND_US_USDC");
        sg = _brand("BRAND_SG_SLUG", "cafe-sg", "SGD", "SG_SETTLEMENT", "FUND_SG_USDC");
        startBlock = block.number;

        vm.startBroadcast(pk);
        token = new PointsToken(owner);
        vault = new RewardsVault(owner, usdc, token);
        token.setVault(address(vault));
        vault.addBrand(us.id, us.settlement, us.currency);
        vault.addBrand(sg.id, sg.settlement, sg.currency);
        if (us.funding + sg.funding > 0) {
            usdc.approve(address(vault), us.funding + sg.funding);
            if (us.funding > 0) vault.fundBrand(us.id, us.funding);
            if (sg.funding > 0) vault.fundBrand(sg.id, sg.funding);
        }
        vm.stopBroadcast();

        console2.log("Owner (network wallet):", owner);
        console2.log("PointsToken:           ", address(token));
        console2.log("RewardsVault:          ", address(vault));

        if (vm.isContext(VmSafe.ForgeContext.ScriptBroadcast)) {
            _writeDeployments();
        } else {
            console2.log("Dry run: deployments.json not written. Add --broadcast to deploy.");
        }
    }

    function _brand(
        string memory slugVar,
        string memory defaultSlug,
        string memory currency,
        string memory settlementVar,
        string memory fundVar
    ) internal view returns (BrandCfg memory b) {
        b.slug = vm.envOr(slugVar, defaultSlug);
        b.id = keccak256(bytes(b.slug));
        b.currency = currency;
        b.settlement = vm.envAddress(settlementVar);
        b.funding = vm.envOr(fundVar, uint256(0));
    }

    function _brandJson(string memory key, BrandCfg memory b) internal returns (string memory) {
        vm.serializeBytes32(key, "id", b.id);
        vm.serializeString(key, "currency", b.currency);
        return vm.serializeAddress(key, "settlement", b.settlement);
    }

    function _writeDeployments() internal {
        string memory brandsKey = "brands";
        vm.serializeString(brandsKey, us.slug, _brandJson("us", us));
        string memory brandsJson = vm.serializeString(brandsKey, sg.slug, _brandJson("sg", sg));

        string memory root = "root";
        vm.serializeUint(root, "chainId", block.chainid);
        vm.serializeString(root, "rpcUrl", vm.envOr("ARC_RPC_URL", string("")));
        vm.serializeString(root, "explorerUrl", vm.envOr("ARC_EXPLORER_URL", string("")));
        vm.serializeUint(root, "deployBlock", startBlock);
        vm.serializeUint(root, "pointValueUsdcUnits", vault.POINT_VALUE());
        vm.serializeAddress(root, "owner", owner);
        vm.serializeAddress(root, "usdc", address(usdc));
        vm.serializeAddress(root, "appToken", address(token));
        vm.serializeAddress(root, "rewardsVault", address(vault));
        string memory json = vm.serializeString(root, "brands", brandsJson);
        vm.writeJson(json, "./deployments.json");
        console2.log("Wrote deployments.json");
    }
}
