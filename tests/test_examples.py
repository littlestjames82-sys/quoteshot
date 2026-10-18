"""Examples tests: the shipped sample price book and sample jobs are
valid, labelled SAMPLE, and their stated totals recompute exactly.
The recomputation here is independent (plain Decimal in the test),
so an error in the core cannot hide behind itself."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CENT = Decimal("0.01")


def recompute(job):
    subtotal = Decimal("0")
    taxable = Decimal("0")
    for it in job["items"]:
        line = (Decimal(it["qty"]) * Decimal(it["unit_price"])).quantize(
            CENT, rounding=ROUND_HALF_UP)
        subtotal += line
        if it.get("taxable", True):
            taxable += line
    tax = (taxable * Decimal(job["tax_rate"])).quantize(
        CENT, rounding=ROUND_HALF_UP)
    return subtotal, tax, subtotal + tax


def test_sample_pricebook_shape_and_labelling():
    book = json.loads((EXAMPLES / "pricebook.sample.json").read_text())
    assert book["version"] == 1
    assert book["sample"] is True
    assert book["currency"] == "USD"
    assert book["items"], "sample book must contain items"
    skus = set()
    for it in book["items"]:
        assert it["sku"] not in skus, "duplicate SKU in sample book"
        skus.add(it["sku"])
        for field in ("name", "unit", "unit_price", "taxable"):
            assert field in it, f"{it['sku']} missing {field}"
        assert isinstance(it["unit_price"], str), "prices are decimal text, not floats"
        assert Decimal(it["unit_price"]) >= 0
        assert "SAMPLE" in it["description"], "every sample item must be labelled SAMPLE"


def test_sample_pricebook_passes_core_validation():
    from quoteshot.pricebook import load_pricebook, validate_pricebook
    book = load_pricebook(EXAMPLES / "pricebook.sample.json")
    assert validate_pricebook(book) == []


def test_sample_job_recomputes_to_expected():
    job = json.loads((EXAMPLES / "sample-job" / "job.json").read_text())
    assert job["version"] == 1 and job["tool"] == "quoteshot"
    subtotal, tax, total = recompute(job)
    exp = job["expected"]
    assert subtotal == Decimal(exp["subtotal"]) == Decimal("374.99")
    assert tax == Decimal(exp["tax"]) == Decimal("30.94")
    assert total == Decimal(exp["total"]) == Decimal("405.93")
    # Every item was snapshotted from the sample book at the book price.
    book = {i["sku"]: i for i in
            json.loads((EXAMPLES / "pricebook.sample.json").read_text())["items"]}
    for it in job["items"]:
        assert it["source"] == "pricebook"
        assert it["unit_price"] == book[it["sku"]]["unit_price"]


def test_sample_job_photo_record_matches_the_file():
    import hashlib
    job = json.loads((EXAMPLES / "sample-job" / "job.json").read_text())
    (rec,) = job["photos"]
    photo = EXAMPLES / "sample-job" / rec["stored_as"]
    data = photo.read_bytes()
    assert rec["size_bytes"] == len(data)
    assert rec["sha256"] == hashlib.sha256(data).hexdigest()
    assert rec["format"] == "png"
    assert rec["has_exif"] is False and rec["has_gps"] is False
    assert rec["gps_lat"] is None and rec["gps_lon"] is None


def test_sample_job_renders_with_banner_and_expected_totals(monkeypatch):
    # job.json references the price book as ../pricebook.sample.json,
    # which resolves when run from inside the job folder (as a user would).
    from quoteshot.render import render_html, render_text
    job_dir = EXAMPLES / "sample-job"
    monkeypatch.chdir(job_dir)
    job = json.loads((job_dir / "job.json").read_text())
    txt, html = render_text(job), render_html(job)
    assert "SAMPLE PRICES" in txt and "SAMPLE PRICES" in html
    assert "Subtotal: $374.99" in txt
    assert "Total: $405.93" in txt
    assert "before.png" in txt and "before.png" in html


def test_empty_job_example_is_zero():
    job = json.loads((EXAMPLES / "empty-job" / "job.json").read_text())
    assert job["items"] == []
    subtotal, tax, total = recompute(job)
    assert (subtotal, tax, total) == (Decimal("0"), Decimal("0"), Decimal("0"))
    assert job["expected"] == {"subtotal": "0.00", "tax": "0.00", "total": "0.00"}
