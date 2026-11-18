"""The whole demo flow through the HTTP API, on the fake chain."""
import time

import db
import watcher
from chain import get_chain


def login(client, email="mia@example.com"):
    r = client.post("/auth/login", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()


def as_user(user):
    return {"X-User-Id": user["user_id"]}


def buy(client, user, dollars):
    r = client.post("/purchase", json={"user_id": user["user_id"], "brand": "brand-a-us",
                                       "amount_minor": dollars * 100, "currency": "USD"})
    assert r.status_code == 200, r.text
    return r.json()


def ring_up(client, sgd_minor):
    r = client.post("/payment-request", json={"brand": "cafe-sg", "branch": "cafe-sg-orchard",
                                              "amount_minor": sgd_minor, "currency": "SGD"})
    assert r.status_code == 200, r.text
    return r.json()


def error_code(response):
    return response.json()["error"]["code"]


def test_login_creates_user_once(client):
    first = login(client, " Mia@Example.com ")
    assert first["is_new"] is True
    assert first["email"] == "mia@example.com"
    assert first["wallet_address"].startswith("0x")
    again = login(client, "mia@example.com")
    assert again["is_new"] is False
    assert again["user_id"] == first["user_id"]
    assert again["wallet_address"] == first["wallet_address"]


def test_login_rejects_bad_email(client):
    r = client.post("/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 400
    assert error_code(r) == "INVALID_REQUEST"


def test_purchase_earns_points(client):
    user = login(client)
    earned = buy(client, user, 50)
    assert earned["points_earned"] == 50
    assert earned["tx_hash"].startswith("0x")
    assert earned["explorer_url"] is None  # no explorer in fake mode

    me = client.get("/me", headers=as_user(user)).json()
    assert me["points"] == 50
    assert me["points_value_cents"] == 50
    assert me["min_points_to_spend"] == 100
    assert me["history"][0]["type"] == "earned"
    assert me["history"][0]["points"] == 50
    assert me["history"][0]["brand"] == "brand-a-us"


def test_purchase_rounds_down_to_whole_dollars(client):
    user = login(client)
    r = client.post("/purchase", json={"user_id": user["user_id"], "brand": "brand-a-us",
                                       "amount_minor": 5099, "currency": "USD"})
    assert r.json()["points_earned"] == 50


def test_full_demo_flow(client):
    user = login(client)
    buy(client, user, 50)

    # Café cashier rings up S$1.35
    order = ring_up(client, 135)
    code = order["order_code"]
    assert order["amount_usd_cents"] == 100
    assert order["status"] == "unpaid"
    assert order["qr_payload"] == f"apprewards://pay?order={code}"

    # 50 points isn't enough to spend yet
    r = client.post(f"/orders/{code}/pay", headers=as_user(user))
    assert r.status_code == 400
    assert error_code(r) == "BELOW_THRESHOLD"

    buy(client, user, 100)  # now 150 points

    # Pay screen shows the order
    shown = client.get(f"/orders/{code}").json()
    assert (shown["brand"], shown["branch"], shown["amount_minor"], shown["currency"]) == \
        ("cafe-sg", "cafe-sg-orchard", 135, "SGD")
    assert shown["brand_name"] == "Brand A Café"
    assert shown["branch_name"] == "Orchard Road"
    assert shown["status"] == "unpaid"

    # Pay with points (typed code in lowercase still works)
    r = client.post(f"/orders/{code.lower()}/pay", headers=as_user(user))
    assert r.status_code == 200, r.text
    paid = r.json()
    assert paid["status"] == "paid"
    assert paid["points_applied"] == 100
    assert paid["card_remainder_minor"] == 0
    assert paid["tx_hash"].startswith("0x")

    # Cashier screen's next poll sees it paid
    assert client.get(f"/orders/{code}").json()["status"] == "paid"

    me = client.get("/me", headers=as_user(user)).json()
    assert me["points"] == 50
    assert [h["type"] for h in me["history"]] == ["spent", "earned", "earned"]

    payouts = client.get("/payouts").json()
    assert len(payouts) == 1
    assert {k: payouts[0][k] for k in ("brand", "branch", "order_code", "usdc_cents", "local_minor",
                                       "currency", "status")} == {
        "brand": "cafe-sg", "branch": "cafe-sg-orchard", "order_code": code,
        "usdc_cents": 100, "local_minor": 135, "currency": "SGD", "status": "paid_mock"}

    # Each order can be paid once
    r = client.post(f"/orders/{code}/pay", headers=as_user(user))
    assert r.status_code == 409
    assert error_code(r) == "ORDER_ALREADY_PAID"


def test_points_short_of_price_rest_paid_by_card(client):
    user = login(client)
    buy(client, user, 150)
    code = ring_up(client, 270)["order_code"]  # S$2.70 = $2.00
    paid = client.post(f"/orders/{code}/pay", headers=as_user(user)).json()
    assert paid["points_applied"] == 150
    assert paid["card_remainder_minor"] == 68  # S$2.70 - S$2.02 (150 points at 1.35, rounded down)


def test_not_found_errors(client):
    user = login(client)
    assert error_code(client.get("/orders/ZZZZZZ")) == "ORDER_NOT_FOUND"
    assert error_code(client.post("/orders/ZZZZZZ/pay", headers=as_user(user))) == "ORDER_NOT_FOUND"
    assert error_code(client.get("/me", headers={"X-User-Id": "nobody"})) == "USER_NOT_FOUND"
    assert error_code(client.get("/me")) == "USER_NOT_FOUND"


def test_unknown_brand_branch_and_currency(client):
    user = login(client)
    r = client.post("/purchase", json={"user_id": user["user_id"], "brand": "nope",
                                       "amount_minor": 100, "currency": "USD"})
    assert error_code(r) == "UNKNOWN_BRAND"
    r = client.post("/payment-request", json={"brand": "cafe-sg", "branch": "nope",
                                              "amount_minor": 135, "currency": "SGD"})
    assert error_code(r) == "UNKNOWN_BRAND"
    r = client.post("/payment-request", json={"brand": "cafe-sg", "amount_minor": 135, "currency": "XYZ"})
    assert error_code(r) == "INVALID_REQUEST"


def test_bad_request_uses_the_error_format(client):
    r = client.post("/purchase", json={})
    assert r.status_code == 400
    assert error_code(r) == "INVALID_REQUEST"


def test_same_event_twice_pays_out_once(client):
    user = login(client)
    buy(client, user, 150)
    code = ring_up(client, 135)["order_code"]
    client.post(f"/orders/{code}/pay", headers=as_user(user))

    chain = get_chain()
    events = chain.spent_events(0, chain.latest_block())
    assert len(events) == 1
    assert watcher.handle_spent(events[0]) is False  # already handled
    assert len(client.get("/payouts").json()) == 1


def test_watcher_alone_marks_order_paid(client):
    """If the pay endpoint never finishes (say the server restarted), the watcher still
    turns the cashier screen green from the Spent event."""
    user = login(client)
    buy(client, user, 150)
    code = ring_up(client, 135)["order_code"]
    db.kv_set("watcher_last_block_fake", "0")

    # Pay "onchain" directly, skipping the endpoint
    get_chain().spend_at_brand(user["user_id"], user["wallet_address"], "cafe-sg", "cafe-sg-orchard", code, 100)

    deadline = time.time() + 3
    while client.get(f"/orders/{code}").json()["status"] != "paid":
        assert time.time() < deadline, "watcher didn't mark the order paid"
        time.sleep(0.05)
    assert len(client.get("/payouts").json()) == 1
