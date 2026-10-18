"""QuoteShot CLI.

  quoteshot init      <job-dir> --title ... --customer ...
                      [--contact ...] [--business ...]
                      [--tax-rate 0.0825] [--currency USD]
                      [--pricebook <pricebook.json>]
  quoteshot add-photo <job-dir> <photo> [<photo> ...]
  quoteshot photos    <job-dir>
  quoteshot note      <job-dir> --text "..." [--measurement k=v ...]
  quoteshot add-item  <job-dir> (--sku SKU | --name "..." --price N)
                      [--qty 1] [--unit each] [--description ...] [--no-tax]
  quoteshot items     <job-dir>
  quoteshot remove-item <job-dir> <index>
  quoteshot show      <job-dir>
  quoteshot render    <job-dir> [--out <dir>]

  quoteshot pricebook init     <path> [--sample] [--currency USD]
  quoteshot pricebook list     <path>
  quoteshot pricebook add      <path> --sku ... --name ... --unit ...
                               --price ... [--description ...] [--no-tax]
                               [--replace]
  quoteshot pricebook validate <path>

Offline only. No AI, no API, no network. Prices come only from the
local price book or from an ad-hoc price the human types.

Exit codes: 0 = done, 1 = user error, 2 = could not proceed.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .job import (add_item, add_note, add_photos, init_job, load_job,
                  pricebook_is_sample, remove_item, save_job, totals)
from .money import QuoteShotError, fmt_money, parse_decimal
from .pricebook import (empty_book, load_pricebook, normalise_item,
                        save_pricebook, upsert_item, validate_pricebook)
from .render import render_job


# ---------------------------------------------------------------------------
# job commands

def cmd_init(args) -> int:
    job = init_job(args.job_dir, title=args.title, customer=args.customer,
                   contact=args.contact or "", business=args.business or "",
                   tax_rate=args.tax_rate, currency=args.currency,
                   pricebook=args.pricebook)
    print(f"job created: {args.job_dir} (id {job['id']})")
    print(f"  title: {job['title']}  customer: {job['customer']['name']}")
    print(f"  tax rate: {job['tax_rate']}  currency: {job['currency']}")
    print(f"  photos folder: {args.job_dir}/photos/")
    if not job.get("pricebook"):
        print("  no price book set; add items ad hoc with --name/--price, "
              "or re-init with --pricebook")
    return 0


def cmd_add_photo(args) -> int:
    job = load_job(args.job_dir)
    added = add_photos(args.job_dir, job, args.photos)
    for rec in added:
        dims = (f"{rec['width']}x{rec['height']}" if rec.get("width") else "dimensions unknown")
        exif = f"captured {rec['captured_at']}" if rec.get("captured_at") else "no EXIF"
        print(f"added {rec['stored_as']}: {rec['format']}, {dims}, {exif}")
    print(f"job now has {len(job['photos'])} photo(s)")
    return 0


def cmd_photos(args) -> int:
    job = load_job(args.job_dir)
    if not job.get("photos"):
        print("(no photos recorded)")
        return 0
    for i, p in enumerate(job["photos"], 1):
        print(f"{i}. {p.get('stored_as')} - {p.get('format')}, "
              f"{p.get('width')}x{p.get('height')}, "
              f"captured {p.get('captured_at') or 'unknown'}, "
              f"sha256 {str(p.get('sha256'))[:12]}...")
    return 0


def cmd_note(args) -> int:
    job = load_job(args.job_dir)
    measurements = {}
    for pair in args.measurement or []:
        if "=" not in pair:
            raise QuoteShotError(
                f"--measurement expects key=value, got {pair!r}")
        k, v = pair.split("=", 1)
        if not k.strip():
            raise QuoteShotError(f"--measurement has an empty key: {pair!r}")
        measurements[k.strip()] = v.strip()
    if not args.text and not measurements:
        raise QuoteShotError("note needs --text and/or --measurement")
    add_note(job, args.text or "", measurements)
    save_job(args.job_dir, job)
    print("note recorded" if args.text else "measurements recorded")
    return 0


def cmd_add_item(args) -> int:
    job = load_job(args.job_dir)
    item = add_item(job, sku=args.sku, name=args.name, price=args.price,
                    qty=args.qty, unit=args.unit,
                    description=args.description,
                    taxable=(False if args.no_tax else None))
    save_job(args.job_dir, job)
    t = totals(job)
    line = [ln for ln in t["lines"]][-1]
    print(f"added item {len(job['items'])}: {item['name']} - "
          f"{item['qty']} {item['unit']} x "
          f"{fmt_money(parse_decimal(item['unit_price'], 'unit_price'), t['currency'])} "
          f"= {fmt_money(parse_decimal(line['line_total'], 'line_total'), t['currency'])}"
          f" (source: {item['source']}"
          f"{', qty defaulted to 1' if not args.qty_explicit else ''})")
    print(f"  running total: {fmt_money(t['total'], t['currency'])}")
    return 0


def cmd_items(args) -> int:
    job = load_job(args.job_dir)
    t = totals(job)
    if not t["lines"]:
        print("(no line items yet)")
        return 0
    for i, line in enumerate(t["lines"], 1):
        print(f"{i}. {line.get('name')} - {line.get('qty')} {line.get('unit')} x "
              f"{fmt_money(parse_decimal(line['unit_price'], 'unit_price'), t['currency'])} "
              f"= {fmt_money(parse_decimal(line['line_total'], 'line_total'), t['currency'])}"
              f"{' (not taxable)' if not line.get('taxable', True) else ''}")
    print(f"subtotal {fmt_money(t['subtotal'], t['currency'])}  "
          f"tax {fmt_money(t['tax'], t['currency'])}  "
          f"total {fmt_money(t['total'], t['currency'])}")
    return 0


def cmd_remove_item(args) -> int:
    job = load_job(args.job_dir)
    removed = remove_item(job, args.index)
    save_job(args.job_dir, job)
    print(f"removed item {args.index}: {removed.get('name')}")
    return 0


def cmd_show(args) -> int:
    job = load_job(args.job_dir)
    t = totals(job)
    print(f"job {job.get('id')}: {job.get('title')}")
    print(f"  customer: {(job.get('customer') or {}).get('name')}")
    print(f"  business: {(job.get('business') or {}).get('name') or '(not set)'}")
    print(f"  created: {job.get('created_at')}  currency: {t['currency']}  "
          f"tax rate: {job.get('tax_rate')}")
    print(f"  price book: {job.get('pricebook') or '(none)'}"
          f"{' [SAMPLE]' if pricebook_is_sample(job) else ''}")
    print(f"  photos: {len(job.get('photos', []))}  notes: {len(job.get('notes', []))}  "
          f"measurements: {len(job.get('measurements', {}))}  items: {len(job.get('items', []))}")
    print(f"  subtotal {fmt_money(t['subtotal'], t['currency'])}  "
          f"tax {fmt_money(t['tax'], t['currency'])}  "
          f"total {fmt_money(t['total'], t['currency'])}")
    return 0


def cmd_render(args) -> int:
    job = load_job(args.job_dir)
    html_path, txt_path = render_job(args.job_dir, job, args.out)
    t = totals(job)
    if pricebook_is_sample(job):
        print("WARNING: SAMPLE price book in use; the quote carries a "
              "SAMPLE PRICES banner.")
    print(f"rendered: {html_path}")
    print(f"rendered: {txt_path}")
    print(f"total: {fmt_money(t['total'], t['currency'])} "
          f"(subtotal {fmt_money(t['subtotal'], t['currency'])}, "
          f"tax {fmt_money(t['tax'], t['currency'])})")
    return 0


# ---------------------------------------------------------------------------
# pricebook commands

def cmd_pricebook_init(args) -> int:
    from pathlib import Path
    if Path(args.path).exists() and not args.force:
        raise QuoteShotError(
            f"price book {args.path} already exists; pass --force to replace it")
    book = empty_book(currency=args.currency, sample=args.sample)
    save_pricebook(args.path, book)
    if args.sample:
        print(f"SAMPLE price book created: {args.path}")
        print("  Prices in it are illustrative placeholders only. "
              "Replace them with your own before quoting a real job.")
    else:
        print(f"empty price book created: {args.path}")
    return 0


def cmd_pricebook_list(args) -> int:
    book = load_pricebook(args.path)
    if book.get("sample"):
        print("SAMPLE price book - illustrative placeholder prices only")
    if not book.get("items"):
        print("(no items)")
        return 0
    cur = (book.get("currency") or "USD").upper()
    for item in book["items"]:
        print(f"{item.get('sku')}: {item.get('name')} - "
              f"{fmt_money(parse_decimal(item['unit_price'], 'unit_price'), cur)} "
              f"per {item.get('unit')}"
              f"{' (not taxable)' if not item.get('taxable', True) else ''}")
    return 0


def cmd_pricebook_add(args) -> int:
    book = load_pricebook(args.path)
    item = normalise_item(args.sku, args.name, args.unit, args.price,
                          description=args.description or "",
                          taxable=not args.no_tax)
    upsert_item(book, item, replace=args.replace)
    save_pricebook(args.path, book)
    print(f"price book item {'replaced' if args.replace else 'added'}: "
          f"{item['sku']} at {item['unit_price']} per {item['unit']}")
    return 0


def cmd_pricebook_validate(args) -> int:
    import json
    from pathlib import Path
    p = Path(args.path)
    if not p.is_file():
        raise QuoteShotError(f"price book not found: {p}", fatal=True)
    try:
        book = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise QuoteShotError(f"price book {p}: unreadable JSON: {exc}", fatal=True) from None
    errors = validate_pricebook(book)
    if errors:
        for e in errors:
            print(f"INVALID: {e}")
        return 1
    print(f"price book OK: {p} ({len(book.get('items', []))} item(s)"
          f"{', SAMPLE' if book.get('sample') else ''})")
    return 0


# ---------------------------------------------------------------------------
# parser / main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="quoteshot",
        description="Offline photo-to-quote workflow for trades. "
                    "No AI, no API, no network in v0.1.")
    ap.add_argument("--version", action="version", version=f"quoteshot {__version__}")
    sub = ap.add_subparsers(dest="command")

    p = sub.add_parser("init", help="create a job folder")
    p.add_argument("job_dir")
    p.add_argument("--title", required=True)
    p.add_argument("--customer", required=True)
    p.add_argument("--contact", default="")
    p.add_argument("--business", default="")
    p.add_argument("--tax-rate", default="0")
    p.add_argument("--currency", default="USD")
    p.add_argument("--pricebook", default=None)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("add-photo", help="copy photos into the job and record them")
    p.add_argument("job_dir")
    p.add_argument("photos", nargs="+")
    p.set_defaults(fn=cmd_add_photo)

    p = sub.add_parser("photos", help="list recorded photos")
    p.add_argument("job_dir")
    p.set_defaults(fn=cmd_photos)

    p = sub.add_parser("note", help="add a note and/or measurements")
    p.add_argument("job_dir")
    p.add_argument("--text", default="")
    p.add_argument("--measurement", action="append", default=[])
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("add-item", help="add a line item (price book SKU or ad hoc)")
    p.add_argument("job_dir")
    p.add_argument("--sku", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--price", default=None)
    p.add_argument("--qty", default="1")
    p.add_argument("--unit", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--no-tax", action="store_true")
    p.set_defaults(fn=cmd_add_item)

    p = sub.add_parser("items", help="list line items and totals")
    p.add_argument("job_dir")
    p.set_defaults(fn=cmd_items)

    p = sub.add_parser("remove-item", help="remove a line item by its listed index")
    p.add_argument("job_dir")
    p.add_argument("index", type=int)
    p.set_defaults(fn=cmd_remove_item)

    p = sub.add_parser("show", help="job summary")
    p.add_argument("job_dir")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("render", help="render quote.html + quote.txt")
    p.add_argument("job_dir")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_render)

    pb = sub.add_parser("pricebook", help="manage a local price book JSON")
    pbs = pb.add_subparsers(dest="pricebook_command")
    p = pbs.add_parser("init", help="create a price book (empty, or --sample)")
    p.add_argument("path")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--currency", default="USD")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_pricebook_init)
    p = pbs.add_parser("list", help="list price book items")
    p.add_argument("path")
    p.set_defaults(fn=cmd_pricebook_list)
    p = pbs.add_parser("add", help="add or --replace one item")
    p.add_argument("path")
    p.add_argument("--sku", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--price", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--no-tax", action="store_true")
    p.add_argument("--replace", action="store_true")
    p.set_defaults(fn=cmd_pricebook_add)
    p = pbs.add_parser("validate", help="validate a price book")
    p.add_argument("path")
    p.set_defaults(fn=cmd_pricebook_validate)
    pb.set_defaults(fn=None)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    fn = getattr(args, "fn", None)
    if fn is None:
        ap.print_help()
        return 2
    # Remember whether --qty was typed (default print in add-item output).
    args.qty_explicit = True
    if args.command == "add-item":
        raw = sys.argv if argv is None else argv
        args.qty_explicit = any(str(a) == "--qty" or str(a).startswith("--qty=")
                                for a in raw)
    try:
        return int(fn(args))
    except QuoteShotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if exc.fatal else 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
