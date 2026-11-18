from decimal import Decimal

import units

SGD = Decimal("1.35")
USD = Decimal(1)


def test_local_to_usd_cents_rounds_down():
    assert units.to_usd_cents(135, SGD) == 100   # S$1.35 -> $1.00
    assert units.to_usd_cents(136, SGD) == 100   # S$1.36 -> $1.007 -> $1.00
    assert units.to_usd_cents(5000, USD) == 5000


def test_exchange_math_is_exact():
    # S$0.81 is exactly $0.60, but float math (81 / 1.35) gives 59.999... and rounds down to 59.
    assert units.to_usd_cents(81, SGD) == 60


def test_usd_cents_to_local_rounds_down():
    assert units.from_usd_cents(100, SGD) == 135  # $1.00 -> S$1.35
    assert units.from_usd_cents(150, SGD) == 202  # $1.50 -> S$2.025 -> S$2.02


def test_points_are_whole_dollars_rounded_down():
    assert units.points_for_purchase(5000) == 50   # $50 jacket -> 50 points
    assert units.points_for_purchase(5099) == 50
    assert units.points_for_purchase(99) == 0


def test_usdc_has_six_decimals():
    assert units.cents_to_usdc_units(150) == 1_500_000  # $1.50
    assert units.cents_to_usdc_units(50) == 500_000     # a $50 purchase backs 50 points with $0.50


def test_points_applied_is_capped_at_order_value():
    assert units.points_to_apply(150, 100) == 100
    assert units.points_to_apply(150, 200) == 150


def test_ids_are_keccak256_of_the_text():
    assert units.id_hash("cafe-sg") == "0x5201e21d519faae81be7783fde2304e898dbb2e67f218026141a55ef2d4bbf19"
    assert len(units.id_bytes("7K2M9Q")) == 32


def test_order_codes():
    code = units.new_order_code()
    assert len(code) == 6
    assert all(c in units.ORDER_CODE_ALPHABET for c in code)
    assert units.normalize_order_code(" 7k2m9q ") == "7K2M9Q"
