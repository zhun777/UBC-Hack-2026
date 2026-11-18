"""Makes the network wallet (the vault owner) and saves its key in backend/.env.

    .venv/bin/python scripts/new_network_wallet.py

Prints only the address, never the key. Then:
  1. Get test USDC for that address from the Circle faucet (it pays every reward and fee).
  2. Send the address (not the key) to whoever deploys the contracts, so it becomes the owner.

If NETWORK_PRIVATE_KEY is already set, this just prints its address.
"""
import re
import shutil
from pathlib import Path

from eth_account import Account
from web3 import Web3

ENV = Path(__file__).resolve().parent.parent / ".env"
EXAMPLE = ENV.with_name(".env.example")


def main():
    if not ENV.exists():
        shutil.copy(EXAMPLE, ENV)
        print("Created backend/.env from .env.example")
    text = ENV.read_text()

    existing = re.search(r"^NETWORK_PRIVATE_KEY=(\S+)", text, flags=re.M)
    if existing:
        print(f"NETWORK_PRIVATE_KEY is already set. Its address is {Account.from_key(existing.group(1)).address}")
        return

    account = Account.create()
    line = f"NETWORK_PRIVATE_KEY={Web3.to_hex(account.key)}"
    if re.search(r"^NETWORK_PRIVATE_KEY=\s*$", text, flags=re.M):
        text = re.sub(r"^NETWORK_PRIVATE_KEY=\s*$", line, text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    ENV.write_text(text)
    ENV.chmod(0o600)  # only your user can read it
    print(f"Saved a new network wallet key to backend/.env. Its address is {account.address}")


if __name__ == "__main__":
    main()
