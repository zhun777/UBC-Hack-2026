"""SQLite storage for what the blockchain doesn't know.

  users     email -> user ID
  wallets   each user's wallet address (and, in test mode, its private key)
  orders    payment requests from cashier screens
  payouts   (mock) local-currency payouts to brands
  history   the earned/spent list on the home screen
  fundings  (mock) brands paying USD in for the rewards they issue
  kv        small bits of state, like the last block the watcher read

The database file (app.db) holds test private keys. It's in .gitignore: never commit it.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import config
import units

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id         TEXT PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallets (
  user_id          TEXT NOT NULL,
  mode             TEXT NOT NULL,          -- 'test' or 'circle'
  address          TEXT NOT NULL,
  private_key      TEXT,                   -- test mode only
  circle_wallet_id TEXT,                   -- circle mode only
  created_at       TEXT NOT NULL,
  PRIMARY KEY (user_id, mode)
);

CREATE TABLE IF NOT EXISTS orders (
  code                 TEXT PRIMARY KEY,   -- "7K2M9Q"
  order_id_hash        TEXT NOT NULL UNIQUE, -- keccak256(code), how Spent events name the order
  brand                TEXT NOT NULL,
  branch               TEXT NOT NULL,
  amount_minor         INTEGER NOT NULL,
  currency             TEXT NOT NULL,
  amount_usd_cents     INTEGER NOT NULL,
  status               TEXT NOT NULL,      -- 'unpaid', 'paying' (transaction in flight), 'paid'
  points_applied       INTEGER,
  card_remainder_minor INTEGER,
  tx_hash              TEXT,
  paid_by              TEXT,
  created_at           TEXT NOT NULL,
  paid_at              TEXT
);

CREATE TABLE IF NOT EXISTS payouts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  order_code  TEXT NOT NULL UNIQUE,        -- one payout per order, however often we see its event
  brand       TEXT NOT NULL,
  branch      TEXT NOT NULL,
  usdc_cents  INTEGER NOT NULL,
  local_minor INTEGER NOT NULL,
  currency    TEXT NOT NULL,
  status      TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    TEXT NOT NULL,
  type       TEXT NOT NULL,                -- 'earned' or 'spent'
  points     INTEGER NOT NULL,
  brand      TEXT NOT NULL,
  tx_hash    TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (tx_hash, type)
);

CREATE TABLE IF NOT EXISTS fundings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  brand      TEXT NOT NULL,
  usd_cents  INTEGER NOT NULL,
  tx_hash    TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def connect():
    """A connection that commits when the block ends, or rolls back on an error."""
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


# --- Users ---------------------------------------------------------------------
def get_user(user_id: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(email: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def create_user(email: str):
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, created_at) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), email, now_iso()),
        )
    return get_user_by_email(email)


# --- Wallets -------------------------------------------------------------------
def get_wallet(user_id: str, mode: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM wallets WHERE user_id = ? AND mode = ?", (user_id, mode)
        ).fetchone()


def save_wallet(user_id: str, mode: str, address: str, private_key: str | None = None,
                circle_wallet_id: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO wallets (user_id, mode, address, private_key, circle_wallet_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, mode, address, private_key, circle_wallet_id, now_iso()),
        )


def find_user_id_by_address(address: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM wallets WHERE lower(address) = lower(?)", (address,)
        ).fetchone()
    return row["user_id"] if row else None


# --- Orders --------------------------------------------------------------------
def create_order(brand: str, branch: str, amount_minor: int, currency: str, amount_usd_cents: int):
    for _ in range(20):
        code = units.new_order_code()
        try:
            with connect() as conn:
                conn.execute(
                    "INSERT INTO orders (code, order_id_hash, brand, branch, amount_minor, currency,"
                    " amount_usd_cents, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'unpaid', ?)",
                    (code, units.id_hash(code), brand, branch, amount_minor, currency,
                     amount_usd_cents, now_iso()),
                )
            return get_order(code)
        except sqlite3.IntegrityError:
            continue  # code already taken; try another
    raise RuntimeError("Couldn't generate a unique order code")


def get_order(code: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM orders WHERE code = ?", (code,)).fetchone()


def get_order_by_id_hash(order_id_hash: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE order_id_hash = ?", (order_id_hash.lower(),)
        ).fetchone()


def claim_order(code: str) -> bool:
    """Marks an unpaid order as 'paying'. False if it's already paid or being paid,
    so two taps on Pay can't send two transactions."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE orders SET status = 'paying' WHERE code = ? AND status = 'unpaid'", (code,)
        )
        return cur.rowcount == 1


def release_order(code: str) -> None:
    """Puts a 'paying' order back to 'unpaid' after its transaction failed."""
    with connect() as conn:
        conn.execute("UPDATE orders SET status = 'unpaid' WHERE code = ? AND status = 'paying'", (code,))


def record_payment(code: str, points: int, card_remainder_minor: int, tx_hash: str,
                   user_id: str | None, payout_local_minor: int) -> bool:
    """Marks the order paid and writes its payout and the user's history entry, all at once.
    Returns False if the order was already paid (we've seen this payment before)."""
    now = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "UPDATE orders SET status = 'paid', points_applied = ?, card_remainder_minor = ?,"
            " tx_hash = ?, paid_by = ?, paid_at = ? WHERE code = ? AND status != 'paid'",
            (points, card_remainder_minor, tx_hash, user_id, now, code),
        )
        if cur.rowcount == 0:
            return False
        order = conn.execute("SELECT * FROM orders WHERE code = ?", (code,)).fetchone()
        conn.execute(
            "INSERT OR IGNORE INTO payouts (order_code, brand, branch, usdc_cents, local_minor,"
            " currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'paid_mock', ?)",
            (code, order["brand"], order["branch"], points, payout_local_minor, order["currency"], now),
        )
        if user_id:
            conn.execute(
                "INSERT OR IGNORE INTO history (user_id, type, points, brand, tx_hash, created_at)"
                " VALUES (?, 'spent', ?, ?, ?, ?)",
                (user_id, points, order["brand"], tx_hash, now),
            )
    return True


# --- Payouts, history, fundings ------------------------------------------------
def list_payouts():
    with connect() as conn:
        return conn.execute("SELECT * FROM payouts ORDER BY id DESC").fetchall()


def add_history(user_id: str, type_: str, points: int, brand: str, tx_hash: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO history (user_id, type, points, brand, tx_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, type_, points, brand, tx_hash, now_iso()),
        )


def list_history(user_id: str, limit: int = 50):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()


def add_funding(brand: str, usd_cents: int, tx_hash: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO fundings (brand, usd_cents, tx_hash, created_at) VALUES (?, ?, ?, ?)",
            (brand, usd_cents, tx_hash, now_iso()),
        )


# --- Key-value -----------------------------------------------------------------
def kv_get(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def kv_set(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
