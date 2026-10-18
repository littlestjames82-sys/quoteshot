"""Deepen lane: `quoteshot check` pre-send audit.

Covers the three things check_job verifies and render never did:
photo integrity against the recorded size/sha256, line-item and
tax-rate validity in a (possibly hand-edited) job.json, and price
book drift against the add-time snapshots. Drift must be reported
without ever changing the quote; a missing price book must be
reported, not crash (the polish A5 rule for render/show).
"""
import json
from pathlib import Path

from quoteshot.check import check_job
from quoteshot.job import add_item as api_add_item
from quoteshot.job import add_photos, init_job as api_init_job

from conftest import init_job, make_png, out_text, pb_item, render, run_cli, write_pricebook

ITEMS = [
    pb_item("LABOUR-HR", "85.00", name="Labour", unit="hour"),
    pb_item("FAUCET", "129.99", name="Faucet"),
]


def _book(tmp_path, items=None, sample=False):
    return write_pricebook(tmp_path / "book.json", items or ITEMS, sample=sample)


def _api_job(tmp_path, book=None):
    return api_init_job(tmp_path / "job", title="T", customer="C",
                        tax_rate="0.0825", pricebook=str(book) if book else None)


def _load(job_dir):
    return json.loads((Path(job_dir) / "job.json").read_text())


def _job_with_photo(tmp_path):
    book = _book(tmp_path)
    job = _api_job(tmp_path, book)
    api_add_item(job, sku="LABOUR-HR", qty="2")
    photo = make_png(tmp_path / "site.png", width=4, height=3)
    add_photos(tmp_path / "job", job, [photo])
    return tmp_path / "job", _load(tmp_path / "job")


# --- clean + photo integrity ------------------------------------------------

def test_clean_job_check_is_ok(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    report = check_job(job_dir, job)
    assert report["ok"] is True
    assert report["problems"] == [] and report["drift"] == []
    assert report["photos_checked"] == 1 and report["photos_ok"] == 1
    assert report["items_checked"] == 1 and report["pricebook_items"] == 1
    assert report["pricebook_status"] == "checked"


def test_missing_photo_is_a_problem(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    (job_dir / "photos" / "site.png").unlink()
    report = check_job(job_dir, job)
    assert report["ok"] is False
    assert [p["kind"] for p in report["problems"]] == ["photo_missing"]
    assert "site.png" in report["problems"][0]["detail"]


def test_tampered_photo_fails_hash_check(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    make_png(job_dir / "photos" / "site.png", width=9, height=9)
    report = check_job(job_dir, job)
    assert report["ok"] is False
    assert "photo_hash_mismatch" in [p["kind"] for p in report["problems"]]
    assert report["photos_ok"] == 0


def test_wrong_recorded_size_is_a_problem_even_with_matching_hash(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    job["photos"][0]["size_bytes"] += 10
    report = check_job(job_dir, job)
    assert [p["kind"] for p in report["problems"]] == ["photo_size_mismatch"]


# --- price book drift --------------------------------------------------------

def test_price_change_is_drift_and_names_both_prices(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    _book(tmp_path, [pb_item("LABOUR-HR", "99.00", name="Labour", unit="hour"),
                     ITEMS[1]])
    report = check_job(job_dir, job)
    assert report["ok"] is False
    (drift,) = report["drift"]
    assert drift["sku"] == "LABOUR-HR" and drift["field"] == "unit_price"
    # Snapshot is stored via dec_str ("85"), the book keeps "99.00".
    assert drift["snapshot"] == "85" and drift["current"] == "99.00"
    assert "99.00" in drift["detail"]


def test_formatting_only_price_difference_is_not_drift(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    _book(tmp_path, [pb_item("LABOUR-HR", "85.0", name="Labour", unit="hour"),
                     ITEMS[1]])
    assert check_job(job_dir, job)["drift"] == []


def test_sku_removed_from_book_is_drift(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    _book(tmp_path, [ITEMS[1]])
    report = check_job(job_dir, job)
    assert [(d["sku"], d["field"]) for d in report["drift"]] == [("LABOUR-HR", "sku")]


def test_taxable_flip_and_rename_are_drift(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    _book(tmp_path, [pb_item("LABOUR-HR", "85.00", name="Labour (crew)",
                             unit="hour", taxable=False), ITEMS[1]])
    fields = {d["field"] for d in check_job(job_dir, job)["drift"]}
    assert fields == {"name", "taxable"}


def test_adhoc_items_are_never_drift(tmp_path):
    book = _book(tmp_path)
    job = _api_job(tmp_path, book)
    api_add_item(job, name="One-off fitting", price="12.50", qty="1")
    _book(tmp_path, [pb_item("LABOUR-HR", "1.00", name="Labour", unit="hour")])
    report = check_job(tmp_path / "job", job)
    assert report["drift"] == []
    assert report["adhoc_items"] == 1 and report["pricebook_items"] == 0


def test_deleted_pricebook_is_a_warning_not_a_crash(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    (tmp_path / "book.json").unlink()
    report = check_job(job_dir, job)
    assert report["pricebook_status"] == "unavailable"
    assert any("unavailable" in w for w in report["warnings"])
    # Quote stands on its snapshots: no problem, no invented drift.
    assert report["problems"] == [] and report["drift"] == []


def test_sample_book_is_flagged_as_a_warning(tmp_path):
    book = _book(tmp_path, sample=True)
    job = _api_job(tmp_path, book)
    api_add_item(job, sku="LABOUR-HR", qty="1")
    report = check_job(tmp_path / "job", job)
    assert any("SAMPLE" in w for w in report["warnings"])


# --- hand-edited job validity -------------------------------------------------

def test_nonfinite_and_bad_item_values_are_named_problems(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    job["items"][0]["unit_price"] = "NaN"
    job["items"].append({"sku": None, "name": "Bad qty", "description": "",
                         "unit": "each", "unit_price": "10.00", "qty": "0",
                         "taxable": True, "source": "adhoc"})
    report = check_job(job_dir, job)
    details = " ".join(p["detail"] for p in report["problems"])
    assert report["ok"] is False
    assert "NaN" in details and "Bad qty" in details


def test_out_of_range_tax_rate_is_a_problem(tmp_path):
    job_dir, job = _job_with_photo(tmp_path)
    job["tax_rate"] = "Infinity"
    report = check_job(job_dir, job)
    assert any(p["field"] == "tax_rate" for p in report["problems"])


# --- CLI -----------------------------------------------------------------------

def test_cli_check_clean_job_exits_zero(tmp_path):
    job = init_job(tmp_path, pricebook=_book(tmp_path))
    run_cli(["add-item", job, "--sku", "LABOUR-HR", "--qty", "1"])
    proc = run_cli(["check", job])
    assert proc.returncode == 0, out_text(proc)
    assert "check: OK" in proc.stdout


def test_cli_check_drift_exits_one_and_quote_still_uses_snapshot(tmp_path):
    book = _book(tmp_path)
    job = init_job(tmp_path, pricebook=book)
    run_cli(["add-item", job, "--sku", "LABOUR-HR", "--qty", "1"])
    _book(tmp_path, [pb_item("LABOUR-HR", "99.00", name="Labour", unit="hour"),
                     ITEMS[1]])
    proc = run_cli(["check", job])
    assert proc.returncode == 1, out_text(proc)
    assert "DRIFT" in proc.stdout and "LABOUR-HR" in proc.stdout
    _html, txt = render(job)
    assert "$85.00" in txt and "99" not in txt


def test_cli_check_missing_photo_exits_one(tmp_path):
    job_dir, _job = _job_with_photo(tmp_path)
    (job_dir / "photos" / "site.png").unlink()
    proc = run_cli(["check", job_dir])
    assert proc.returncode == 1, out_text(proc)
    assert "PROBLEM" in proc.stdout and "site.png" in proc.stdout
