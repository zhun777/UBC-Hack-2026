"""Users' wallets, behind the two functions from the build plan:

  get_or_create_wallet(user_id) -> address
  send_tx(user_id, to, data)    -> tx hash, signed by that user's own wallet

WALLET_MODE=test    the backend makes one key per user and keeps it in SQLite (test only)
WALLET_MODE=circle  Circle developer-controlled wallets: Circle holds the keys and signs
                    when the backend asks (not wired up yet)

Nothing outside this file knows which mode is on, so switching is one line in .env
and the frontend never notices.
"""
from __future__ import annotations

from eth_account import Account
from web3 import Web3

import config
import db


def get_or_create_wallet(user_id: str) -> str:
    mode = _mode()
    wallet = db.get_wallet(user_id, mode)
    if wallet:
        return wallet["address"]
    if mode == "test":
        account = Account.create()
        db.save_wallet(user_id, "test", account.address, private_key=Web3.to_hex(account.key))
        return account.address
    return _circle_create_wallet(user_id)


def send_tx(user_id: str, to: str, data: str) -> str:
    mode = _mode()
    wallet = db.get_wallet(user_id, mode)
    if wallet is None:
        raise RuntimeError(f"User {user_id} has no {mode} wallet")
    if mode == "test":
        import rpc  # only needed with a real chain

        receipt = rpc.send_transaction(wallet["private_key"], to, data)
        return Web3.to_hex(receipt["transactionHash"])
    return _circle_send_tx(wallet, to, data)


def needs_gas_topup() -> bool:
    """Test wallets pay their own Arc fees; Circle wallets get theirs paid by Gas Station."""
    return _mode() == "test"


def _mode() -> str:
    if config.WALLET_MODE not in ("test", "circle"):
        raise RuntimeError(f"WALLET_MODE must be 'test' or 'circle', not {config.WALLET_MODE!r}")
    return config.WALLET_MODE


# --- Circle developer-controlled wallets ------------------------------------------
# To do once we have a Circle API key and entity secret: create one wallet set, then one
# smart-contract-account wallet per user on Arc testnet, and send transactions with the
# contract-execution endpoint so Gas Station pays the fees.
def _circle_create_wallet(user_id: str) -> str:
    raise RuntimeError("WALLET_MODE=circle isn't wired up yet. Use WALLET_MODE=test for now.")


def _circle_send_tx(wallet, to: str, data: str) -> str:
    raise RuntimeError("WALLET_MODE=circle isn't wired up yet. Use WALLET_MODE=test for now.")
