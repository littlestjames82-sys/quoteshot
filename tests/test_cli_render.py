"""End-to-end CLI tests: init -> add-item -> render, totals in the
rendered quote, sample labelling, price snapshotting, empty job."""
import json
from decimal import Decimal

from conftest import (add_item, init_job, out_text, pb_item, render,
                      run_cli, totals_from_text, write_pricebook)

BOOK_ITEMS = [
    pb_item("SERVICE-CALL", "75.00", name="Service call"),
    pb_item("LABOUR-HR", "85.00", name="Labour", unit="hour"),
    pb_item("FAUCET-SUPPLY", "129.99", name="Faucet, supply only"),
]


def book(tmp_path, sample=False):
    return write_pricebook(tmp_path / "book.json", BOOK_ITEMS, sample=sample)


def test_rendered_quote_totals_match_hand_arithmetic(tmp_path):
    job = init_job(tmp_path, pricebook=book(tmp_path))
    add_item(job, "--sku", "SERVICE-CALL", "--qty", "1")
    add_item(job, "--sku", "LABOUR-HR", "--qty", "2")
    add_item(job, "--sku", "FAUCET-SUPPLY", "--qty", "1")
    _html, txt = render(job)
    got = totals_from_text(txt)
    # 75 + 170 + 129.99 = 374.99; tax 8.25% = 30.94; total 405.93
    assert got["subtotal"] == Decimal("374.99"), txt
    assert got["tax"] == Decimal("30.94"), txt
    assert got["total"] == Decimal("405.93"), txt
    for needle in ("Service call", "Labour", "Faucet"):
        assert needle in txt


def test_rendered_html_has_same_totals(tmp_path):
    job = init_job(tmp_path, pricebook=book(tmp_path))
    add_item(job, "--sku", "LABOUR-HR", "--qty", "2")
    html, _txt = render(job)
    assert "$170.00" in html  # subtotal and total-with-tax differ; line total is 170
    assert "$184.03" in html  # 170 + 14.03 tax (170 x 0.0825 = 14.025 -> 14.03)


def test_empty_job_renders_with_zero_totals(tmp_path):
    job = init_job(tmp_path)  # no price book, no items
    _html, txt = render(job)
    got = totals_from_text(txt)
    assert got["subtotal"] == Decimal("0.00"), txt
    assert got["tax"] == Decimal("0.00"), txt
    assert got["total"] == Decimal("0.00"), txt
    assert "no line items" in txt.lower()


def test_sample_book_banner_in_both_outputs_and_not_otherwise(tmp_path):
    job = init_job(tmp_path, pricebook=book(tmp_path, sample=True), name="sjob")
    add_item(job, "--sku", "LABOUR-HR", "--qty", "1")
    html, txt = render(job)
    assert "SAMPLE" in html and "SAMPLE" in txt

    job2 = init_job(tmp_path, pricebook=book(tmp_path, sample=False), name="rjob")
    add_item(job2, "--sku", "LABOUR-HR", "--qty", "1")
    html2, txt2 = render(job2)
    assert "SAMPLE PRICES" not in html2 and "SAMPLE PRICES" not in txt2


def test_price_snapshot_survives_later_pricebook_edit(tmp_path):
    path = book(tmp_path)
    job = init_job(tmp_path, pricebook=path)
    add_item(job, "--sku", "LABOUR-HR", "--qty", "1")
    # Raise the book price after the item was quoted.
    data = json.loads(path.read_text())
    data["items"][1]["unit_price"] = "999.00"
    path.write_text(json.dumps(data))
    _html, txt = render(job)
    got = totals_from_text(txt)
    assert got["subtotal"] == Decimal("85.00"), txt
    assert "999" not in txt


def test_unknown_sku_is_an_error_naming_the_sku(tmp_path):
    job = init_job(tmp_path, pricebook=book(tmp_path))
    proc = run_cli(["add-item", job, "--sku", "NOPE-123", "--qty", "1"])
    assert proc.returncode != 0
    assert "NOPE-123" in out_text(proc)


def test_adhoc_item_requires_an_explicit_price(tmp_path):
    job = init_job(tmp_path)
    proc = run_cli(["add-item", job, "--name", "Mystery work", "--qty", "1"])
    assert proc.returncode != 0, "ad-hoc item without --price must not be invented"
    add_item(job, "--name", "Mystery work", "--price", "12.50", "--qty", "2")
    _html, txt = render(job)
    got = totals_from_text(txt)
    assert got["subtotal"] == Decimal("25.00")


def test_footer_states_no_ai_and_local_price_book(tmp_path):
    job = init_job(tmp_path)
    html, txt = render(job)
    for text in (html, txt):
        assert "No AI" in text
        assert "price book" in text.lower()
        assert "not" in text.lower() and "analysed" in text or "analyzed" in text
