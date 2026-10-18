"""Polish round regression tests, pass 2: snapshot completeness + render.

Audit background (POLISH.md):
- A5: item prices were snapshotted at add time, but the SAMPLE state
  was not: the banner re-read the live price book on every render, so
  flipping the book's sample flag rewrote banners on quoted jobs, and
  deleting/corrupting the book made render and show fail (exit 2)
  even though every number on the quote lives in job.json. init now
  records `pricebook_sample` in the job; legacy jobs keep the old
  live-book fallback but fail soft instead of crashing.
- A6: item field snapshot (price/name/unit/taxable/description) was
  verified against edits in the audit; pinned here in full.
- A7: multi-line notes collapsed to run-on text in HTML and lost
  their indentation in the text quote.
- A8: the GPS non-leak rule is extended from the two rendered files
  to every other customer-visible surface: render --out, and the
  `photos` / `show` CLI listings.
"""
import json

from conftest import (add_item, init_job, out_text, pb_item, render,
                      run_cli, totals_from_text, write_pricebook)

ITEMS = [pb_item("LABOUR-HR", "85.00", name="Labour", unit="hour")]


def _book(tmp_path, sample=False):
    return write_pricebook(tmp_path / "book.json", ITEMS, sample=sample)


def _flip_sample(path, value):
    data = json.loads(path.read_text())
    data["sample"] = value
    path.write_text(json.dumps(data))


def _job_with_item(tmp_path, sample=False):
    book_path = _book(tmp_path, sample=sample)
    job = init_job(tmp_path, pricebook=book_path)
    add_item(job, "--sku", "LABOUR-HR", "--qty", "2")
    return job, book_path


# ---------------------------------------------------------------------------
# A5: the SAMPLE state is part of the snapshot

def test_sample_banner_survives_sample_flag_toggled_off(tmp_path):
    job, book_path = _job_with_item(tmp_path, sample=True)
    _flip_sample(book_path, False)  # book edited after the job was quoted
    html, txt = render(job)
    assert "SAMPLE PRICES" in html and "SAMPLE PRICES" in txt


def test_no_banner_when_real_book_later_flagged_sample(tmp_path):
    job, book_path = _job_with_item(tmp_path, sample=False)
    _flip_sample(book_path, True)
    html, txt = render(job)
    assert "SAMPLE PRICES" not in html and "SAMPLE PRICES" not in txt


def test_render_and_show_survive_pricebook_deletion(tmp_path):
    job, book_path = _job_with_item(tmp_path)
    book_path.unlink()
    html, txt = render(job)  # render() asserts rc == 0
    got = totals_from_text(txt)
    from decimal import Decimal
    assert got["subtotal"] == Decimal("170.00")
    assert got["total"] == Decimal("184.03")  # 170 + 170x0.0825 -> 14.03
    proc = run_cli(["show", job])
    assert proc.returncode == 0, out_text(proc)


def test_render_survives_pricebook_corruption(tmp_path):
    job, book_path = _job_with_item(tmp_path)
    book_path.write_text("{not json")
    _html, txt = render(job)
    assert "$170.00" in txt


def test_legacy_job_without_recorded_flag_falls_back_then_fails_soft(tmp_path):
    job, book_path = _job_with_item(tmp_path, sample=True)
    data = json.loads((job / "job.json").read_text())
    del data["pricebook_sample"]  # a job written before the polish
    (job / "job.json").write_text(json.dumps(data))
    html, txt = render(job)  # live book still there: banner as before
    assert "SAMPLE PRICES" in txt
    book_path.unlink()  # ... and with the book gone it renders, banner off
    html, txt = render(job)
    assert "SAMPLE PRICES" not in txt
    assert "$170.00" in txt


# ---------------------------------------------------------------------------
# A6: every item field is snapshotted, not just the price

def test_item_snapshot_covers_name_unit_taxable_description(tmp_path):
    job, book_path = _job_with_item(tmp_path)
    data = json.loads(book_path.read_text())
    data["items"][0].update({"unit_price": "999.00", "name": "CHANGED",
                             "unit": "day", "taxable": False,
                             "description": "CHANGED DESC"})
    book_path.write_text(json.dumps(data))
    _html, txt = render(job)
    got = totals_from_text(txt)
    from decimal import Decimal
    assert got["subtotal"] == Decimal("170.00")   # price snapshot
    assert got["tax"] == Decimal("14.03")         # taxable snapshot (still taxed)
    assert "Labour" in txt and "CHANGED" not in txt
    assert "hour" in txt and "day x" not in txt


# ---------------------------------------------------------------------------
# A7: multi-line notes read the same in both quotes

def test_multiline_note_keeps_breaks_in_html_and_indent_in_text(tmp_path):
    job = init_job(tmp_path)
    proc = run_cli(["note", job, "--text",
                    "Gate latch broken.\nPosts lean about 2 inches."])
    assert proc.returncode == 0, out_text(proc)
    html, txt = render(job)
    assert "Gate latch broken.<br>Posts lean about 2 inches." in html
    assert "  - Gate latch broken.\n    Posts lean about 2 inches." in txt


def test_typed_br_in_a_note_stays_inert_text(tmp_path):
    job = init_job(tmp_path)
    proc = run_cli(["note", job, "--text", "use a<br>tag"])
    assert proc.returncode == 0, out_text(proc)
    html, _txt = render(job)
    assert "use a&lt;br&gt;tag" in html


# ---------------------------------------------------------------------------
# A8: GPS never reaches any customer-visible surface

GPS_PHOTO = {
    "filename": "site.jpg", "stored_as": "photos/site.jpg",
    "original_filename": "site.jpg", "size_bytes": 68, "sha256": "0" * 64,
    "format": "jpeg", "width": 800, "height": 600,
    "captured_at": "2026:10:14 08:30:00", "camera_make": "TestCam",
    "camera_model": "TC-1", "has_gps": True,
    "gps_lat": 36.1234567, "gps_lon": -84.7654321, "has_exif": True}


def test_gps_absent_from_cli_listings_and_render_out(tmp_path):
    job = init_job(tmp_path)
    data = json.loads((job / "job.json").read_text())
    data["photos"].append(GPS_PHOTO)
    (job / "job.json").write_text(json.dumps(data))
    # The record itself keeps the coordinates (record-only by design).
    assert "36.1234567" in (job / "job.json").read_text()

    for args in (["photos", job], ["show", job]):
        proc = run_cli(args)
        assert proc.returncode == 0, out_text(proc)
        assert "36.123" not in out_text(proc) and "84.765" not in out_text(proc)

    out_dir = tmp_path / "elsewhere"
    html, txt = render(job, out_dir=out_dir)
    for text in (html, txt):
        assert "36.123" not in text and "84.765" not in text
        assert "site.jpg" in text
