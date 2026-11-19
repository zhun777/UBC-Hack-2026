"""Settings for the backend, read once at startup.

Where they come from:
  backend/.env                  secrets and modes (copy .env.example to make it)
  contracts/deployments.json    contract addresses, committed by the contracts role after deploying
  contracts/abi/                contract ABIs, also from the contracts role
  backend/brands.json           member brands and their branches
"""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger("config")

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent

# Values already set in the environment win over .env (the tests rely on this).
load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# --- Modes -------------------------------------------------------------------
# CHAIN_MODE=fake: no blockchain; points live in SQLite. Use until the contracts are deployed.
# CHAIN_MODE=arc:  real calls to APPToken and RewardsVault on Arc testnet.
CHAIN_MODE = _env("CHAIN_MODE", "fake").lower()
# WALLET_MODE=test:   the backend makes one key per user and keeps it in SQLite (test only).
# WALLET_MODE=circle: Circle developer-controlled wallets.
WALLET_MODE = _env("WALLET_MODE", "test").lower()

# --- Secrets -----------------------------------------------------------------
NETWORK_PRIVATE_KEY = _env("NETWORK_PRIVATE_KEY")
CIRCLE_API_KEY = _env("CIRCLE_API_KEY")
CIRCLE_ENTITY_SECRET = _env("CIRCLE_ENTITY_SECRET")

# --- Rules and tuning ----------------------------------------------------------
MIN_POINTS_TO_SPEND = int(_env("MIN_POINTS_TO_SPEND", "100"))  # the vault has no minimum; only we enforce it
GAS_TOPUP_CENTS = int(_env("GAS_TOPUP_CENTS", "20"))            # test USDC given to each test wallet for fees
WATCHER_INTERVAL_SECONDS = float(_env("WATCHER_INTERVAL_SECONDS", "2"))
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]
DB_PATH = Path(_env("DB_PATH") or BACKEND_DIR / "app.db")
DEPLOYMENTS_PATH = Path(_env("DEPLOYMENTS_PATH") or REPO_DIR / "contracts" / "deployments.json")


# --- Exchange rates ------------------------------------------------------------
def local_per_usd(currency: str) -> Decimal | None:
    """Fixed demo rate: how much of `currency` one US dollar buys. None if unsupported.

    USD is always 1. Any other currency needs <CURRENCY>_PER_USD in .env, e.g. SGD_PER_USD=1.35.
    Amounts are assumed to have 2 decimal places (cents), true for USD and SGD.
    """
    currency = currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        return None
    if currency == "USD":
        return Decimal(1)
    raw = _env(f"{currency}_PER_USD")
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        return None
    return rate if rate > 0 else None


# --- Contracts -------------------------------------------------------------------
def load_deployments() -> dict:
    """contracts/deployments.json, or {} until the contracts role commits it."""
    if not DEPLOYMENTS_PATH.exists():
        return {}
    return json.loads(DEPLOYMENTS_PATH.read_text())


def rpc_url() -> str:
    return _env("RPC_URL") or load_deployments().get("rpcUrl", "")


def explorer_base() -> str:
    return (_env("EXPLORER_URL") or load_deployments().get("explorerUrl", "")).rstrip("/")


def load_abi(name: str) -> list | None:
    """The ABI the contracts role committed, as a bare list or inside a Foundry artifact."""
    contracts = REPO_DIR / "contracts"
    for path in (
        contracts / "abi" / f"{name}.json",
        contracts / "abi" / f"{name}.abi.json",
        contracts / "out" / f"{name}.sol" / f"{name}.json",
    ):
        if path.exists():
            data = json.loads(path.read_text())
            abi = data.get("abi") if isinstance(data, dict) else data
            if isinstance(abi, list):
                log.info("Using %s ABI from %s", name, path.relative_to(REPO_DIR))
                return abi
    return None


# --- Brands --------------------------------------------------------------------
BRANDS: dict[str, dict] = {b["slug"]: b for b in json.loads((BACKEND_DIR / "brands.json").read_text())}


def get_brand(slug: str) -> dict | None:
    return BRANDS.get(slug)


def resolve_branch(brand: dict, branch: str | None) -> str | None:
    """The branch slug to use for an order, or None if `branch` isn't one of the brand's.

    No branch given: the brand's first branch, or the brand's own slug if it has none.
    """
    slugs = [b["slug"] for b in brand.get("branches", [])]
    if not branch:
        return slugs[0] if slugs else brand["slug"]
    if branch in slugs or branch == brand["slug"]:
        return branch
    return None


def brand_name(slug: str) -> str:
    brand = BRANDS.get(slug)
    return brand["name"] if brand else slug


def branch_name(brand_slug: str, branch_slug: str) -> str:
    for branch in BRANDS.get(brand_slug, {}).get("branches", []):
        if branch["slug"] == branch_slug:
            return branch["name"]
    return brand_name(brand_slug)
