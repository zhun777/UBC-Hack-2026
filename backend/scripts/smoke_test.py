"""Runs the whole demo against a running backend.

    .venv/bin/python scripts/smoke_test.py                  # http://localhost:8000
    .venv/bin/python scripts/smoke_test.py https://...      # somewhere else

Earns 150 points at Brand A, rings up S$1.35 at the Singapore café, pays with points,
then checks the order turned paid and a payout appeared. With CHAIN_MODE=arc this sends
real testnet transactions and uses $1.50 of the network wallet's test USDC.
"""
import sys
import time
import uuid

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def call(method, path, **kwargs):
    r = httpx.request(method, BASE + path, timeout=120, **kwargs)
    if r.status_code >= 400:
        sys.exit(f"FAIL  {method} {path} -> {r.status_code} {r.text}")
    return r.json()


def check(ok, message):
    if not ok:
        sys.exit(f"FAIL  {message}")
    print(f"ok    {message}")


def main():
    health = call("GET", "/health")
    print(f"Backend at {BASE}: CHAIN_MODE={health['chain_mode']} WALLET_MODE={health['wallet_mode']}")

    user = call("POST", "/auth/login", json={"email": f"smoke-{uuid.uuid4().hex[:8]}@example.com"})
    me_headers = {"X-User-Id": user["user_id"]}
    check(user["is_new"], f"logged in as {user['email']}, wallet {user['wallet_address']}")

    for dollars in (50, 100):
        earned = call("POST", "/purchase", json={"user_id": user["user_id"], "brand": "brand-a-us",
                                                 "amount_minor": dollars * 100, "currency": "USD"})
        check(earned["points_earned"] == dollars, f"${dollars} at Brand A earned {earned['points_earned']} points"
              + (f"  {earned['explorer_url']}" if earned["explorer_url"] else ""))

    points = call("GET", "/me", headers=me_headers)["points"]
    check(points == 150, f"balance is {points} points")

    order = call("POST", "/payment-request", json={"brand": "cafe-sg", "branch": "cafe-sg-orchard",
                                                   "amount_minor": 135, "currency": "SGD"})
    code = order["order_code"]
    check(order["amount_usd_cents"] == 100, f"café rang up S$1.35 as order {code} ($1.00)")

    started = time.time()
    paid = call("POST", f"/orders/{code}/pay", headers=me_headers)
    check(paid["points_applied"] == 100, f"paid with {paid['points_applied']} points in {time.time() - started:.1f}s"
          + (f"  {paid['explorer_url']}" if paid["explorer_url"] else ""))

    deadline = time.time() + 15
    while call("GET", f"/orders/{code}")["status"] != "paid":
        if time.time() > deadline:
            sys.exit("FAIL  cashier screen never saw the order as paid")
        time.sleep(1.5)
    check(True, "cashier screen sees the order as paid")

    payout = next((p for p in call("GET", "/payouts") if p["order_code"] == code), None)
    check(payout is not None and payout["local_minor"] == 135,
          f"payout logged: ${payout['usdc_cents'] / 100:.2f} USDC -> S${payout['local_minor'] / 100:.2f} (mock)")

    points = call("GET", "/me", headers=me_headers)["points"]
    check(points == 50, f"balance is now {points} points")
    print("All good.")


if __name__ == "__main__":
    main()
