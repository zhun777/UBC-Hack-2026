"""The connection to Arc, plus one helper that signs and sends a transaction.

Only used when CHAIN_MODE=arc.
"""
from __future__ import annotations

import functools
import threading

from eth_account import Account
from web3 import Web3

import config

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


@functools.lru_cache(maxsize=1)
def w3() -> Web3:
    url = config.rpc_url()
    if not url:
        raise RuntimeError("No RPC URL: set RPC_URL in backend/.env or rpcUrl in contracts/deployments.json")
    return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))


@functools.lru_cache(maxsize=1)
def chain_id() -> int:
    return w3().eth.chain_id


def send_transaction(private_key: str, to: str, data: str, value: int = 0):
    """Signs a transaction with `private_key`, sends it, and waits for the receipt.

    Transactions from the same sender go one at a time, so two requests never pick
    the same nonce (each wallet's transaction counter).
    """
    client = w3()
    account = Account.from_key(private_key)
    with _lock_for(account.address):
        tx = {
            "from": account.address,
            "to": Web3.to_checksum_address(to),
            "data": data,
            "value": value,
            "nonce": client.eth.get_transaction_count(account.address, "pending"),
            "chainId": chain_id(),
        }
        tx["gas"] = int(client.eth.estimate_gas(tx) * 1.25)  # fails here, with the reason, if it would revert
        tx.update(_fees(client))
        signed = account.sign_transaction(tx)
        tx_hash = client.eth.send_raw_transaction(signed.raw_transaction)
        receipt = client.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction {Web3.to_hex(tx_hash)} reverted")
    return receipt


def _fees(client: Web3) -> dict:
    """EIP-1559 fee fields if the chain has a base fee, otherwise a plain gas price."""
    base_fee = client.eth.get_block("latest").get("baseFeePerGas")
    if base_fee is None:
        return {"gasPrice": client.eth.gas_price}
    try:
        tip = client.eth.max_priority_fee
    except Exception:
        tip = Web3.to_wei(1, "gwei")
    return {"maxFeePerGas": base_fee * 2 + tip, "maxPriorityFeePerGas": tip}


def _lock_for(address: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(address, threading.Lock())
