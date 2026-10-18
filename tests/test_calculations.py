"""Calculation tests: subtotal, tax, total, empty job, and rounding.

These are the tests the task explicitly requires, plus the PLAN's
golden mixed-tax case. Expected values are hand-computed in comments
and checked against quoteshot.job.totals (Decimal) directly.
"""
from decimal import Decimal

from quoteshot.job import line_total, totals

from conftest import EXAMPLES  # noqa: F401  (also asserts examples dir exists)
import json
from pathlib import Path


def item(name, price, qty="1", taxable=True, unit="each"):
    return {"sku": None, "name": name, "description": "", "unit": unit,
            "unit_price": str(price), "qty": str(qty),
            "taxable": bool(taxable), "source": "adhoc"}


def job(items, tax_rate="0.0825"):
    return {"version": 1, "currency": "USD", "tax_rate": str(tax_rate),
            "customer": {"name": "T", "contact": ""},
            "business": {"name": "B"}, "title": "T",
            "notes": [], "measurements": {}, "photos": [], "items": items}


# ---------------------------------------------------------------------------
# Required: subtotal

def test_subtotal_sums_line_totals():
    # 1 x 75.00 + 2 x 85.00 + 1 x 129.99 = 75 + 170 + 129.99 = 374.99
    t = totals(job([item("call", "75.00"), item("labour", "85.00", "2"),
                    item("faucet", "129.99")]))
    assert t["subtotal"] == Decimal("374.99")
    assert [line["line_total"] for line in t["lines"]] == ["75", "170", "129.99"]


def test_line_total_multiplies_qty_by_price():
    assert line_total(item("labour", "85.00", "2")) == Decimal("170.00")
    assert line_total(item("labour", "85.00", "2.5")) == Decimal("212.50")
    assert line_total(item("bolt", "0.10", "3")) == Decimal("0.30")


# Required: tax (taxable subtotal only)

def test_tax_on_taxable_subtotal():
    # 374.99 x 0.0825 = 30.936675 -> 30.94 (half up)
    t = totals(job([item("call", "75.00"), item("labour", "85.00", "2"),
                    item("faucet", "129.99")]))
    assert t["taxable_subtotal"] == Decimal("374.99")
    assert t["tax"] == Decimal("30.94")


def test_tax_skips_non_taxable_items():
    # PLAN golden: 2.5x40 + 1x129.99 taxable, 3x10 non-taxable.
    # subtotal 259.99, taxable 229.99, tax 229.99x0.0825=18.974175 -> 18.97
    t = totals(job([item("a", "40.00", "2.5"), item("b", "129.99"),
                    item("c", "10.00", "3", taxable=False)]))
    assert t["subtotal"] == Decimal("259.99")
    assert t["taxable_subtotal"] == Decimal("229.99")
    assert t["tax"] == Decimal("18.97")


def test_tax_zero_when_nothing_taxable_and_zero_rate():
    t = totals(job([item("c", "10.00", "3", taxable=False)]))
    assert t["tax"] == Decimal("0.00")
    t2 = totals(job([item("a", "50.00")], tax_rate="0"))
    assert t2["tax"] == Decimal("0.00")
    assert t2["total"] == Decimal("50.00")


# Required: total

def test_total_is_subtotal_plus_tax():
    t = totals(job([item("call", "75.00"), item("labour", "85.00", "2"),
                    item("faucet", "129.99")]))
    assert t["total"] == Decimal("405.93")
    assert t["total"] == t["subtotal"] + t["tax"]
    golden = totals(job([item("a", "40.00", "2.5"), item("b", "129.99"),
                         item("c", "10.00", "3", taxable=False)]))
    assert golden["total"] == Decimal("278.96")


# Required: empty job

def test_empty_job_totals_are_all_zero():
    t = totals(job([]))
    assert t["lines"] == []
    assert t["subtotal"] == Decimal("0.00")
    assert t["taxable_subtotal"] == Decimal("0.00")
    assert t["tax"] == Decimal("0.00")
    assert t["total"] == Decimal("0.00")


# Rounding discipline: Decimal, ROUND_HALF_UP to cents.

def test_tax_rounds_half_up_not_bankers():
    # 50.00 x 0.0625 = 3.125 exactly: half-up -> 3.13 (banker's -> 3.12)
    t = totals(job([item("a", "50.00")], tax_rate="0.0625"))
    assert t["tax"] == Decimal("3.13")
    assert t["total"] == Decimal("53.13")


def test_line_total_rounds_half_up():
    # 3 x 33.335 = 100.005 -> 100.01 half up at line level
    assert line_total(item("x", "33.335", "3")) == Decimal("100.01")


def test_fractional_quantity():
    # 2.5 hr labour at 85.00 = 212.50; tax 212.50x0.0825=17.53125 -> 17.53
    t = totals(job([item("labour", "85.00", "2.5", unit="hour")]))
    assert t["subtotal"] == Decimal("212.50")
    assert t["tax"] == Decimal("17.53")
    assert t["total"] == Decimal("230.03")


def test_no_float_dust():
    # The classic 0.1 + 0.2 trap must not appear anywhere in the totals.
    t = totals(job([item("a", "0.10"), item("b", "0.20")], tax_rate="0"))
    assert t["subtotal"] == Decimal("0.30")
    assert str(t["subtotal"]) == "0.30"


# Cross-check against the shipped sample job's `expected` block.

def test_sample_job_file_matches_totals_function():
    data = json.loads((Path(__file__).resolve().parents[1] / "examples"
                       / "sample-job" / "job.json").read_text())
    t = totals(data)
    exp = data["expected"]
    assert t["subtotal"] == Decimal(exp["subtotal"])
    assert t["tax"] == Decimal(exp["tax"])
    assert t["total"] == Decimal(exp["total"])
