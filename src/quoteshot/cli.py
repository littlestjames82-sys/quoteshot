"""QuoteShot command-line interface.

QuoteShot turns photos you took on a walk-through, notes you typed,
and prices from a price book you own into a rendered quote. It never
looks inside a photo, never guesses a price, and never uses a network.

Run it two equivalent ways::

    quoteshot ...                  # if installed (pip install -e .)
    python3 -m quoteshot ...       # same commands, via the module

Every job command takes the job folder as its first argument (the
folder created by ``init``). Run ``quoteshot <command> --help`` for
the full options of any single command.

Quick start (see README.md for the annotated version)::

    quoteshot pricebook init my-prices.json
    quoteshot pricebook add my-prices.json --sku LABOUR-HR \\
        --name Labour --unit hour --price 85.00
    quoteshot init my-job --title "Kitchen faucet" \\
        --customer "Sample Customer" --tax-rate 0.0825 \\
        --pricebook my-prices.json
    quoteshot add-photo my-job IMG_0001.jpg
    quoteshot note my-job --text "Shut-off valve corroded" \\
        --measurement length_ft=24
    quoteshot add-item my-job --sku LABOUR-HR --qty 2
    quoteshot add-item my-job --name "Extra fitting" --price 12.50
    quoteshot render my-job        # writes my-job/quote.html + quote.txt

Command map::

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
  quoteshot check     <job-dir>
  quoteshot render    <job-dir> [--out <dir>]

  quoteshot pricebook init     <path> [--sample] [--currency USD]
  quoteshot pricebook list     <path>
  quoteshot pricebook add      <path> --sku ... --name ... --unit ...
                               --price ... [--description ...] [--no-tax]
                               [--replace]
  quoteshot pricebook validate <path>

Offline only. No AI, no API, no network. Prices come only from the
local price book or from an ad-hoc price the human types.
Tax rates are decimal fractions: 0.0825 means 8.25%, not 8.25.

Exit codes: 0 = done, 1 = user error (bad input, unknown SKU,
invalid price book item), 2 = could not proceed (no job there,
unreadable or corrupt file, or no command given).
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
from .check import check_job
from .render import render_job


# ---------------------------------------------------------------------------
# job commands

def cmd_init(args) -> int:
    """Create a job folder (job.json + photos/) for one job."""
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
    """Copy photo files into the job folder and record them."""
    job = load_job(args.job_dir)
    added = add_photos(args.job_dir, job, args.photos)
    for rec in added:
        dims = (f"{rec['width']}x{rec['height']}" if rec.get("width") else "dimensions unknown")
        exif = f"captured {rec['captured_at']}" if rec.get("captured_at") else "no EXIF"
        print(f"added {rec['stored_as']}: {rec['format']}, {dims}, {exif}")
    print(f"job now has {len(job['photos'])} photo(s)")
    return 0


def cmd_photos(args) -> int:
    """List the photos recorded for a job, by stored name."""
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
    """Append a free-text note and/or key=value measurements."""
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
    """Add one line item, by price-book SKU or as an ad-hoc item."""
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
    """List line items with line totals, subtotal, tax, and total."""
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
    """Remove the line item at the 1-based index shown by `items`."""
    job = load_job(args.job_dir)
    removed = remove_item(job, args.index)
    save_job(args.job_dir, job)
    print(f"removed item {args.index}: {removed.get('name')}")
    return 0


def cmd_show(args) -> int:
    """Print a one-screen summary of a job and its totals."""
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


def cmd_check(args) -> int:
    job = load_job(args.job_dir)
    report = check_job(args.job_dir, job)
    print(f"job check: {args.job_dir}")
    print(f"  photos: {report['photos_checked']} recorded, "
          f"{report['photos_ok']} verified on file")
    print(f"  items: {report['items_checked']} checked "
          f"({report['pricebook_items']} from price book, "
          f"{report['adhoc_items']} ad hoc)")
    print(f"  price book: {report['pricebook_status']}")
    for warning in report["warnings"]:
        print(f"  warning: {warning}")
    for problem in report["problems"]:
        print(f"  PROBLEM: {problem['detail']}")
    for drift in report["drift"]:
        print(f"  DRIFT: {drift['detail']}")
    if report["ok"]:
        print("  check: OK - photos verified, no price book drift")
        return 0
    print("  check: NOT OK - see above; the quote itself is unchanged "
          "(snapshots govern), decide before sending")
    return 1


def cmd_render(args) -> int:
    """Render quote.html and quote.txt for a job."""
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
    """Create an empty price book, or a labelled sample one."""
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
    """List every item in a price book with its unit price."""
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
    """Add one price-book item, or replace it with --replace."""
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
    """Check a price book file and report each problem by field."""
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
    """Build the argument parser.

    Help text is part of the interface: every argument explains what
    it means, what format it expects, and what happens by default, so
    ``quoteshot <command> --help`` is usable on its own.
    """
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(
        prog="quoteshot", formatter_class=fmt,
        description="Offline photo-to-quote workflow for trades: organise "
                    "photos you took into a job folder, add your own notes "
                    "and line items priced from your own price book, and "
                    "render a clean quote. No AI, no API, no network.",
        epilog="workflow:\n"
               "  1. pricebook init + pricebook add   build your price book once\n"
               "  2. init <job-dir>                   start a folder for one job\n"
               "  3. add-photo <job-dir> <photo>...   copy in walk-through photos\n"
               "  4. note <job-dir> --text ...        record notes / measurements\n"
               "  5. add-item <job-dir> --sku ...     price lines from your book,\n"
               "     or --name ... --price ...        or type a one-off price\n"
               "  6. render <job-dir>                 write quote.html + quote.txt\n"
               "\n"
               "examples:\n"
               "  quoteshot pricebook init my-prices.json\n"
               "  quoteshot init my-job --title \"Kitchen faucet\" "
               "--customer \"Sam\" --tax-rate 0.0825 --pricebook my-prices.json\n"
               "  quoteshot add-item my-job --sku LABOUR-HR --qty 2\n"
               "  quoteshot render my-job\n"
               "\n"
               "tax rates are decimal fractions: 0.0825 = 8.25%.\n"
               "exit codes: 0 = done, 1 = user error, 2 = could not proceed.\n"
               "run 'quoteshot <command> --help' for one command's options.")
    ap.add_argument("--version", action="version", version=f"quoteshot {__version__}",
                    help="print the version and exit")
    sub = ap.add_subparsers(dest="command")

    p = sub.add_parser("init", formatter_class=fmt,
                       help="create a job folder",
                       description="Create a job folder: job.json plus a "
                                   "photos/ subfolder. Refuses to overwrite "
                                   "an existing job.json.",
                       epilog="example:\n"
                              "  quoteshot init my-job --title \"Kitchen faucet\" "
                              "--customer \"Sam\" --tax-rate 0.0825 "
                              "--pricebook my-prices.json")
    p.add_argument("job_dir", help="folder to create for this job")
    p.add_argument("--title", required=True,
                   help="job title shown on the quote (required), "
                        "e.g. 'Kitchen faucet replacement'")
    p.add_argument("--customer", required=True,
                   help="customer name shown on the quote (required)")
    p.add_argument("--contact", default="",
                   help="customer contact shown on the quote, e.g. a phone "
                        "number or email (default: blank)")
    p.add_argument("--business", default="",
                   help="your business name shown at the top of the quote "
                        "(default: blank; the quote is then headed 'Quote')")
    p.add_argument("--tax-rate", default="0",
                   help="tax rate as a decimal fraction: 0.0825 = 8.25%% "
                        "(default: 0; this is not a percent, so do not type 8.25)")
    p.add_argument("--currency", default="USD",
                   help="currency code for this job, e.g. USD (default: USD; "
                        "if --pricebook is given, the book's currency wins)")
    p.add_argument("--pricebook", default=None,
                   help="path to your price book JSON; needed before you can "
                        "add items with --sku")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("add-photo", formatter_class=fmt,
                       help="copy photos into the job and record them",
                       description="Copy one or more photos into the job's "
                                   "photos/ folder and record each file's name, "
                                   "size, hash, dimensions, and camera details "
                                   "already in the file. Photos are copied byte "
                                   "for byte and are never analysed. A name that "
                                   "is already taken gets a -2, -3 suffix.",
                       epilog="example:\n"
                              "  quoteshot add-photo my-job IMG_0001.jpg IMG_0002.jpg")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.add_argument("photos", nargs="+",
                   help="photo file(s) to copy in; JPEG, PNG, or GIF only - "
                        "any other file is rejected by name")
    p.set_defaults(fn=cmd_add_photo)

    p = sub.add_parser("photos", formatter_class=fmt,
                       help="list recorded photos",
                       description="List the photos recorded for a job: stored "
                                   "name, format, dimensions, capture time, "
                                   "and a short hash. GPS is never listed.")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.set_defaults(fn=cmd_photos)

    p = sub.add_parser("note", formatter_class=fmt,
                       help="add a note and/or measurements",
                       description="Record your own notes and measurements on "
                                   "a job. At least one of --text or "
                                   "--measurement is required. Measurements are "
                                   "stored exactly as typed; they are not checked "
                                   "against any photo.",
                       epilog="example:\n"
                              "  quoteshot note my-job --text \"Valve corroded\" "
                              "--measurement length_ft=24 --measurement width_in=18")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.add_argument("--text", default="",
                   help="note text, shown on the quote under Notes")
    p.add_argument("--measurement", action="append", default=[],
                   help="one measurement as key=value, e.g. length_ft=24; "
                        "repeat the flag for more measurements")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("add-item", formatter_class=fmt,
                       help="add a line item (price book SKU or ad hoc)",
                       description="Add one line item to a job. Use exactly "
                                   "one pricing route: --sku copies the name, "
                                   "unit, price, and taxable flag from the job's "
                                   "price book at this moment (later book edits "
                                   "do not change this job), or --name + "
                                   "--price types a one-off price for this job "
                                   "only. QuoteShot never invents a price.",
                       epilog="examples:\n"
                              "  quoteshot add-item my-job --sku LABOUR-HR --qty 2\n"
                              "  quoteshot add-item my-job --name \"Extra fitting\" "
                              "--price 12.50 --qty 1")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.add_argument("--sku", default=None,
                   help="price-book SKU to price from (route 1; needs a job "
                        "created with --pricebook)")
    p.add_argument("--name", default=None,
                   help="ad-hoc item name for this job only (route 2; needs --price)")
    p.add_argument("--price", default=None,
                   help="ad-hoc unit price as decimal text, e.g. 12.50 "
                        "(required with --name)")
    p.add_argument("--qty", default="1",
                   help="quantity; may be fractional, e.g. 2.5 (default: 1)")
    p.add_argument("--unit", default=None,
                   help="unit label, e.g. each, hour, ft (default: the price "
                        "book's unit for --sku, otherwise 'each')")
    p.add_argument("--description", default=None,
                   help="optional description shown under the item on the quote")
    p.add_argument("--no-tax", action="store_true",
                   help="mark this line non-taxable; tax is charged only on "
                        "taxable lines")
    p.set_defaults(fn=cmd_add_item)

    p = sub.add_parser("items", formatter_class=fmt,
                       help="list line items and totals",
                       description="List a job's line items in order, with "
                                   "each line total, then subtotal, tax, and "
                                   "total. The numbers here are the index "
                                   "numbers 'remove-item' uses.")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.set_defaults(fn=cmd_items)

    p = sub.add_parser("remove-item", formatter_class=fmt,
                       help="remove a line item by its listed index",
                       description="Remove one line item by the 1-based index "
                                   "shown by 'quoteshot items <job-dir>'.")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.add_argument("index", type=int,
                   help="1-based line number shown by the 'items' command")
    p.set_defaults(fn=cmd_remove_item)

    p = sub.add_parser("show", formatter_class=fmt,
                       help="job summary",
                       description="Print a one-screen summary: customer, "
                                   "business, price book (with a [SAMPLE] flag "
                                   "if it was a sample book), photo/note/item "
                                   "counts, and subtotal, tax, and total.")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("check", formatter_class=fmt,
                       help="pre-send audit: photo integrity, item validity, price book drift",
                       description="Pre-send audit: verify every recorded "
                                   "photo against its recorded size and "
                                   "sha256, check every line item and the "
                                   "tax rate are valid, and report price "
                                   "book drift against the job's snapshots. "
                                   "Read-only; drift never changes the quote. "
                                   "Exits 0 when clean, 1 when problems or "
                                   "drift are found.")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("render", formatter_class=fmt,
                       help="render quote.html + quote.txt",
                       description="Render the customer quote: quote.html "
                                   "(formatted, photos shown) and quote.txt "
                                   "(plain text, photos listed by name). Both "
                                   "show each line item, subtotal, the tax line "
                                   "with the rate and taxable amount, and the "
                                   "total. Rendering invents nothing: a job "
                                   "with no items renders with 0.00 totals.",
                       epilog="example:\n"
                              "  quoteshot render my-job          # into my-job/\n"
                              "  quoteshot render my-job --out ./send-to-customer")
    p.add_argument("job_dir", help="job folder created by 'init'")
    p.add_argument("--out", default=None,
                   help="folder to write quote.html and quote.txt into "
                        "(default: the job folder itself)")
    p.set_defaults(fn=cmd_render)

    pb = sub.add_parser("pricebook", formatter_class=fmt,
                        help="manage a local price book JSON",
                        description="Manage a local price book: one JSON file "
                                    "you own that holds your prices. A job's "
                                    "items copy their price from it when they "
                                    "are added, so later edits never change a "
                                    "quote you already made.",
                        epilog="price book format (version 1):\n"
                               "  {\"version\": 1, \"currency\": \"USD\", \"sample\": false,\n"
                               "   \"items\": [{\"sku\": \"LABOUR-HR\", \"name\": \"Labour\",\n"
                               "              \"description\": \"Per hour\", \"unit\": \"hour\",\n"
                               "              \"unit_price\": \"85.00\", \"taxable\": true}]}\n"
                               "unit_price is decimal text in quotes, not a JSON number.\n"
                               "run 'quoteshot pricebook <command> --help' for details.")
    pbs = pb.add_subparsers(dest="pricebook_command")
    p = pbs.add_parser("init", formatter_class=fmt,
                       help="create a price book (empty, or --sample)",
                       description="Create a new price book file. Without "
                                   "--sample it starts empty; add your prices "
                                   "with 'pricebook add'. Refuses to overwrite "
                                   "an existing file unless --force is given.")
    p.add_argument("path", help="file to create, e.g. my-prices.json")
    p.add_argument("--sample", action="store_true",
                   help="fill it with labelled SAMPLE placeholder prices "
                        "instead; quotes from it carry a SAMPLE PRICES banner")
    p.add_argument("--currency", default="USD",
                   help="currency code stored in the book (default: USD)")
    p.add_argument("--force", action="store_true",
                   help="replace the file if it already exists")
    p.set_defaults(fn=cmd_pricebook_init)
    p = pbs.add_parser("list", formatter_class=fmt,
                       help="list price book items",
                       description="List every item in a price book: SKU, "
                                   "name, unit price, unit, and whether it is "
                                   "taxable. A sample book is labelled SAMPLE.")
    p.add_argument("path", help="price book file to list")
    p.set_defaults(fn=cmd_pricebook_list)
    p = pbs.add_parser("add", formatter_class=fmt,
                       help="add or --replace one item",
                       description="Add one item to a price book. Adding a "
                                   "SKU that already exists is an error; pass "
                                   "--replace to overwrite that item instead.",
                       epilog="example:\n"
                              "  quoteshot pricebook add my-prices.json --sku LABOUR-HR "
                              "--name Labour --unit hour --price 85.00")
    p.add_argument("path", help="price book file to add the item to")
    p.add_argument("--sku", required=True,
                   help="unique code you will use with add-item --sku, "
                        "e.g. LABOUR-HR (required)")
    p.add_argument("--name", required=True,
                   help="item name shown on quotes, e.g. Labour (required)")
    p.add_argument("--unit", required=True,
                   help="unit the price is per, e.g. hour, each, ft (required)")
    p.add_argument("--price", required=True,
                   help="unit price as decimal text, e.g. 85.00 (required)")
    p.add_argument("--description", default="",
                   help="optional description copied onto quotes that use this SKU")
    p.add_argument("--no-tax", action="store_true",
                   help="mark this item non-taxable (default: taxable)")
    p.add_argument("--replace", action="store_true",
                   help="overwrite the existing item with the same SKU")
    p.set_defaults(fn=cmd_pricebook_add)
    p = pbs.add_parser("validate", formatter_class=fmt,
                       help="validate a price book",
                       description="Check a price book file: version, item "
                                   "shape, duplicate SKUs, and that every price "
                                   "is a non-negative decimal. Each problem is "
                                   "printed with its SKU and field.")
    p.add_argument("path", help="price book file to check")
    p.set_defaults(fn=cmd_pricebook_validate)
    pb.set_defaults(fn=None)
    # Keep a handle so main() can show this parser's own help (not the
    # top-level help) when 'pricebook' is run with no subcommand.
    ap._pricebook_parser = pb  # type: ignore[attr-defined]
    return ap


def main(argv=None) -> int:
    """Run the CLI and return its exit code (0, 1, or 2; see module docs)."""
    ap = build_parser()
    args = ap.parse_args(argv)
    fn = getattr(args, "fn", None)
    if fn is None:
        # No command (or 'pricebook' with no subcommand): show the most
        # relevant help instead of an error, and exit 2 as before.
        if getattr(args, "command", None) == "pricebook":
            ap._pricebook_parser.print_help()  # type: ignore[attr-defined]
        else:
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
