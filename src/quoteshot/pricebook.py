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
    book = {"version": 1, "currency": currency.upper(), "sample": bool(sample),
            "items": list(SAMPLE_ITEMS) if sample else []}
    if sample:
        book["note"] = ("SAMPLE price book. Prices are illustrative placeholders "
                        "only, not market prices and not any real business's prices.")
    return book


def load_pricebook(path) -> dict:
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
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(book, indent=2) + "\n", encoding="utf-8")
    return p


def validate_pricebook(book) -> list[str]:
    errors: list[str] = []
    if not isinstance(book, dict):
        return ["price book must be a JSON object"]
    if book.get("version") != 1:
        errors.append("version: must be 1")
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
        if not sku or not isinstance(sku, str):
            errors.append(f"{where}.sku: missing or not a string")
            continue
        where = f"item {sku!r}"
        if sku in seen:
            errors.append(f"{where}: duplicate SKU")
        seen.add(sku)
        if not item.get("name"):
            errors.append(f"{where}.name: missing")
        if not item.get("unit"):
            errors.append(f"{where}.unit: missing")
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
    for item in book.get("items", []):
        if item.get("sku") == sku:
            return item
    return None


def upsert_item(book: dict, item: dict, replace: bool = False) -> None:
    existing = find_item(book, item["sku"])
    if existing is not None and not replace:
        raise QuoteShotError(
            f"price book already has SKU {item['sku']!r}; pass --replace to overwrite it")
    if existing is not None:
        book["items"][book["items"].index(existing)] = item
    else:
        book.setdefault("items", []).append(item)


def normalise_item(sku, name, unit, unit_price, description="", taxable=True) -> dict:
    price = parse_decimal(unit_price, f"item {sku!r} unit_price")
    if price < 0:
        raise QuoteShotError(f"item {sku!r} unit_price: negative price {price}")
    return {"sku": sku, "name": name, "description": description or "",
            "unit": unit, "unit_price": dec_str(price), "taxable": bool(taxable)}
