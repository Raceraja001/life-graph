"""Tests for parse_price with currency markers."""

from decimal import Decimal

import pytest

from life_graph.services.page_monitors import parse_price


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("Save 20%! Now ₹1,299", Decimal("1299")),
        ("4.5 out of 5 stars ₹999", Decimal("999")),
        ("Only 3 left! $49.99", Decimal("49.99")),
        ("Rs. 2,499 (was Rs 3,000)", Decimal("2499")),
        ("MRP ₹1,999 Deal ₹1,499", Decimal("1999")),
        ("62999.00", Decimal("62999.00")),
        ("4 stars, 1,299", Decimal("1299")),
        ("₹ 1,24,999", Decimal("124999")),
        ("20% off", None),
        ("Rated 4.2/5", None),
        ("no price", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_price(text, price):
    assert parse_price(text) == price
