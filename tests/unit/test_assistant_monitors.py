"""Phase D: page monitors — selectors, prices, transitions, failures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from life_graph.models.assistant import PageMonitor
from life_graph.services import page_monitors as pm
from life_graph.services.safe_fetch import FetchResult

SHOP = """<html><head><title>Pixel 9</title>
<meta property="product:price:amount" content="62999.00">
<script>var price = "1";</script></head>
<body><h1 id="name">Pixel 9</h1>
<div class="box"><span class="price big" itemprop="price">₹64,999.00</span><b>MRP ₹79,999</b></div>
<p class="stock">Out of stock</p></body></html>"""


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("#name", "Pixel 9"),
        ("span.price", "₹64,999.00"),
        ("[itemprop=price]", "₹64,999.00"),
        ("span.price.big[itemprop=price]", "₹64,999.00"),
        ("div.box", "₹64,999.00 MRP ₹79,999"),
        ("meta[property=product:price:amount]", "62999.00"),
        ("p.stock", "Out of stock"),
        ("regex:MRP\\s*(₹[\\d,]+)", "₹79,999"),
        ("span.missing", None),
    ],
)
def test_select_text(selector, expected):
    assert pm.select_text(SHOP, selector) == expected


def test_whole_page_without_a_selector_skips_scripts():
    text = pm.select_text(SHOP, None)
    assert "Pixel 9" in text and "var price" not in text


@pytest.mark.parametrize("bad", ["div > span", "span price", "", "a::before"])
def test_unsupported_selectors_are_refused(bad):
    with pytest.raises(pm.SelectorError):
        pm.parse_selector(bad)


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("₹1,24,999.00", Decimal("124999.00")),
        ("Rs. 499", Decimal("499")),
        ("$19.99 today", Decimal("19.99")),
        ("no price", None),
    ],
)
def test_parse_price(text, price):
    assert pm.parse_price(text) == price


def _m(**kw) -> PageMonitor:
    base = dict(
        tenant_id="t",
        name="Pixel 9",
        url="https://shop.example/p9",
        mode="change",
        interval_minutes=180,
        paused=False,
        consecutive_failures=0,
    )
    return PageMonitor(**{**base, **kw})


def test_price_below_alerts_on_the_drop_only():
    m = _m(mode="price_below", threshold=Decimal("60000"))
    event, upd = pm.evaluate(m, "₹64,999")
    assert event is None and upd["last_value"] == Decimal("64999")
    m.last_value = upd["last_value"]
    event, upd = pm.evaluate(m, "₹58,999")
    assert event and "58,999.00" in event["title"]
    m.last_value = upd["last_value"]
    event, _ = pm.evaluate(m, "₹57,999")
    assert event is None  # still below: no repeat


def test_contains_alerts_when_text_appears():
    m = _m(mode="contains", pattern="In stock")
    event, upd = pm.evaluate(m, "Out of stock")
    assert event is None and upd["last_value"] == 0
    m.last_value = upd["last_value"]
    event, upd = pm.evaluate(m, "In stock now")
    assert event and "appeared" in event["title"]


def test_change_needs_a_baseline_first():
    m = _m()
    event, upd = pm.evaluate(m, "v1")
    assert event is None
    m.last_hash, m.last_excerpt = upd["last_hash"], upd["last_excerpt"]
    assert pm.evaluate(m, "v1")[0] is None
    event, _ = pm.evaluate(m, "v2")
    assert event["details"]["before"] == "v1" and event["details"]["after"] == "v2"


def test_due_respects_interval_and_pause():
    now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    assert pm.due(_m(), now)
    assert not pm.due(_m(last_checked_at=now - timedelta(minutes=60)), now)
    assert pm.due(_m(last_checked_at=now - timedelta(minutes=181)), now)
    assert not pm.due(_m(paused=True), now)


@pytest.mark.asyncio
async def test_failures_pause_the_monitor_once():
    m = _m()
    now = datetime(2026, 10, 14, 12, tzinfo=UTC)

    async def broken(url):
        raise ConnectionError("down")

    events = [await pm.check(m, now, fetch=broken) for _ in range(pm.MAX_FAILURES)]
    assert events[:-1] == [None] * (pm.MAX_FAILURES - 1)
    assert "paused" in events[-1]["title"] and m.paused


@pytest.mark.asyncio
async def test_check_updates_the_monitor():
    m = _m(mode="price_below", threshold=Decimal("70000"), selector="span.price")

    async def page(url):
        return FetchResult(
            url=url, status_code=200, content_type="text/html", text=SHOP, truncated=False
        )

    event = await pm.check(m, datetime(2026, 10, 14, tzinfo=UTC), fetch=page)
    assert event and m.last_value == Decimal("64999.00") and m.last_error is None


def test_validate():
    pm.validate("change", None, None, None)
    with pytest.raises(ValueError):
        pm.validate("price_below", None, None, None)
    with pytest.raises(ValueError):
        pm.validate("contains", None, "", None)
    with pytest.raises(ValueError):
        pm.validate("nope", None, None, None)
    with pytest.raises(pm.SelectorError):
        pm.validate("change", None, None, "regex:(")
