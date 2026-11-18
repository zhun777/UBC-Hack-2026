"""Every conversion between API units and onchain units lives here.

API side (what the frontend sends and sees):
  money   integer minor units + currency code: {"amount_minor": 135, "currency": "SGD"} = S$1.35
  points  whole numbers; 1 point = 1 US cent
  IDs     readable text: "cafe-sg", "cafe-sg-orchard", order code "7K2M9Q"

Chain side (what the contracts take):
  USDC    6 decimals, so 1 cent = 10,000 units and $1.50 = 1,500,000
  APP     0 decimals, so 150 points = 150
  IDs     bytes32 = keccak256 of the text

Exchange-rate math uses Decimal, never floats: 135 / 1.35 must be exactly 100.
"""
from __future__ import annotations

import secrets
from decimal import ROUND_FLOOR, Decimal

from web3 import Web3

USDC_UNITS_PER_CENT = 10_000
ORDER_CODE_LENGTH = 6
ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, so codes are easy to type


# --- Money -------------------------------------------------------------------
def to_usd_cents(amount_minor: int, local_per_usd: Decimal) -> int:
    """Local minor units -> US cents, rounded down. S$1.35 at 1.35 SGD per USD -> 100."""
    return int((Decimal(amount_minor) / local_per_usd).to_integral_value(rounding=ROUND_FLOOR))


def from_usd_cents(usd_cents: int, local_per_usd: Decimal) -> int:
    """US cents -> local minor units, rounded down. 100 cents at 1.35 -> 135 (S$1.35)."""
    return int((Decimal(usd_cents) * local_per_usd).to_integral_value(rounding=ROUND_FLOOR))


def points_for_purchase(usd_cents: int) -> int:
    """$1 spent = 1 point, rounded down to whole dollars. $50.99 -> 50."""
    return usd_cents // 100


def points_to_apply(balance: int, order_usd_cents: int) -> int:
    """All the user's points, up to the order's value (1 point = 1 cent)."""
    return min(balance, order_usd_cents)


def cents_to_usdc_units(cents: int) -> int:
    return cents * USDC_UNITS_PER_CENT


# --- IDs ---------------------------------------------------------------------
def id_bytes(text: str) -> bytes:
    """keccak256 of a slug or order code: the bytes32 the contract takes."""
    return bytes(Web3.keccak(text=text))


def id_hash(text: str) -> str:
    """Same as id_bytes, as a lowercase 0x hex string (how we store and compare it)."""
    return Web3.to_hex(id_bytes(text))


def new_order_code() -> str:
    return "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(ORDER_CODE_LENGTH))


def normalize_order_code(code: str) -> str:
    return code.strip().upper()
