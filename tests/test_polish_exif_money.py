"""Polish round regression tests, pass 1: EXIF fail-soft + money gates.

Audit background (POLISH.md):
- A1: Decimal parses "NaN"/"Infinity" happily; NaN used to poison
  totals silently ($NaN on a quote), Infinity passed pricebook
  validation and then crashed totals, and a NaN price crashed
  `pricebook validate` with a traceback. parse_decimal is the single
  gate and now rejects non-finite values by field name.
- A2: the ambient 28-digit Decimal context made money() raise
  InvalidOperation on large finite amounts (1e30) and made long
  multiplications / dec_str silently round.
- A3/A4: the EXIF/header parsers survived ~1,034 audit fuzz cases
  (every truncation length, seeded mutations, magic-prefixed garbage,
  targeted corrupt TIFFs) with zero crashes; the one inconsistency was
  PNG/GIF zero dimensions recorded as 0 instead of null. These tests
  pin the fail-soft behaviour so it cannot regress quietly.
"""
import random
import struct
from decimal import Decimal

import pytest

from quoteshot.job import line_total, totals
from quoteshot.money import QuoteShotError, dec_str, fmt_money, money, parse_decimal
from quoteshot.photos import describe_photo
from quoteshot.pricebook import validate_pricebook

from conftest import out_text, run_cli


# ---------------------------------------------------------------------------
# EXIF fixture: a hand-built little-endian TIFF JPEG with GPS, in the
# same shape as the audit probe. Layout offsets are fixed by hand.

def _ifd(entries):
    out = struct.pack("<H", len(entries))
    for tag, typ, cnt, val in entries:
        out += struct.pack("<HHI", tag, typ, cnt) + val
    return out + struct.pack("<I", 0)


def _rats(vals):
    return b"".join(struct.pack("<II", n, d) for n, d in vals)


def build_exif_jpeg() -> bytes:
    make_off, dt_off, lat_off, lon_off = 146, 154, 174, 198
    ifd0 = _ifd([
        (0x010F, 2, 8, struct.pack("<I", make_off)),      # Make
        (0x0110, 2, 4, b"TC-1"),                          # Model, inline
        (0x0132, 2, 20, struct.pack("<I", dt_off)),        # DateTime
        (0x8769, 4, 1, struct.pack("<I", 74)),             # Exif IFD ptr
        (0x8825, 4, 1, struct.pack("<I", 92)),             # GPS IFD ptr
    ])
    exif_ifd = _ifd([(0x9003, 2, 20, struct.pack("<I", dt_off))])
    gps_ifd = _ifd([
        (1, 2, 2, b"N\x00\x00\x00"),
        (2, 5, 3, struct.pack("<I", lat_off)),
        (3, 2, 2, b"W\x00\x00\x00"),
        (4, 5, 3, struct.pack("<I", lon_off)),
    ])
    tiff = b"II*\x00" + struct.pack("<I", 8) + ifd0 + exif_ifd + gps_ifd
    assert len(tiff) == 146
    tiff += (b"TestCam\x00" + b"2026:10:14 08:30:00\x00"
             + _rats([(36, 1), (7, 1), (30, 1)])
             + _rats([(84, 1), (45, 1), (554, 10)]))
    app1 = b"\xff\xe1" + struct.pack(">H", len(tiff) + 8) + b"Exif\x00\x00" + tiff
    sof = (b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"
           + struct.pack(">HH", 600, 800)
           + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
    return b"\xff\xd8" + app1 + sof + b"\xff\xd9"


def describe_bytes(tmp_path, data, name="probe.jpg"):
    p = tmp_path / name
    p.write_bytes(data)
    return describe_photo(p)


def assert_fails_soft(tmp_path, data, name="probe.jpg"):
    """Either a record with null-or-sane fields, or a QuoteShotError
    rejection by name. Any other exception type is a parser crash."""
    try:
        rec = describe_bytes(tmp_path, data, name)
    except QuoteShotError:
        return
    for field in ("width", "height"):
        assert rec[field] is None or (isinstance(rec[field], int) and rec[field] > 0)
    for field in ("captured_at", "camera_make", "camera_model"):
        assert rec[field] is None or isinstance(rec[field], str)
    assert rec["has_gps"] == (rec["gps_lat"] is not None and rec["gps_lon"] is not None)


def test_valid_exif_jpeg_still_parses_every_field(tmp_path):
    rec = describe_bytes(tmp_path, build_exif_jpeg())
    assert (rec["width"], rec["height"]) == (800, 600)
    assert rec["camera_make"] == "TestCam" and rec["camera_model"] == "TC-1"
    assert rec["captured_at"] == "2026:10:14 08:30:00"
    assert rec["has_exif"] is True and rec["has_gps"] is True


def test_exif_truncation_at_every_length_fails_soft(tmp_path):
    valid = build_exif_jpeg()
    for n in range(len(valid) + 1):
        assert_fails_soft(tmp_path, valid[:n], "trunc.jpg")


def test_exif_seeded_mutations_fail_soft(tmp_path):
    valid = build_exif_jpeg()
    rng = random.Random(20261014)
    for _ in range(250):
        data = bytearray(valid)
        for _ in range(rng.randint(1, 12)):
            data[rng.randrange(len(data))] = rng.randrange(256)
        assert_fails_soft(tmp_path, bytes(data), "mut.jpg")


def test_magic_prefixed_garbage_fails_soft(tmp_path):
    rng = random.Random(7)
    for magic in (b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"GIF89a", b"GIF87a"):
        for _ in range(40):
            junk = bytes(rng.randrange(256) for _ in range(rng.randint(0, 80)))
            assert_fails_soft(tmp_path, magic + junk, "garbage.bin")


def test_targeted_corrupt_tiffs_fail_soft(tmp_path):
    head = b"\xff\xd8\xff\xe1\x00\x12Exif\x00\x00"
    cases = [
        head + b"ZZ*\x00\x08\x00\x00\x00" + b"\x00" * 8 + b"\xff\xd9",   # bad byte order
        head + b"II\x99\x99\x08\x00\x00\x00" + b"\x00" * 8 + b"\xff\xd9",  # bad magic
        head + b"II*\x00\x08\x00\x00\x00\xff\xff" + b"\x00" * 16 + b"\xff\xd9",  # huge IFD count
        head + b"II*\x00\xff\xff\xff\x7f" + b"\x00" * 8 + b"\xff\xd9",   # IFD offset past EOF
        b"\xff\xd8",                       # SOI only
        b"\x89PNG\r\n\x1a\n",              # PNG signature only
        b"GIF89a",                         # GIF signature only
    ]
    for data in cases:
        assert_fails_soft(tmp_path, data)


def test_empty_and_unrecognised_files_are_rejected_by_name(tmp_path):
    for data, name in [(b"", "empty.jpg"), (b"plain text", "notes.txt")]:
        with pytest.raises(QuoteShotError) as exc:
            describe_bytes(tmp_path, data, name)
        assert name in str(exc.value)


def test_zero_dimensions_fail_soft_to_null(tmp_path):
    png = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
           + struct.pack(">II", 0, 0) + b"\x00" * 9)
    rec = describe_bytes(tmp_path, png, "zero.png")
    assert rec["format"] == "png" and rec["width"] is None and rec["height"] is None
    gif = b"GIF89a" + struct.pack("<HH", 0, 5)
    rec = describe_bytes(tmp_path, gif, "zero.gif")
    assert rec["format"] == "gif" and rec["width"] is None and rec["height"] == 5


# ---------------------------------------------------------------------------
# Money gates (A1/A2)

NON_FINITE = ["NaN", "-NaN", "sNaN", "Infinity", "-Infinity", "inf", "-inf"]


@pytest.mark.parametrize("bad", NON_FINITE)
def test_parse_decimal_rejects_non_finite_naming_the_field(bad):
    with pytest.raises(QuoteShotError) as exc:
        parse_decimal(bad, "unit_price")
    assert "unit_price" in str(exc.value)


def _job(price="10.00", qty="1", rate="0.0825"):
    return {"version": 1, "currency": "USD", "tax_rate": rate,
            "items": [{"sku": None, "name": "x", "description": "", "unit": "each",
                       "unit_price": price, "qty": qty, "taxable": True,
                       "source": "adhoc"}]}


@pytest.mark.parametrize("field", ["price", "qty", "rate"])
def test_totals_reject_non_finite_instead_of_poisoning_or_crashing(field):
    kwargs = {field: "NaN"}
    with pytest.raises(QuoteShotError):
        totals(_job(**kwargs))
    kwargs = {field: "Infinity"}
    with pytest.raises(QuoteShotError):
        totals(_job(**kwargs))


def test_pricebook_validation_reports_non_finite_prices(tmp_path):
    for bad in ("NaN", "Infinity"):
        book = {"version": 1, "currency": "USD", "sample": False,
                "items": [{"sku": "X", "name": "X", "unit": "each",
                           "unit_price": bad, "taxable": True}]}
        errors = validate_pricebook(book)
        assert any("X" in e and "unit_price" in e for e in errors), errors
        # And through the CLI: a clean exit 1, not a traceback.
        import json as _json
        path = tmp_path / f"bad_{bad}.json"
        path.write_text(_json.dumps(book))
        proc = run_cli(["pricebook", "validate", path])
        assert proc.returncode == 1, out_text(proc)
        assert "Traceback" not in out_text(proc)


def test_large_finite_amounts_compute_exactly():
    # 1e30 used to raise InvalidOperation out of money().
    t = totals(_job(price="1000000000000000000000000000000.00", rate="0"))
    assert t["subtotal"] == Decimal("1000000000000000000000000000000.00")
    assert money(Decimal("1e30")) == Decimal("1000000000000000000000000000000.00")
    assert fmt_money(Decimal("1e30")) == "$1,000,000,000,000,000,000,000,000,000,000.00"


def test_long_multiplication_is_not_silently_rounded():
    # 12345678901234567890.12 x 3 = 37037036703703703670.36 exactly.
    item = {"qty": "3", "unit_price": "12345678901234567890.12"}
    assert line_total(item) == Decimal("37037036703703703670.36")
    # A 25-significant-digit price x a 6-digit quantity has an exact
    # product longer than the ambient 28-digit context: before the
    # polish the product was rounded at 28 digits before the cents
    # rounding ever ran, so the line total could land a cent (or more)
    # away from the true value. Expected value computed exactly with
    # fractions, rounded half-up to cents by integer arithmetic.
    from fractions import Fraction
    product = Fraction("9.99999") * Fraction("12345678901234567890.12345")
    cents = product * 100
    rounded_cents = (2 * cents.numerator + cents.denominator) // (2 * cents.denominator)
    expected = Decimal(f"{rounded_cents // 100}.{rounded_cents % 100:02d}")
    item = {"qty": "9.99999", "unit_price": "12345678901234567890.12345"}
    assert line_total(item) == expected


def test_dec_str_round_trips_long_prices_without_rounding():
    for text in ("12345678901234567890.123456789", "1000000000000000000000000000000.5",
                 "85.00", "0.0825", "2.5"):
        value = parse_decimal(text, "unit_price")
        assert parse_decimal(dec_str(value), "unit_price") == value
    assert dec_str(Decimal("85.00")) == "85"
    assert dec_str(Decimal("0.0825")) == "0.0825"
    assert dec_str(Decimal("-0.00")) == "0"
