"""Turns Spent events from the vault into paid orders and (mock) payouts.

handle_spent() runs for every Spent event we see:
  - straight from the receipt, inside POST /orders/{code}/pay (the fast path)
  - from the polling loop below, which reads new Spent events every few seconds
    (catches payments the pay endpoint didn't finish, e.g. if the server restarted)
It's safe to run twice for the same event: the second time does nothing.
"""
from __future__ import annotations

import logging
import threading

import config
import db
import units
from chain import SpentEvent

log = logging.getLogger("watcher")

MAX_BLOCKS_PER_POLL = 1000


def handle_spent(event: SpentEvent) -> bool:
    """Marks the event's order paid and writes its payout. True if this call did it."""
    order = db.get_order_by_id_hash(event.order_id)
    if order is None:
        log.warning("Spent event for an order we don't know (%s), tx %s", event.order_id, event.tx_hash)
        return False
    if order["status"] == "paid":
        return False
    problem = _mismatch(order, event)
    if problem:
        log.warning("Spent event doesn't match order %s: %s (tx %s)", order["code"], problem, event.tx_hash)
        return False

    rate = config.local_per_usd(order["currency"])
    paid_local = units.from_usd_cents(event.points, rate)       # what the points are worth in SGD etc.
    card_remainder = max(0, order["amount_minor"] - paid_local)  # the rest is paid by card (mock)
    user_id = db.find_user_id_by_address(event.user)
    if not db.record_payment(order["code"], event.points, card_remainder, event.tx_hash, user_id, paid_local):
        return False
    log.info("Order %s paid with %d points. Payout to %s: $%.2f USDC -> %s %.2f (mock)",
             order["code"], event.points, config.brand_name(order["brand"]),
             event.points / 100, order["currency"], paid_local / 100)
    return True


def _mismatch(order, event: SpentEvent) -> str | None:
    if event.brand_id != units.id_hash(order["brand"]):
        return "wrong brand"
    if event.branch_id != units.id_hash(order["branch"]):
        return "wrong branch"
    if event.points > order["amount_usd_cents"]:
        return f"{event.points} points is more than the order's {order['amount_usd_cents']} cents"
    if event.usdc_amount != units.cents_to_usdc_units(event.points):
        return "USDC amount doesn't match the points"
    return None


class Watcher:
    """Background loop: every few seconds, read new Spent events and handle them."""

    def __init__(self, chain, interval: float | None = None):
        self.chain = chain
        self.interval = interval or config.WATCHER_INTERVAL_SECONDS
        self.state_key = f"watcher_last_block_{config.CHAIN_MODE}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="spent-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def poll_once(self) -> int:
        """Handles Spent events in blocks we haven't read yet. Returns how many orders it marked paid."""
        latest = self.chain.latest_block()
        last = db.kv_get(self.state_key)
        if last is None:  # first run ever: start watching from now
            db.kv_set(self.state_key, str(latest))
            return 0
        start = int(last) + 1
        if start > latest:
            return 0
        end = min(latest, start + MAX_BLOCKS_PER_POLL - 1)
        handled = sum(handle_spent(event) for event in self.chain.spent_events(start, end))
        db.kv_set(self.state_key, str(end))
        return handled

    def _run(self) -> None:
        log.info("Watching for Spent events every %.1fs", self.interval)
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                log.exception("Watcher poll failed; will retry")
            self._stop.wait(self.interval)
