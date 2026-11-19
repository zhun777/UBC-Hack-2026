"""Checks the backend against the ABIs in contracts/abi/, so a contract change that would
break the backend fails here instead of during the demo."""
from eth_abi import encode
from web3 import Web3

import chain
import config
import units

VAULT = config.load_abi("RewardsVault")
TOKEN = config.load_abi("APPToken")
w3 = Web3()


def _signature(abi, name):
    item = next(i for i in abi if i.get("type") in ("function", "event") and i.get("name") == name)
    return [(i["name"], i["type"]) for i in item["inputs"]]


def test_abis_are_committed():
    assert VAULT is not None and TOKEN is not None


def test_functions_the_backend_calls_have_the_arguments_it_sends():
    vault = w3.eth.contract(abi=VAULT)
    token = w3.eth.contract(abi=TOKEN)
    user = "0x" + "11" * 20
    vault.encode_abi("issueReward", args=[units.id_bytes("brand-a-us"), user, 150])
    vault.encode_abi("fundBrand", args=[units.id_bytes("brand-a-us"), 1_500_000])
    vault.encode_abi("spendAtBrand", args=[units.id_bytes("cafe-sg"), units.id_bytes("cafe-sg-orchard"),
                                           units.id_bytes("7K2M9Q"), 150])
    vault.encode_abi("orderPaid", args=[units.id_bytes("7K2M9Q")])
    vault.encode_abi("owner", args=[])
    token.encode_abi("balanceOf", args=[user])


def test_get_brand_has_budget_fifth():
    item = next(i for i in VAULT if i.get("name") == "getBrand")
    fields = [c["name"] for c in item["outputs"][0]["components"]]
    assert fields[4] == "budget"  # ArcChain.issue_reward reads getBrand(...)[4]


def test_spent_event_has_the_fields_the_watcher_reads():
    assert _signature(VAULT, "Spent") == [
        ("user", "address"), ("brandId", "bytes32"), ("branchId", "bytes32"),
        ("orderId", "bytes32"), ("points", "uint256"), ("usdcAmount", "uint256")]


def test_points_have_zero_decimals_and_point_is_one_cent():
    assert any(i.get("name") == "decimals" for i in TOKEN)
    assert any(i.get("name") == "POINT_VALUE" for i in VAULT)
    assert units.cents_to_usdc_units(1) == 10_000  # the vault's POINT_VALUE


def _revert_data(name, types=(), args=()):
    selector = Web3.keccak(text=f"{name}({','.join(types)})")[:4]
    return Web3.to_hex(selector + encode(list(types), list(args)))


class _Revert(Exception):
    def __init__(self, data):
        super().__init__(data)
        self.data = data


def test_vault_refusals_become_api_errors():
    errors = chain.custom_errors(VAULT)
    paid = chain.vault_refusal(errors, _Revert(_revert_data("OrderAlreadyPaid")))
    assert paid.code == "ORDER_ALREADY_PAID"
    assert chain.vault_refusal(errors, _Revert(_revert_data("UnknownBrand"))).code == "UNKNOWN_BRAND"

    short = chain.vault_refusal(errors, _Revert(
        _revert_data("InsufficientPoints", ("uint256", "uint256"), (500, 120))))
    assert short.code == "CHAIN_ERROR"
    assert "InsufficientPoints(500, 120)" in short.message

    assert chain.vault_refusal(errors, _Revert("0xdeadbeef")) is None
    assert chain.vault_refusal(errors, ValueError("timeout")) is None
