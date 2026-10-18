"""Job folder model: job.json + photos/ + rendered quote output.

A job is a directory. job.json is the single record: customer, business,
tax rate, notes, measurements, photo records, and line items with prices
snapshotted at add time (later price-book edits never change a job).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from .money import QuoteShotError, _wide_prec, dec_str, money, parse_decimal
from .photos import describe_photo
from .pricebook import find_item, load_pricebook

JOB_FILE = "job.json"
PHOTOS_DIR = "photos"


def now_iso() -> str:
    """Current local time as an ISO-8601 string, for record timestamps."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def init_job(job_dir, *, title, customer, contact="", business="",
             tax_rate="0", currency="USD", pricebook=None) -> dict:
    """Create a job folder and its job.json; return the new job dict.

    ``tax_rate`` is a decimal fraction (``"0.0825"`` = 8.25%). If a
    ``pricebook`` is given it is validated first, its currency wins
    over ``currency``, and whether it was a sample book is recorded
    on the job. Refuses to overwrite an existing job.json.
    """
    d = Path(job_dir)
    jf = d / JOB_FILE
    if jf.exists():
        raise QuoteShotError(
            f"{jf} already exists; refusing to overwrite (delete the folder "
            "yourself if this job was created by mistake)")
    rate = parse_decimal(tax_rate, "tax_rate")
    if rate < 0 or rate > 1:
        raise QuoteShotError(f"tax_rate: must be between 0 and 1, got {rate}")
    if not isinstance(currency, str) or not currency.strip():
        raise QuoteShotError(f"currency: must be a non-empty string, got {currency!r}")
    pb_ref = None
    pb_sample = False
    if pricebook:
        book = load_pricebook(pricebook)  # validates before we commit to it
        pb_ref = str(Path(pricebook))
        pb_sample = bool(book.get("sample"))
        currency = (book.get("currency") or currency).upper()
        if pb_sample:
            print("note: this price book is a SAMPLE book; quotes from it "
                  "will carry a SAMPLE PRICES banner.")
    d.mkdir(parents=True, exist_ok=True)
    (d / PHOTOS_DIR).mkdir(exist_ok=True)
    job = {
        "version": 1,
        "tool": "quoteshot",
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "customer": {"name": customer, "contact": contact or ""},
        "business": {"name": business or ""},
        "created_at": now_iso(),
        "currency": currency.upper(),
        "tax_rate": dec_str(rate),
        "pricebook": pb_ref,
        "pricebook_sample": pb_sample,
        "notes": [],
        "measurements": {},
        "photos": [],
        "items": [],
    }
    save_job(d, job)
    return job


def load_job(job_dir) -> dict:
    """Load and check a job folder's job.json; raise if missing/bad."""
    d = Path(job_dir)
    jf = d / JOB_FILE
    if not jf.is_file():
        raise QuoteShotError(
            f"no job at {d} (missing {JOB_FILE}); create one with: "
            f"quoteshot init {d} --title ... --customer ...", fatal=True)
    try:
        job = json.loads(jf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise QuoteShotError(f"{jf}: unreadable JSON: {exc}", fatal=True) from None
    if not isinstance(job, dict) or job.get("version") != 1:
        raise QuoteShotError(f"{jf}: unsupported job format (version must be 1)",
                             fatal=True)
    # Structural check: a hand-edited job.json whose fields have the
    # wrong shape used to crash render/show with an AttributeError
    # traceback (e.g. "customer" as a string, "items" as an object).
    # Name the offending field instead, as a fatal (exit 2) error.
    for field in ("notes", "photos", "items"):
        value = job.get(field)
        if value is not None and (not isinstance(value, list)
                                  or any(not isinstance(v, dict) for v in value)):
            raise QuoteShotError(
                f"{jf}: {field}: must be a list of objects", fatal=True)
    for field in ("measurements", "customer", "business"):
        value = job.get(field)
        if value is not None and not isinstance(value, dict):
            raise QuoteShotError(f"{jf}: {field}: must be an object", fatal=True)
    return job


def save_job(job_dir, job: dict) -> Path:
    """Write ``job`` as job.json inside ``job_dir``; return its path."""
    d = Path(job_dir)
    d.mkdir(parents=True, exist_ok=True)
    jf = d / JOB_FILE
    jf.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return jf


def job_pricebook(job: dict) -> dict | None:
    """Load the price book a job refers to, or None if it has none."""
    ref = job.get("pricebook")
    if not ref:
        return None
    return load_pricebook(ref)


def pricebook_is_sample(job: dict) -> bool:
    """Was the job's price book a sample book *when the job was made*?

    The flag is snapshotted into job.json at init, like the item prices
    themselves (polish A5): before the polish this re-read the live
    price book on every render/show, so toggling the book's sample
    flag rewrote the banner on already-quoted jobs, and deleting or
    corrupting the book made render and show fail outright even though
    every number on the quote comes from the job's own snapshots.
    Jobs written before the polish have no recorded flag; for those,
    fall back to the live book as before, but fail soft to False when
    it is unreadable rather than breaking the quote.
    """
    recorded = job.get("pricebook_sample")
    if recorded is not None:
        return bool(recorded)
    try:
        book = job_pricebook(job)
    except QuoteShotError:
        return False
    return bool(book and book.get("sample"))


# ---------------------------------------------------------------------------
# photos

def add_photos(job_dir, job: dict, photo_paths) -> list[dict]:
    """Copy each photo into photos/, record it on the job, and save.

    Returns the new photo records. A taken file name gets a ``-2``,
    ``-3`` suffix instead of overwriting; a non-image is rejected
    by name (see :mod:`quoteshot.photos`).
    """
    d = Path(job_dir)
    photos_dir = d / PHOTOS_DIR
    photos_dir.mkdir(exist_ok=True)
    # Validate every source first, then copy: a batch used to copy the
    # good photos and only then fail on a missing / non-image file,
    # leaving orphan files in photos/ that job.json knew nothing about.
    described = [(raw, describe_photo(Path(raw))) for raw in photo_paths]
    added = []
    for raw, record in described:
        src = Path(raw)
        dest = photos_dir / record["filename"]
        same_file = dest.exists() and src.resolve() == dest.resolve()
        if not same_file:
            suffix = 2
            base, ext = dest.stem, dest.suffix
            while dest.exists():
                dest = photos_dir / f"{base}-{suffix}{ext}"
                suffix += 1
            shutil.copyfile(src, dest)
        record["stored_as"] = f"{PHOTOS_DIR}/{dest.name}"
        record["original_filename"] = Path(raw).name
        record["added_at"] = now_iso()
        job.setdefault("photos", []).append(record)
        added.append(record)
    save_job(d, job)
    return added


# ---------------------------------------------------------------------------
# notes / measurements

def add_note(job: dict, text: str, measurements: dict | None = None) -> None:
    """Append a timestamped note and/or merge measurements onto a job."""
    if text:
        job.setdefault("notes", []).append({"at": now_iso(), "text": text})
    for key, value in (measurements or {}).items():
        job.setdefault("measurements", {})[key] = value


# ---------------------------------------------------------------------------
# line items + totals

def add_item(job: dict, *, sku=None, name=None, price=None, qty="1",
             unit=None, description=None, taxable=None) -> dict:
    """Append one line item to a job and return it.

    With ``sku``, every field is snapshotted from the job's price
    book. Without it, ``name`` and an explicit ``price`` are required
    (an ad-hoc item). ``unit`` / ``description`` / ``taxable``, when
    given, override the snapshotted values for this line only.
    """
    qty_d = parse_decimal(qty, "qty")
    if qty_d <= 0:
        raise QuoteShotError(f"qty: must be greater than 0, got {qty_d}")
    if sku:
        book = job_pricebook(job)
        if book is None:
            raise QuoteShotError(
                f"add-item --sku {sku!r}: this job has no price book; set one "
                "at init with --pricebook, or add an ad-hoc item with "
                "--name and --price")
        found = find_item(book, sku)
        if found is None:
            known = ", ".join(i.get("sku", "?") for i in book.get("items", [])) or "(empty)"
            raise QuoteShotError(
                f"SKU {sku!r} not in price book {job.get('pricebook')}; known SKUs: {known}")
        item = {
            "sku": sku,
            "name": found.get("name", sku),
            "description": found.get("description", ""),
            "unit": found.get("unit", "each"),
            "unit_price": dec_str(parse_decimal(found["unit_price"], f"{sku} unit_price")),
            "qty": dec_str(qty_d),
            "taxable": bool(found.get("taxable", True)),
            "source": "pricebook",
        }
    else:
        if not name:
            raise QuoteShotError("add-item needs --sku, or --name with --price")
        if price is None:
            raise QuoteShotError(
                f"ad-hoc item {name!r}: --price is required (QuoteShot never "
                "invents a price)")
        price_d = parse_decimal(price, "unit_price")
        if price_d < 0:
            raise QuoteShotError(f"unit_price: negative price {price_d}")
        item = {
            "sku": None,
            "name": name,
            "description": description or "",
            "unit": unit or "each",
            "unit_price": dec_str(price_d),
            "qty": dec_str(qty_d),
            "taxable": True if taxable is None else bool(taxable),
            "source": "adhoc",
        }
    if unit and sku:
        item["unit"] = unit
    if description is not None and sku:
        item["description"] = description
    if taxable is not None and sku:
        item["taxable"] = bool(taxable)
    job.setdefault("items", []).append(item)
    return item


def remove_item(job: dict, index: int) -> dict:
    """Remove and return the item at 1-based ``index`` (as listed)."""
    items = job.get("items", [])
    if index < 1 or index > len(items):
        raise QuoteShotError(
            f"remove-item: index {index} out of range (job has {len(items)} item(s))")
    return items.pop(index - 1)


def line_total(item: dict) -> Decimal:
    """One line's total: quantity x unit price, rounded half-up to cents."""
    if not isinstance(item, dict):
        raise QuoteShotError(f"line item: must be an object, got {item!r}")
    if "taxable" in item and not isinstance(item["taxable"], bool):
        raise QuoteShotError(f"taxable: must be true or false, got {item['taxable']!r}")
    qty = parse_decimal(item.get("qty", "1"), "qty")
    if qty <= 0:
        # add_item enforces this at entry; enforce it here too so a
        # hand-edited job.json cannot render a negative-quantity quote.
        raise QuoteShotError(f"qty: must be greater than 0, got {qty}")
    price = parse_decimal(item.get("unit_price", "0"), "unit_price")
    if price < 0:
        raise QuoteShotError(f"unit_price: negative price {price}")
    # Multiply under a context sized to the operands: the ambient
    # 28-digit context silently rounds long products before they are
    # ever rounded to cents on purpose (polish A2).
    with localcontext() as ctx:
        ctx.prec = _wide_prec(qty, price)
        product = qty * price
    return money(product)


def totals(job: dict) -> dict:
    """Compute a job's totals.

    Returns a dict with ``lines`` (each item plus its ``line_total``),
    ``subtotal``, ``taxable_subtotal``, ``tax_rate``, ``tax``,
    ``total``, and ``currency``. Money values are Decimal. Tax is
    charged only on taxable lines: tax = taxable subtotal x tax rate.
    """
    raw_items = job.get("items", [])
    if not isinstance(raw_items, list):
        raise QuoteShotError(f"items: must be a list, got {raw_items!r}")
    currency_raw = job.get("currency") or "USD"
    if not isinstance(currency_raw, str):
        # .upper() on an int/list from a hand-edited job used to crash
        # totals (and every render) with an AttributeError traceback.
        raise QuoteShotError(f"currency: must be a string, got {currency_raw!r}")
    lines = []
    raw_lines = [(item, line_total(item)) for item in raw_items]
    with localcontext() as ctx:
        ctx.prec = _wide_prec(*(lt for _item, lt in raw_lines))
        subtotal = Decimal("0")
        taxable_subtotal = Decimal("0")
        for item, lt in raw_lines:
            subtotal += lt
            if item.get("taxable", True):
                taxable_subtotal += lt
    for item, lt in raw_lines:
        lines.append({**item, "line_total": dec_str(lt)})
    rate = parse_decimal(job.get("tax_rate", "0"), "tax_rate")
    if rate < 0 or rate > 1:
        # init_job enforces this at entry; a hand-edited job.json used
        # to render 500% (or negative) tax with no complaint at all.
        raise QuoteShotError(f"tax_rate: must be between 0 and 1, got {rate}")
    with localcontext() as ctx:
        ctx.prec = _wide_prec(taxable_subtotal, rate)
        raw_tax = taxable_subtotal * rate
    tax = money(raw_tax)
    with localcontext() as ctx:
        # subtotal + tax under the ambient 28-digit context silently
        # dropped the cents on large totals (1e30 + tax lost 0.01).
        ctx.prec = _wide_prec(subtotal, tax)
        grand = subtotal + tax
    return {
        "lines": lines,
        "subtotal": money(subtotal),
        "taxable_subtotal": money(taxable_subtotal),
        "tax_rate": rate,
        "tax": tax,
        "total": money(grand),
        "currency": currency_raw.upper(),
    }
