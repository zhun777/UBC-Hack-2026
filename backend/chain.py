"""Everything the backend does with the contracts, behind one set of methods.

  ArcChain   the real APPToken and RewardsVault on Arc testnet     (CHAIN_MODE=arc)
  FakeChain  pretends to be them, keeping points in SQLite          (CHAIN_MODE=fake)

FakeChain enforces the same rules as the vault, so the frontend can build against a
working API before the contracts are deployed. Switching is one line in .env.
"""
from __future__ import annotations

import functools
import logging
import secrets
from dataclasses import dataclass

from eth_abi import decode as decode_abi
from web3 import Web3
from web3.logs import DISCARD

import config
import db
import units
import wallets
from errors import ApiError

log = logging.getLogger("chain")


@dataclass
class SpentEvent:
    """One RewardsVault Spent event: a user paid a brand with points."""
    user: str          # wallet address
    brand_id: str      # bytes32 as lowercase 0x hex = keccak256(brand slug)
    branch_id: str     # keccak256(branch slug)
    order_id: str      # keccak256(order code)
    points: int
    usdc_amount: int   # 6-decimal units sent to the settlement address
    tx_hash: str
    block: int


@functools.lru_cache(maxsize=1)
def get_chain():
    if config.CHAIN_MODE == "fake":
        return FakeChain()
    if config.CHAIN_MODE == "arc":
        return ArcChain()
    raise RuntimeError(f"CHAIN_MODE must be 'fake' or 'arc', not {config.CHAIN_MODE!r}")


def explorer_url(tx_hash: str | None) -> str | None:
    """Link to the transaction on the Arc explorer, for the "Verify onchain" link."""
    if config.CHAIN_MODE != "arc" or not tx_hash:
        return None
    base = config.explorer_base()
    return f"{base}/tx/{tx_hash}" if base else None


# --- ABIs ----------------------------------------------------------------------
def _fn(name, inputs, outputs=(), view=False):
    return {"type": "function", "name": name,
            "inputs": [{"name": n, "type": t} for n, t in inputs],
            "outputs": [{"name": "", "type": t} for t in outputs],
            "stateMutability": "view" if view else "nonpayable"}


ERC20_ABI = [
    _fn("balanceOf", [("account", "address")], ["uint256"], view=True),
    _fn("allowance", [("owner", "address"), ("spender", "address")], ["uint256"], view=True),
    _fn("approve", [("spender", "address"), ("amount", "uint256")], ["bool"]),
    _fn("transfer", [("to", "address"), ("amount", "uint256")], ["bool"]),
]


def _abi(name: str) -> list:
    abi = config.load_abi(name)
    if abi is None:
        raise RuntimeError(f"No {name} ABI in contracts/abi/. Pull the repo, or run contracts/export-abi.sh.")
    return abi


# Vault refusals the frontend has an error code for. Any other refusal comes back as a
# CHAIN_ERROR naming the contract's error, e.g. "InsufficientPoints(500, 120)".
VAULT_ERRORS = {
    "OrderAlreadyPaid": ("ORDER_ALREADY_PAID", "This order has already been paid."),
    "UnknownBrand": ("UNKNOWN_BRAND", "This store isn't registered with the rewards vault."),
    "BrandInactive": ("UNKNOWN_BRAND", "This store is paused in the rewards vault."),
}


def custom_errors(abi: list) -> dict[str, tuple[str, list[str]]]:
    """The contract's custom errors by 4-byte selector: {"0x1234abcd": ("OrderAlreadyPaid", [])}."""
    errors = {}
    for item in abi:
        if item.get("type") == "error":
            types = [i["type"] for i in item.get("inputs", [])]
            selector = Web3.to_hex(Web3.keccak(text=f"{item['name']}({','.join(types)})")[:4])
            errors[selector] = (item["name"], types)
    return errors


def vault_refusal(errors: dict, exc: Exception) -> ApiError | None:
    """If `exc` is the vault reverting with one of its custom errors, that error as an ApiError."""
    data = getattr(exc, "data", None)  # web3 puts the revert data here, e.g. "0x1234abcd..."
    if not isinstance(data, str) or len(data) < 10 or data[:10].lower() not in errors:
        return None
    name, types = errors[data[:10].lower()]
    if name in VAULT_ERRORS:
        return ApiError(*VAULT_ERRORS[name])
    try:
        args = decode_abi(types, bytes.fromhex(data[10:])) if types else ()
    except Exception:
        args = ()
    return ApiError("CHAIN_ERROR", f"The rewards vault refused: {name}({', '.join(map(str, args))})")


def _chain_call(method):
    """Turns any failure talking to Arc into an error the frontend understands."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ApiError:
            raise
        except Exception as exc:
            refusal = vault_refusal(getattr(args[0], "errors", {}), exc) if args else None
            if refusal:
                log.warning("%s: %s", method.__name__, refusal.message)
                raise refusal from exc
            log.exception("%s failed", method.__name__)
            reason = getattr(exc, "message", None) or str(exc) or type(exc).__name__
            raise ApiError("CHAIN_ERROR", f"Blockchain call failed: {reason[:300]}") from exc
    return wrapper


def _dollars(usdc_units: int) -> str:
    return f"{usdc_units / 1_000_000:.2f}"


# --- Real contracts --------------------------------------------------------------
class ArcChain:
    def __init__(self):
        import rpc
        from eth_account import Account

        d = config.load_deployments()
        missing = [k for k in ("appToken", "rewardsVault", "usdc") if not d.get(k) or d[k] == "0x..."]
        if missing:
            raise RuntimeError(
                f"CHAIN_MODE=arc needs {', '.join(missing)} in {config.DEPLOYMENTS_PATH}. "
                "Pull the repo after the contracts are deployed, or set CHAIN_MODE=fake.")
        if not config.NETWORK_PRIVATE_KEY:
            raise RuntimeError("CHAIN_MODE=arc needs NETWORK_PRIVATE_KEY in backend/.env (the vault owner's key)")

        self.rpc = rpc
        self.w3 = rpc.w3()
        self.network = Account.from_key(config.NETWORK_PRIVATE_KEY)
        contract = self.w3.eth.contract
        self.token = contract(address=Web3.to_checksum_address(d["appToken"]), abi=_abi("APPToken"))
        self.vault = contract(address=Web3.to_checksum_address(d["rewardsVault"]), abi=_abi("RewardsVault"))
        self.usdc = contract(address=Web3.to_checksum_address(d["usdc"]), abi=ERC20_ABI)
        self.errors = custom_errors(self.vault.abi)

    def startup(self) -> None:
        owner = self.vault.functions.owner().call()
        if owner.lower() != self.network.address.lower():
            log.error("The RewardsVault owner is %s but NETWORK_PRIVATE_KEY is %s, so earning points will fail. "
                      "Deploy with the network wallet's key, or transfer the vault's ownership to it.",
                      owner, self.network.address)
        # One large approval, so fundBrand can move the network wallet's USDC into brand budgets.
        allowance = self.usdc.functions.allowance(self.network.address, self.vault.address).call()
        if allowance >= 10**11:  # $100,000: plenty for a demo
            return
        log.info("Approving the vault to pull the network wallet's USDC")
        self._send_as_network(self.usdc.address, self.usdc.encode_abi("approve", args=[self.vault.address, 2**256 - 1]))

    @_chain_call
    def points_of(self, address: str) -> int:
        return self.token.functions.balanceOf(address).call()

    @_chain_call
    def issue_reward(self, address: str, points: int, brand: str) -> str:
        """Network wallet calls issueReward: the vault takes points x $0.01 from the brand's
        budget and mints the points. If the budget is short, the network wallet tops it up
        first with fundBrand (in the demo it pays in for the brand)."""
        brand_id = units.id_bytes(brand)
        cost = units.cents_to_usdc_units(points)
        budget = self.vault.functions.getBrand(brand_id).call()[4]  # Brand: settlement, currency, active, exists, budget
        if budget < cost:
            log.info("Funding %s's reward budget with $%s", brand, _dollars(cost - budget))
            self._send_as_network(self.vault.address, self.vault.encode_abi("fundBrand", args=[brand_id, cost - budget]))
        receipt = self._send_as_network(
            self.vault.address, self.vault.encode_abi("issueReward", args=[brand_id, address, points]))
        return Web3.to_hex(receipt["transactionHash"])

    @_chain_call
    def spend_at_brand(self, user_id: str, address: str, brand: str, branch: str,
                       order_code: str, points: int) -> SpentEvent:
        """The user's own wallet calls spendAtBrand, so only their points can be burned."""
        data = self.vault.encode_abi("spendAtBrand", args=[
            units.id_bytes(brand), units.id_bytes(branch), units.id_bytes(order_code), points])
        # Dry run first: if the vault would refuse, we get its reason without paying a fee.
        self.w3.eth.call({"from": address, "to": self.vault.address, "data": data})
        tx_hash = wallets.send_tx(user_id, self.vault.address, data)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise ApiError("CHAIN_ERROR", f"The payment transaction failed onchain ({tx_hash})")
        events = self.vault.events.Spent().process_receipt(receipt, errors=DISCARD)
        if not events:
            raise ApiError("CHAIN_ERROR", f"The payment went through but had no Spent event ({tx_hash})")
        return self._to_spent_event(events[0])

    @_chain_call
    def ensure_gas(self, address: str) -> None:
        """Test wallets pay their own Arc fees (in USDC), so keep a little test USDC in each.

        This sends Arc's USDC as an ERC-20 transfer, which on Arc tops up the same balance
        that pays fees. Circle wallets skip this: Gas Station pays for them.
        """
        if not wallets.needs_gas_topup():
            return
        topup = units.cents_to_usdc_units(config.GAS_TOPUP_CENTS)
        if self.usdc.functions.balanceOf(address).call() >= topup // 2:
            return
        log.info("Topping up %s with $%.2f of test USDC for fees", address, config.GAS_TOPUP_CENTS / 100)
        self._send_as_network(self.usdc.address, self.usdc.encode_abi("transfer", args=[address, topup]))

    @_chain_call
    def latest_block(self) -> int:
        return self.w3.eth.block_number

    @_chain_call
    def spent_events(self, from_block: int, to_block: int) -> list[SpentEvent]:
        logs = self.vault.events.Spent().get_logs(from_block=from_block, to_block=to_block)
        return [self._to_spent_event(e) for e in logs]

    def status(self) -> dict:
        balance = self.usdc.functions.balanceOf
        return {
            "chain_id": self.w3.eth.chain_id,
            "latest_block": self.w3.eth.block_number,
            "network_wallet": self.network.address,
            "network_wallet_usdc": _dollars(balance(self.network.address).call()),
            "vault_usdc": _dollars(balance(self.vault.address).call()),
            "contracts": {"appToken": self.token.address, "rewardsVault": self.vault.address,
                          "usdc": self.usdc.address},
        }

    def _send_as_network(self, to: str, data: str):
        return self.rpc.send_transaction(config.NETWORK_PRIVATE_KEY, to, data)

    @staticmethod
    def _to_spent_event(event) -> SpentEvent:
        args = event["args"]
        return SpentEvent(
            user=args["user"],
            brand_id=Web3.to_hex(args["brandId"]),
            branch_id=Web3.to_hex(args["branchId"]),
            order_id=Web3.to_hex(args["orderId"]),
            points=int(args["points"]),
            usdc_amount=int(args["usdcAmount"]),
            tx_hash=Web3.to_hex(event["transactionHash"]),
            block=event["blockNumber"],
        )


# --- Fake contracts ------------------------------------------------------------
FAKE_SCHEMA = """
CREATE TABLE IF NOT EXISTS fake_balances (
  address TEXT PRIMARY KEY,
  points  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS fake_spent (
  block       INTEGER PRIMARY KEY AUTOINCREMENT,  -- each fake payment gets its own "block"
  user        TEXT NOT NULL,
  brand_id    TEXT NOT NULL,
  branch_id   TEXT NOT NULL,
  order_id    TEXT NOT NULL UNIQUE,
  points      INTEGER NOT NULL,
  usdc_amount INTEGER NOT NULL,
  tx_hash     TEXT NOT NULL
);
"""


def _fake_tx_hash() -> str:
    return "0x" + secrets.token_hex(32)


def _revert(reason: str):
    raise ApiError("CHAIN_ERROR", f"The vault refused the payment: {reason}")


class FakeChain:
    """Stands in for the contracts until they're deployed: same methods, same rules
    (registered brands, the 100-point threshold, each order paid once)."""

    def __init__(self):
        with db.connect() as conn:
            conn.executescript(FAKE_SCHEMA)
        self._registered_brands = {units.id_hash(slug) for slug in config.BRANDS}

    def startup(self) -> None:
        log.warning("CHAIN_MODE=fake: no blockchain calls. Points live in SQLite until you switch to CHAIN_MODE=arc.")

    def points_of(self, address: str) -> int:
        with db.connect() as conn:
            row = conn.execute("SELECT points FROM fake_balances WHERE address = ?", (address.lower(),)).fetchone()
        return row["points"] if row else 0

    def issue_reward(self, address: str, points: int, brand: str) -> str:
        if units.id_hash(brand) not in self._registered_brands:
            raise ApiError("UNKNOWN_BRAND", "This store isn't registered with the rewards vault.")
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO fake_balances (address, points) VALUES (?, ?)"
                " ON CONFLICT(address) DO UPDATE SET points = points + excluded.points",
                (address.lower(), points),
            )
        return _fake_tx_hash()

    def spend_at_brand(self, user_id: str, address: str, brand: str, branch: str,
                       order_code: str, points: int) -> SpentEvent:
        brand_id, branch_id, order_id = units.id_hash(brand), units.id_hash(branch), units.id_hash(order_code)
        tx_hash = _fake_tx_hash()
        with db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")  # read-check-write as one step
            row = conn.execute("SELECT points FROM fake_balances WHERE address = ?", (address.lower(),)).fetchone()
            balance = row["points"] if row else 0
            if brand_id not in self._registered_brands:
                _revert("unknown brand")
            if balance < config.MIN_POINTS_TO_SPEND:
                _revert("below threshold")
            if points <= 0 or points > balance:
                _revert("not enough points")
            if conn.execute("SELECT 1 FROM fake_spent WHERE order_id = ?", (order_id,)).fetchone():
                _revert("order already paid")
            conn.execute("UPDATE fake_balances SET points = points - ? WHERE address = ?", (points, address.lower()))
            cur = conn.execute(
                "INSERT INTO fake_spent (user, brand_id, branch_id, order_id, points, usdc_amount, tx_hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (address, brand_id, branch_id, order_id, points, units.cents_to_usdc_units(points), tx_hash),
            )
            block = cur.lastrowid
        return SpentEvent(user=address, brand_id=brand_id, branch_id=branch_id, order_id=order_id,
                          points=points, usdc_amount=units.cents_to_usdc_units(points),
                          tx_hash=tx_hash, block=block)

    def ensure_gas(self, address: str) -> None:
        pass  # no fees in fake mode

    def latest_block(self) -> int:
        with db.connect() as conn:
            return conn.execute("SELECT COALESCE(MAX(block), 0) AS b FROM fake_spent").fetchone()["b"]

    def spent_events(self, from_block: int, to_block: int) -> list[SpentEvent]:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fake_spent WHERE block BETWEEN ? AND ? ORDER BY block", (from_block, to_block)
            ).fetchall()
        return [SpentEvent(user=r["user"], brand_id=r["brand_id"], branch_id=r["branch_id"],
                           order_id=r["order_id"], points=r["points"], usdc_amount=r["usdc_amount"],
                           tx_hash=r["tx_hash"], block=r["block"]) for r in rows]

    def status(self) -> dict:
        return {"note": "CHAIN_MODE=fake: no blockchain; points are kept in SQLite"}
