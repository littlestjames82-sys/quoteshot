"""Local price book JSON: user-supplied prices, nothing invented.

Format (version 1):
{
  "version": 1,
  "currency": "USD",
  "sample": false,
  "items": [
    {"sku": "LABOUR-HR", "name": "Labour", "description": "",
     "unit": "hr", "unit_price": "0.00", "taxable": true}
  ]
}
`sample: true` marks the illustrative sample book. That flag flows into
every quote rendered from it as a visible SAMPLE banner.
"""
from __future__ import annotations

import json
from pathlib import Path

from .money import QuoteShotError, dec_str, parse_decimal

SAMPLE_ITEMS = [
    {"sku": "SAMPLE-LABOUR-HR", "name": "SAMPLE - Labour (per hour)",
     "description": "SAMPLE placeholder price, replace with your own.",
     "unit": "hr", "unit_price": "10.00", "taxable": True},
    {"sku": "SAMPLE-CALL-OUT", "name": "SAMPLE - Call-out fee",
     "description": "SAMPLE placeholder price, replace with your own.",
     "unit": "each", "unit_price": "25.00", "taxable": True},
    {"sku": "SAMPLE-MATERIAL", "name": "SAMPLE - Material (example)",
     "description": "SAMPLE placeholder price, replace with your own.",
     "unit": "each", "unit_price": "5.00", "taxable": True},
]


def empty_book(currency: str = "USD", sample: bool = False) -> dict:
    """Return a new version-1 price book dict (empty, or SAMPLE-filled)."""
    if not isinstance(currency, str) or not currency.strip():
        raise QuoteShotError(f"currency: must be a non-empty string, got {currency!r}")
    book = {"version": 1, "currency": currency.upper(), "sample": bool(sample),
            "items": list(SAMPLE_ITEMS) if sample else []}
    if sample:
        book["note"] = ("SAMPLE price book. Prices are illustrative placeholders "
                        "only, not market prices and not any real business's prices.")
    return book


def load_pricebook(path) -> dict:
    """Load a price book file and validate it; raise a named error if bad."""
    p = Path(path)
    if not p.is_file():
        raise QuoteShotError(f"price book not found: {p}", fatal=True)
    try:
        book = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise QuoteShotError(f"price book {p}: unreadable JSON: {exc}", fatal=True) from None
    errors = validate_pricebook(book)
    if errors:
        raise QuoteShotError(
            f"price book {p} is invalid:\n" + "\n".join(f"  - {e}" for e in errors),
            fatal=True)
    return book


def save_pricebook(path, book: dict) -> Path:
    """Write ``book`` as JSON to ``path`` (creating folders); return it."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(book, indent=2) + "\n", encoding="utf-8")
    return p


def validate_pricebook(book) -> list[str]:
    """Return a list of problems with ``book`` (empty list means valid).

    Each problem names its item by SKU (or position) and its field,
    e.g. a duplicate SKU, a missing name/unit, or a negative price.
    """
    errors: list[str] = []
    if not isinstance(book, dict):
        return ["price book must be a JSON object"]
    if isinstance(book.get("version"), bool) or book.get("version") != 1:
        errors.append("version: must be 1")
    if "currency" in book and (not isinstance(book["currency"], str)
                               or not book["currency"].strip()):
        errors.append("currency: must be a non-empty string")
    if "sample" in book and not isinstance(book["sample"], bool):
        # A string "false" is truthy: it used to pass validation and
        # then stamp a SAMPLE banner on every quote from the book.
        errors.append("sample: must be true or false")
    items = book.get("items")
    if not isinstance(items, list):
        return errors + ["items: must be a list"]
    seen: set[str] = set()
    for idx, item in enumerate(items):
        where = f"items[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        sku = item.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            errors.append(f"{where}.sku: missing or not a string")
            continue
        where = f"item {sku!r}"
        if sku in seen:
            errors.append(f"{where}: duplicate SKU")
        seen.add(sku)
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"{where}.name: missing")
        if not isinstance(item.get("unit"), str) or not item["unit"].strip():
            errors.append(f"{where}.unit: missing")
        if "description" in item and not isinstance(item["description"], str):
            errors.append(f"{where}.description: must be a string")
        if "unit_price" not in item:
            errors.append(f"{where}.unit_price: missing")
        else:
            try:
                price = parse_decimal(item["unit_price"],
                                      f"{where}.unit_price")
                if price < 0:
                    errors.append(f"{where}.unit_price: negative price {price}")
            except QuoteShotError as exc:
                errors.append(str(exc))
        if "taxable" in item and not isinstance(item["taxable"], bool):
            errors.append(f"{where}.taxable: must be true or false")
    return errors


def find_item(book: dict, sku: str) -> dict | None:
    """Return the price-book item with exactly this ``sku``, or None."""
    for item in book.get("items", []):
        if item.get("sku") == sku:
            return item
    return None


def upsert_item(book: dict, item: dict, replace: bool = False) -> None:
    """Add ``item`` to ``book``; a duplicate SKU needs ``replace=True``."""
    existing = find_item(book, item["sku"])
    if existing is not None and not replace:
        raise QuoteShotError(
            f"price book already has SKU {item['sku']!r}; pass --replace to overwrite it")
    if existing is not None:
        book["items"][book["items"].index(existing)] = item
    else:
        book.setdefault("items", []).append(item)


def normalise_item(sku, name, unit, unit_price, description="", taxable=True) -> dict:
    """Build a validated price-book item dict from raw CLI/file values."""
    # The CLI writes whatever this returns straight into the book: a
    # blank sku/name/unit used to be saved without complaint and the
    # book then failed its own validation on the next load.
    for field, value in (("sku", sku), ("name", name), ("unit", unit)):
        if not isinstance(value, str) or not value.strip():
            raise QuoteShotError(f"item {field}: must be a non-empty string, got {value!r}")
    price = parse_decimal(unit_price, f"item {sku!r} unit_price")
    if price < 0:
        raise QuoteShotError(f"item {sku!r} unit_price: negative price {price}")
    return {"sku": sku, "name": name, "description": description or "",
            "unit": unit, "unit_price": dec_str(price), "taxable": bool(taxable)}
