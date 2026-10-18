"""Hardening regression tests (2026-10-18 improve pass, lane: harden).

Each test pins a bug that was reproduced against the pre-fix code:

- H1 parse_decimal returned a Decimal input untouched, so
  Decimal("NaN") / ("Infinity") / ("sNaN") bypassed the one finite
  gate entirely, and an absurd exponent (1e10000) parsed fine and
  then made quantize/format build a giant digit string downstream.
- H2 totals computed `subtotal + tax` under the ambient 28-digit
  context, silently dropping the cents on large totals, and totals /
  line_total accepted hand-edited jobs with negative prices,
  negative/zero quantities, a tax rate outside 0..1, a non-bool
  taxable flag, or a non-string currency (the last crashed with an
  AttributeError traceback).
- H3 _pct multiplied/normalized the tax rate under the ambient
  context, so a long rate was rounded in the quote's tax label and
  disagreed with the tax actually charged.
- H4 validate_pricebook accepted a non-string currency, a truthy
  string sample flag ("false" stamped a SAMPLE banner), a boolean
  version, and non-string/blank item names and units.
- H5 normalise_item (and empty_book) let the CLI write a price book
  with a blank sku/name/unit or blank currency that its own loader
  then rejected as invalid.
- H6 add_photos copied good photos into the job and only then failed
  on a later missing/non-image file, leaving orphan files in photos/
  that job.json knew nothing about.
- H7 load_job did no structural check, so a hand-edited job.json with
  the wrong field shapes crashed render/show with a traceback.
- H8 EXIF GPS: a zero-denominator rational silently became 0.0 and
  out-of-range DMS/coordinate values were folded into a fabricated
  coordinate instead of failing soft to no GPS.
"""
import json
import struct
from decimal import Decimal

import pytest

from quoteshot.job import add_photos, init_job, line_total, load_job, totals
from quoteshot.money import QuoteShotError, parse_decimal
from quoteshot.photos import describe_photo
from quoteshot.pricebook import (empty_book, load_pricebook, normalise_item,
                                 validate_pricebook)
from quoteshot.render import _pct

from conftest import make_png, out_text, run_cli


def _item(price="10.00", qty="1", taxable=True):
    return {"sku": None, "name": "x", "description": "", "unit": "each",
            "unit_price": price, "qty": qty, "taxable": taxable,
            "source": "adhoc"}


def _job(items, rate="0.0825", currency="USD"):
    return {"version": 1, "currency": currency, "tax_rate": rate,
            "items": items}


# ---------------------------------------------------------------------------
# H1: the finite gate covers Decimal inputs and absurd magnitudes too

@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_parse_decimal_rejects_decimal_objects_that_are_not_finite(bad):
    with pytest.raises(QuoteShotError) as exc:
        parse_decimal(Decimal(bad), "unit_price")
    assert "unit_price" in str(exc.value)


@pytest.mark.parametrize("bad", ["1e10000", "1e-10000", "9" * 1001])
def test_parse_decimal_rejects_implausible_magnitudes(bad):
    with pytest.raises(QuoteShotError):
        parse_decimal(bad, "unit_price")
    with pytest.raises(QuoteShotError):
        parse_decimal(Decimal(bad), "unit_price")


def test_parse_decimal_still_accepts_large_legitimate_amounts():
    # The polish-era 1e30 case must keep working under the bound.
    assert parse_decimal("1e30", "unit_price") == Decimal("1e30")
    assert parse_decimal(Decimal("85.00"), "unit_price") == Decimal("85.00")


# ---------------------------------------------------------------------------
# H2: totals arithmetic and hand-edited job values

def test_large_total_keeps_its_cents():
    # subtotal 1000000000000000000000000000000.01, tax at 8.25% is
    # 82500000000000000000000000000.00; the pre-fix total lost the .01.
    t = totals(_job([_item(price="1000000000000000000000000000000.01")]))
    assert t["total"] == Decimal("1082500000000000000000000000000.01")


@pytest.mark.parametrize("item", [
    _item(price="-5.00"),
    _item(qty="-2"),
    _item(qty="0"),
])
def test_totals_reject_out_of_range_line_values(item):
    with pytest.raises(QuoteShotError):
        totals(_job([item]))
    with pytest.raises(QuoteShotError):
        line_total(item)


@pytest.mark.parametrize("rate", ["5", "-0.5", "1.0001"])
def test_totals_reject_tax_rate_outside_zero_to_one(rate):
    with pytest.raises(QuoteShotError) as exc:
        totals(_job([_item()], rate=rate))
    assert "tax_rate" in str(exc.value)


@pytest.mark.parametrize("rate", ["0", "1"])
def test_totals_accept_tax_rate_bounds(rate):
    t = totals(_job([_item(price="100.00")], rate=rate))
    assert t["tax"] == Decimal("100.00") * Decimal(rate)


def test_totals_reject_non_bool_taxable_and_non_string_currency():
    with pytest.raises(QuoteShotError):
        totals(_job([_item(taxable="false")]))
    for bad_currency in (123, ["USD"]):
        with pytest.raises(QuoteShotError) as exc:
            totals(_job([_item()], currency=bad_currency))
        assert "currency" in str(exc.value)
    with pytest.raises(QuoteShotError):
        totals({"currency": "USD", "tax_rate": "0", "items": {"a": 1}})


# ---------------------------------------------------------------------------
# H3: the displayed tax rate is not silently rounded

def test_pct_does_not_round_long_rates():
    rate = parse_decimal("0.1234567890123456789012345678901234", "tax_rate")
    assert _pct(rate) == "12.34567890123456789012345678901234"
    assert _pct(Decimal("0.0825")) == "8.25"
    assert _pct(Decimal("0")) == "0"
    assert _pct(Decimal("1")) == "100"


# ---------------------------------------------------------------------------
# H4/H5: price book validation and writes that cannot corrupt the book

def _book(**overrides):
    book = {"version": 1, "currency": "USD", "sample": False, "items": []}
    book.update(overrides)
    return book


@pytest.mark.parametrize("book", [
    _book(currency=123),
    _book(currency=""),
    _book(sample="false"),
    _book(version=True),
    _book(items=[{"sku": "X", "name": 123, "unit": "each",
                  "unit_price": "1", "taxable": True}]),
    _book(items=[{"sku": "X", "name": "X", "unit": "  ",
                  "unit_price": "1", "taxable": True}]),
    _book(items=[{"sku": "  ", "name": "X", "unit": "each",
                  "unit_price": "1", "taxable": True}]),
    _book(items=[{"sku": "X", "name": "X", "unit": "each",
                  "unit_price": "1", "taxable": True, "description": 5}]),
])
def test_validate_pricebook_rejects_malformed_metadata(book):
    assert validate_pricebook(book) != []
    assert validate_pricebook(_book()) == []


@pytest.mark.parametrize("field", ["sku", "name", "unit"])
def test_normalise_item_rejects_blank_fields(field):
    kwargs = {"sku": "X", "name": "X", "unit": "each"}
    kwargs[field] = "   "
    with pytest.raises(QuoteShotError):
        normalise_item(unit_price="10.00", **kwargs)


def test_empty_book_rejects_blank_currency():
    with pytest.raises(QuoteShotError):
        empty_book(currency="")
    with pytest.raises(QuoteShotError):
        empty_book(currency=123)


def test_cli_pricebook_add_blank_sku_does_not_corrupt_book(tmp_path):
    path = tmp_path / "book.json"
    proc = run_cli(["pricebook", "init", path])
    assert proc.returncode == 0, out_text(proc)
    proc = run_cli(["pricebook", "add", path, "--sku", "", "--name", "X",
                    "--unit", "each", "--price", "10.00"])
    assert proc.returncode == 1, out_text(proc)
    assert "Traceback" not in out_text(proc)
    assert load_pricebook(path)["items"] == []  # book still loads, unchanged


# ---------------------------------------------------------------------------
# H6: add-photo batches are all-or-nothing

def test_add_photos_batch_failure_leaves_no_orphan_files(tmp_path):
    job_dir = tmp_path / "job"
    init_job(job_dir, title="t", customer="c")
    good = make_png(tmp_path / "good.png")
    bad = tmp_path / "notes.txt"
    bad.write_text("not a photo")
    job = load_job(job_dir)
    with pytest.raises(QuoteShotError):
        add_photos(job_dir, job, [good, bad])
    assert list((job_dir / "photos").iterdir()) == []
    assert load_job(job_dir)["photos"] == []
    with pytest.raises(QuoteShotError):
        add_photos(job_dir, job, [good, tmp_path / "missing.png"])
    assert list((job_dir / "photos").iterdir()) == []


def test_add_photos_batch_success_still_works(tmp_path):
    job_dir = tmp_path / "job"
    init_job(job_dir, title="t", customer="c")
    a = make_png(tmp_path / "a.png")
    b = make_png(tmp_path / "b.png")
    add_photos(job_dir, load_job(job_dir), [a, b])
    assert len(load_job(job_dir)["photos"]) == 2
    assert sorted(p.name for p in (job_dir / "photos").iterdir()) == ["a.png", "b.png"]


# ---------------------------------------------------------------------------
# H7: malformed job.json fails by field name, not with a traceback

@pytest.mark.parametrize("patch", [
    {"items": {"not": "a list"}},
    {"photos": ["not-a-dict"]},
    {"customer": "a string, not an object"},
    {"measurements": ["not", "a", "dict"]},
])
def test_load_job_rejects_wrong_field_shapes(tmp_path, patch):
    job_dir = tmp_path / "job"
    init_job(job_dir, title="t", customer="c")
    jf = job_dir / "job.json"
    data = json.loads(jf.read_text())
    data.update(patch)
    jf.write_text(json.dumps(data))
    with pytest.raises(QuoteShotError):
        load_job(job_dir)
    proc = run_cli(["show", job_dir])
    assert proc.returncode == 2, out_text(proc)
    assert "Traceback" not in out_text(proc)


# ---------------------------------------------------------------------------
# H8: EXIF GPS fails soft instead of fabricating coordinates

def _ifd(entries):
    out = struct.pack("<H", len(entries))
    for tag, typ, cnt, val in entries:
        out += struct.pack("<HHI", tag, typ, cnt) + val
    return out + struct.pack("<I", 0)


def _rats(vals):
    return b"".join(struct.pack("<II", n, d) for n, d in vals)


def _gps_jpeg(lat_rats, lon_rats) -> bytes:
    lat_off, lon_off = 174, 198
    ifd0 = _ifd([
        (0x010F, 2, 8, struct.pack("<I", 146)),
        (0x0110, 2, 4, b"TC-1"),
        (0x0132, 2, 20, struct.pack("<I", 154)),
        (0x8769, 4, 1, struct.pack("<I", 74)),
        (0x8825, 4, 1, struct.pack("<I", 92)),
    ])
    exif_ifd = _ifd([(0x9003, 2, 20, struct.pack("<I", 154))])
    gps_ifd = _ifd([
        (1, 2, 2, b"N\x00\x00\x00"),
        (2, 5, 3, struct.pack("<I", lat_off)),
        (3, 2, 2, b"W\x00\x00\x00"),
        (4, 5, 3, struct.pack("<I", lon_off)),
    ])
    tiff = b"II*\x00" + struct.pack("<I", 8) + ifd0 + exif_ifd + gps_ifd
    assert len(tiff) == 146
    tiff += (b"TestCam\x00" + b"2026:10:14 08:30:00\x00"
             + _rats(lat_rats) + _rats(lon_rats))
    app1 = b"\xff\xe1" + struct.pack(">H", len(tiff) + 8) + b"Exif\x00\x00" + tiff
    sof = (b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"
           + struct.pack(">HH", 600, 800)
           + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
    return b"\xff\xd8" + app1 + sof + b"\xff\xd9"


def _describe(tmp_path, data):
    p = tmp_path / "probe.jpg"
    p.write_bytes(data)
    return describe_photo(p)


def test_gps_zero_denominator_rational_is_dropped_not_zeroed(tmp_path):
    rec = _describe(tmp_path, _gps_jpeg([(36, 1), (7, 1), (59, 0)],
                                        [(84, 1), (45, 1), (30, 1)]))
    assert rec["has_gps"] is False
    assert rec["gps_lat"] is None and rec["gps_lon"] is None
    assert rec["width"] == 800  # the photo itself is still recorded


@pytest.mark.parametrize("lat_rats,lon_rats", [
    ([(999, 1), (0, 1), (0, 1)], [(84, 1), (0, 1), (0, 1)]),    # lat > 90
    ([(36, 1), (999, 1), (0, 1)], [(84, 1), (0, 1), (0, 1)]),   # minutes 999
    ([(36, 1), (0, 1), (0, 1)], [(999, 1), (0, 1), (0, 1)]),    # lon > 180
])
def test_gps_out_of_range_coordinates_are_dropped(tmp_path, lat_rats, lon_rats):
    rec = _describe(tmp_path, _gps_jpeg(lat_rats, lon_rats))
    assert rec["has_gps"] is False
    assert rec["gps_lat"] is None and rec["gps_lon"] is None


def test_gps_valid_coordinates_still_recorded(tmp_path):
    rec = _describe(tmp_path, _gps_jpeg([(36, 1), (7, 1), (30, 1)],
                                        [(84, 1), (45, 1), (554, 10)]))
    assert rec["has_gps"] is True
    assert rec["gps_lat"] == pytest.approx(36.125)
    assert rec["gps_lon"] == pytest.approx(-84.7653889, abs=1e-6)
