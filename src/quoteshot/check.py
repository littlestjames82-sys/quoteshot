"""Pre-send job check: verify what a quote is about to stand behind.

QuoteShot already *records* two kinds of evidence and, until this
module, never re-checked either of them:

- Every photo record carries ``size_bytes`` and a ``sha256`` of the
  file as copied in. Nothing verified them again, so a photo deleted
  from ``photos/`` or replaced/corrupted after the walk-through would
  still be listed on the rendered quote as if it were on file.
- Every price-book line item snapshots its price (and name, unit,
  description, taxable flag) at add time, deliberately, so later
  price-book edits never change a quoted job. PLAN.md's verification
  bar asks for the other half of that bargain: "say the price book
  changed if asked to validate". Nothing ever said it.

``check_job`` is that asking. It is a read-only audit of one job:

- photo integrity: each recorded photo still exists under the job
  folder, with the recorded size and sha256;
- line-item validity: every quantity and unit price still parses as
  a finite decimal, quantity > 0, price >= 0, and the job tax rate
  is finite and within 0..1 (hand-edited ``job.json`` is the user's
  own file, so a bad edit is reported by item and field, not crashed
  on - and never via a non-finite total);
- price-book drift: for each price-book item, the snapshot is compared
  field by field with the current price book. A changed price, a
  renamed/re-unit-ed/re-taxed item, or a SKU that is gone from the
  book is reported as drift. Drift never changes the quote - the
  snapshot still governs - it is reported so the human can decide
  whether to re-quote before sending. Ad-hoc items have no book
  entry by design and are never drift.

The check reads only local files, changes nothing, and fails soft on
an unreadable price book exactly as rendering does (polish A5): the
quote survives a moved or deleted book, so the check reports the book
as unavailable instead of failing the whole audit.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .job import job_pricebook, pricebook_is_sample
from .money import QuoteShotError, parse_decimal
from .pricebook import find_item

# Fields snapshotted from the price book at add-item time (job.add_item).
# Compared as stored text/values so a formatting-only difference in the
# book ("85.0" vs "85.00") is judged on the parsed price, not the string.
_DRIFT_TEXT_FIELDS = ("name", "unit", "description")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_photos(job_dir: Path, job: dict, report: dict) -> None:
    for idx, rec in enumerate(job.get("photos") or [], 1):
        report["photos_checked"] += 1
        label = rec.get("stored_as") or rec.get("filename") or f"photo {idx}"
        stored = rec.get("stored_as")
        path = (job_dir / stored) if stored else None
        if path is None or not path.is_file():
            report["problems"].append({
                "kind": "photo_missing", "photo": label,
                "detail": f"photo {label}: recorded but not found in the job folder"})
            continue
        ok = True
        size = path.stat().st_size
        if rec.get("size_bytes") is not None and rec["size_bytes"] != size:
            ok = False
            report["problems"].append({
                "kind": "photo_size_mismatch", "photo": label,
                "detail": (f"photo {label}: size is {size} bytes, "
                           f"record says {rec['size_bytes']}")})
        recorded_hash = rec.get("sha256")
        if recorded_hash and _sha256(path) != recorded_hash:
            ok = False
            report["problems"].append({
                "kind": "photo_hash_mismatch", "photo": label,
                "detail": (f"photo {label}: contents no longer match the "
                           "sha256 recorded when the photo was added "
                           "(file replaced or corrupted)")})
        if ok:
            report["photos_ok"] += 1


def _check_items_and_tax(job: dict, report: dict) -> None:
    try:
        rate = parse_decimal(job.get("tax_rate", "0"), "tax_rate")
        if rate < 0 or rate > 1:
            report["problems"].append({
                "kind": "invalid_field", "field": "tax_rate",
                "detail": f"tax_rate: must be between 0 and 1, got {rate}"})
    except QuoteShotError as exc:
        report["problems"].append({
            "kind": "invalid_field", "field": "tax_rate", "detail": str(exc)})
    for idx, item in enumerate(job.get("items") or [], 1):
        report["items_checked"] += 1
        label = item.get("name") or item.get("sku") or f"item {idx}"
        where = f"item {idx} ({label})"
        if item.get("source") == "pricebook":
            report["pricebook_items"] += 1
        else:
            report["adhoc_items"] += 1
        for field, rule in (("qty", "positive"), ("unit_price", "non_negative")):
            try:
                value = parse_decimal(item.get(field), f"{where} {field}")
            except QuoteShotError as exc:
                report["problems"].append({
                    "kind": "invalid_field", "field": field, "detail": str(exc)})
                continue
            if rule == "positive" and value <= 0:
                report["problems"].append({
                    "kind": "invalid_field", "field": field,
                    "detail": f"{where} qty: must be greater than 0, got {value}"})
            if rule == "non_negative" and value < 0:
                report["problems"].append({
                    "kind": "invalid_field", "field": field,
                    "detail": f"{where} unit_price: negative price {value}"})


def _check_drift(job: dict, report: dict) -> None:
    pb_items = [it for it in (job.get("items") or [])
                if it.get("source") == "pricebook" and it.get("sku")]
    if not job.get("pricebook"):
        if pb_items:
            report["warnings"].append(
                "job has price-book items but records no price book; "
                "drift cannot be checked")
        return
    if pricebook_is_sample(job):
        report["warnings"].append(
            "price book was a SAMPLE book when this job was created; "
            "quotes from it carry the SAMPLE PRICES banner")
    try:
        book = job_pricebook(job)
    except QuoteShotError as exc:
        # Fail soft, like render/show: the quote stands on its snapshots.
        report["pricebook_status"] = "unavailable"
        report["warnings"].append(
            f"price book unavailable ({exc}); drift cannot be checked, "
            "the quote itself is unaffected")
        return
    if book is None:
        report["pricebook_status"] = "unavailable"
        return
    report["pricebook_status"] = "checked"
    for item in pb_items:
        sku = item["sku"]
        current = find_item(book, sku)
        if current is None:
            report["drift"].append({
                "sku": sku, "field": "sku", "snapshot": sku, "current": None,
                "detail": (f"SKU {sku!r} is no longer in the price book "
                           "(snapshot price "
                           f"{item.get('unit_price')} still governs this quote)")})
            continue
        try:
            snap_price = parse_decimal(item.get("unit_price"),
                                       f"{sku} unit_price")
            cur_price = parse_decimal(current.get("unit_price"),
                                      f"{sku} unit_price")
            price_changed = snap_price != cur_price
        except QuoteShotError:
            price_changed = str(item.get("unit_price")) != str(current.get("unit_price"))
        if price_changed:
            report["drift"].append({
                "sku": sku, "field": "unit_price",
                "snapshot": str(item.get("unit_price")),
                "current": str(current.get("unit_price")),
                "detail": (f"SKU {sku!r} unit_price: quote snapshot is "
                           f"{item.get('unit_price')}, price book now says "
                           f"{current.get('unit_price')}")})
        for field in _DRIFT_TEXT_FIELDS:
            if str(item.get(field) or "") != str(current.get(field) or ""):
                report["drift"].append({
                    "sku": sku, "field": field,
                    "snapshot": str(item.get(field) or ""),
                    "current": str(current.get(field) or ""),
                    "detail": (f"SKU {sku!r} {field}: quote snapshot is "
                               f"{item.get(field) or ''!r}, price book now "
                               f"says {current.get(field) or ''!r}")})
        if bool(item.get("taxable", True)) != bool(current.get("taxable", True)):
            report["drift"].append({
                "sku": sku, "field": "taxable",
                "snapshot": str(bool(item.get("taxable", True))),
                "current": str(bool(current.get("taxable", True))),
                "detail": (f"SKU {sku!r} taxable: quote snapshot is "
                           f"{bool(item.get('taxable', True))}, price book now "
                           f"says {bool(current.get('taxable', True))}")})


def check_job(job_dir, job: dict) -> dict:
    """Audit one loaded job. Read-only; never raises for job content.

    Returns a report dict: ``ok`` (no problems and no drift),
    ``problems`` (integrity/validity failures), ``drift`` (snapshot vs
    current price book), ``warnings``, and the checked counts.
    """
    report: dict = {
        "ok": True,
        "problems": [],
        "drift": [],
        "warnings": [],
        "photos_checked": 0,
        "photos_ok": 0,
        "items_checked": 0,
        "pricebook_items": 0,
        "adhoc_items": 0,
        "pricebook_status": "none",
    }
    _check_photos(Path(job_dir), job, report)
    _check_items_and_tax(job, report)
    _check_drift(job, report)
    report["ok"] = not report["problems"] and not report["drift"]
    return report
