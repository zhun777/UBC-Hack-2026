"""$APP backend: the HTTP API the frontend calls.

Run it from backend/ with:   .venv/bin/uvicorn main:app --reload
Interactive docs:            http://localhost:8000/docs

Endpoints and formats follow the Integration spec in the build plan. The frontend sends
X-User-Id: <user_id> on every request after login (demo only, no passwords).
"""
from __future__ import annotations

import logging
import re
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import db
import units
import wallets
from chain import explorer_url, get_chain
from errors import ApiError, error_body
from watcher import Watcher, handle_spent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    watcher = None
    try:
        chain = get_chain()
        chain.startup()
        watcher = Watcher(chain)
        watcher.start()
    except Exception:
        log.exception("Chain setup failed. The API is up, but chain calls will fail until this is fixed (see GET /health).")
    log.info("Backend ready: CHAIN_MODE=%s WALLET_MODE=%s", config.CHAIN_MODE, config.WALLET_MODE)
    yield
    if watcher:
        watcher.stop()


app = FastAPI(title="$APP backend", lifespan=lifespan)


# --- Errors --------------------------------------------------------------------
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = f"{field}: {first.get('msg', 'invalid value')}" if field else "Invalid request"
    return JSONResponse(status_code=400, content=error_body("INVALID_REQUEST", message))


@app.middleware("http")
async def unexpected_errors(request: Request, call_next):
    """Bugs come back in the usual error format (and with CORS headers) instead of a bare 500."""
    try:
        return await call_next(request)
    except Exception:
        log.exception("Unexpected error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=error_body("SERVER_ERROR", "Something went wrong on our side."))


# Added last so it wraps everything above, including error responses.
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# --- Request bodies --------------------------------------------------------------
class LoginBody(BaseModel):
    email: str = Field(max_length=254)


class PurchaseBody(BaseModel):
    user_id: str | None = None   # falls back to the X-User-Id header
    brand: str
    amount_minor: int = Field(ge=0)
    currency: str


class PaymentRequestBody(BaseModel):
    brand: str
    branch: str | None = None    # defaults to the brand's first branch
    amount_minor: int = Field(gt=0)
    currency: str


# --- Helpers ---------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_user(user_id: str | None):
    user = db.get_user(user_id) if user_id else None
    if user is None:
        raise ApiError("USER_NOT_FOUND", "We couldn't find that user. Please log in again.")
    return user


def require_brand(slug: str) -> dict:
    brand = config.get_brand(slug)
    if brand is None:
        raise ApiError("UNKNOWN_BRAND", f"{slug!r} isn't a member brand.")
    return brand


def require_rate(currency: str):
    rate = config.local_per_usd(currency)
    if rate is None:
        raise ApiError("INVALID_REQUEST", f"We don't support {currency!r} yet.")
    return rate


def require_order(code: str):
    order = db.get_order(units.normalize_order_code(code))
    if order is None:
        raise ApiError("ORDER_NOT_FOUND", "We couldn't find that order code.")
    return order


def order_json(order) -> dict:
    return {
        "order_code": order["code"],
        "brand": order["brand"],
        "brand_name": config.brand_name(order["brand"]),
        "branch": order["branch"],
        "branch_name": config.branch_name(order["brand"], order["branch"]),
        "amount_minor": order["amount_minor"],
        "currency": order["currency"],
        "amount_usd_cents": order["amount_usd_cents"],
        "status": "paid" if order["status"] == "paid" else "unpaid",  # 'paying' still shows as unpaid
        "points_applied": order["points_applied"],
        "card_remainder_minor": order["card_remainder_minor"],
        "tx_hash": order["tx_hash"],
        "explorer_url": explorer_url(order["tx_hash"]),
    }


def top_up_gas_in_background(address: str) -> None:
    """Gives a test wallet a little USDC for fees, without making login wait for it."""
    def run():
        try:
            get_chain().ensure_gas(address)
        except Exception:
            log.warning("Couldn't top up %s for fees; will retry when they pay", address, exc_info=True)
    threading.Thread(target=run, daemon=True).start()


# --- Endpoints -------------------------------------------------------------------
@app.post("/auth/login")
def login(body: LoginBody):
    """Finds or creates the user and their wallet. No password: demo only."""
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ApiError("INVALID_REQUEST", "Please enter a valid email address.")
    user = db.get_user_by_email(email)
    is_new = user is None
    if is_new:
        user = db.create_user(email)
    address = wallets.get_or_create_wallet(user["id"])
    top_up_gas_in_background(address)
    return {"user_id": user["id"], "email": user["email"], "wallet_address": address, "is_new": is_new}


@app.get("/me")
def me(x_user_id: str | None = Header(default=None)):
    """Home screen: points (read from the chain), progress to 100, history."""
    user = require_user(x_user_id)
    address = wallets.get_or_create_wallet(user["id"])
    points = get_chain().points_of(address)
    return {
        "user_id": user["id"],
        "email": user["email"],
        "wallet_address": address,
        "points": points,
        "points_value_cents": points,  # 1 point = 1 US cent
        "min_points_to_spend": config.MIN_POINTS_TO_SPEND,
        "history": [
            {
                "type": h["type"],
                "points": h["points"],
                "brand": h["brand"],
                "brand_name": config.brand_name(h["brand"]),
                "tx_hash": h["tx_hash"],
                "explorer_url": explorer_url(h["tx_hash"]),
                "at": h["created_at"],
            }
            for h in db.list_history(user["id"])
        ],
    }


@app.post("/purchase")
def purchase(body: PurchaseBody, x_user_id: str | None = Header(default=None)):
    """A store's checkout finished (card payment mocked): issue points for it."""
    user = require_user(body.user_id or x_user_id)
    brand = require_brand(body.brand)
    usd_cents = units.to_usd_cents(body.amount_minor, require_rate(body.currency))
    points = units.points_for_purchase(usd_cents)
    tx_hash = None
    if points > 0:
        address = wallets.get_or_create_wallet(user["id"])
        tx_hash = get_chain().issue_reward(address, points, brand["slug"])
        db.add_history(user["id"], "earned", points, brand["slug"], tx_hash)
        # Mock: the brand "pays in" USD for the reward. Onchain, the network wallet funds the
        # brand's USDC budget for it (fundBrand) when the budget runs short.
        db.add_funding(brand["slug"], points, tx_hash)
        log.info("%s funded $%.2f (mock USD in): %d points to %s", brand["name"], points / 100, points, user["email"])
    return {"points_earned": points, "tx_hash": tx_hash, "explorer_url": explorer_url(tx_hash)}


@app.post("/payment-request")
def payment_request(body: PaymentRequestBody):
    """Cashier screen rings up an order. Nothing onchain yet."""
    brand = require_brand(body.brand)
    branch = config.resolve_branch(brand, body.branch)
    if branch is None:
        raise ApiError("UNKNOWN_BRAND", f"{body.branch!r} isn't a branch of {brand['name']}.")
    currency = body.currency.strip().upper()
    usd_cents = units.to_usd_cents(body.amount_minor, require_rate(currency))
    if usd_cents < 1:
        raise ApiError("INVALID_REQUEST", "The amount is too small.")
    order = db.create_order(brand["slug"], branch, body.amount_minor, currency, usd_cents)
    return {
        "order_code": order["code"],
        "amount_usd_cents": usd_cents,
        "status": "unpaid",
        "qr_payload": f"apprewards://pay?order={order['code']}",
    }


@app.get("/orders/{code}")
def get_order(code: str):
    """Pay screen shows it; cashier screen polls it until status is 'paid'."""
    return order_json(require_order(code))


@app.post("/orders/{code}/pay")
def pay_order(code: str, x_user_id: str | None = Header(default=None)):
    """Pay with points: the user's wallet calls spendAtBrand, then we handle its Spent event."""
    user = require_user(x_user_id)
    order = require_order(code)
    if order["status"] != "unpaid":
        raise ApiError("ORDER_ALREADY_PAID", "This order has already been paid.")

    chain = get_chain()
    address = wallets.get_or_create_wallet(user["id"])
    balance = chain.points_of(address)
    if balance < config.MIN_POINTS_TO_SPEND:
        raise ApiError("BELOW_THRESHOLD", f"You need at least {config.MIN_POINTS_TO_SPEND} points to pay.")
    points = units.points_to_apply(balance, order["amount_usd_cents"])

    if not db.claim_order(order["code"]):  # someone else is paying it right now
        raise ApiError("ORDER_ALREADY_PAID", "This order has already been paid.")
    try:
        chain.ensure_gas(address)
        event = chain.spend_at_brand(user["id"], address, order["brand"], order["branch"], order["code"], points)
    except Exception:
        db.release_order(order["code"])
        raise

    handle_spent(event)  # same code the watcher runs; this is what turns the cashier screen green
    order = db.get_order(order["code"])
    if order["status"] != "paid":
        raise ApiError("CHAIN_ERROR", "The payment went through onchain but didn't match this order.")
    return {
        "status": "paid",
        "points_applied": order["points_applied"],
        "card_remainder_minor": order["card_remainder_minor"],
        "tx_hash": order["tx_hash"],
        "explorer_url": explorer_url(order["tx_hash"]),
    }


@app.get("/payouts")
def payouts():
    """Brand payouts screen, newest first. Local-currency payouts are mocked."""
    return [
        {
            "brand": p["brand"],
            "brand_name": config.brand_name(p["brand"]),
            "branch": p["branch"],
            "order_code": p["order_code"],
            "usdc_cents": p["usdc_cents"],
            "local_minor": p["local_minor"],
            "currency": p["currency"],
            "status": p["status"],
            "at": p["created_at"],
        }
        for p in db.list_payouts()
    ]


@app.get("/health")
def health():
    """For us, not the frontend: which modes are on and whether the chain is reachable."""
    info = {"ok": True, "chain_mode": config.CHAIN_MODE, "wallet_mode": config.WALLET_MODE,
            "min_points_to_spend": config.MIN_POINTS_TO_SPEND}
    try:
        info.update(get_chain().status())
    except Exception as exc:
        info.update(ok=False, chain_error=str(exc))
    return info
