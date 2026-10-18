"""Shared helpers for the QuoteShot tests (Agent B).

CONTRACT (from PLAN.md, confirmed against Agent A's core as it landed):
  package quoteshot, modules:
    quoteshot.job       init_job / load_job / add_item / totals / line_total
    quoteshot.money     parse_decimal / money / fmt_money / QuoteShotError
    quoteshot.pricebook load_pricebook / validate_pricebook / find_item
    quoteshot.photos    describe_photo
    quoteshot.render    render_text / render_html / render_job
  CLI (python -m quoteshot):
    init <dir> --title --customer [--tax-rate] [--pricebook] [...]
    add-photo <dir> <photo>... | photos <dir> | note <dir> --text [--measurement k=v]
    pricebook init|list|add|validate
    add-item <dir> (--sku SKU | --name N --price P) --qty Q [--no-tax]
    items <dir> | remove-item <dir> <index>
    render <dir> [--out <dir>]

Money is Decimal end to end, prices/qty stored as strings in JSON,
tax = taxable subtotal x tax_rate, ROUND_HALF_UP to cents.

Behavioural CLI tests FAIL (never skip) if no entrypoint exists, so a
green run cannot be faked by a missing core. Pure example tests in
test_examples.py pass on their own.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def find_entrypoint():
    script = shutil.which("quoteshot")
    if script:
        return [script]
    if (SRC / "quoteshot" / "__main__.py").exists():
        return [sys.executable, "-m", "quoteshot"]
    try:
        import quoteshot  # noqa: F401
        return [sys.executable, "-m", "quoteshot"]
    except Exception:
        return None


ENTRYPOINT = find_entrypoint()


def run_cli(args, timeout=60):
    if ENTRYPOINT is None:
        pytest.fail("QuoteShot core not ready: no entrypoint found "
                    "(no quoteshot script, no src/quoteshot package).")
    env = dict(os.environ)
    if SRC.is_dir():
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["NO_COLOR"] = "1"
    return subprocess.run(ENTRYPOINT + [str(a) for a in args],
                          capture_output=True, text=True, timeout=timeout, env=env)


def out_text(proc):
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def write_pricebook(path, items, sample=False, currency="USD"):
    book = {"version": 1, "currency": currency, "sample": bool(sample),
            "items": items}
    Path(path).write_text(json.dumps(book, indent=2) + "\n")
    return Path(path)


def pb_item(sku, price, name=None, unit="each", taxable=True, description=""):
    return {"sku": sku, "name": name or sku, "description": description,
            "unit": unit, "unit_price": str(price), "taxable": bool(taxable)}


def init_job(tmp_path, pricebook=None, tax_rate="0.0825", title="Test job",
             customer="Test Customer", name="job"):
    job_dir = tmp_path / name
    args = ["init", job_dir, "--title", title, "--customer", customer,
            "--tax-rate", tax_rate]
    if pricebook is not None:
        args += ["--pricebook", pricebook]
    proc = run_cli(args)
    assert proc.returncode == 0, out_text(proc)
    return job_dir


def add_item(job_dir, *extra):
    proc = run_cli(["add-item", job_dir, *extra])
    assert proc.returncode == 0, out_text(proc)
    return proc


def render(job_dir, out_dir=None):
    args = ["render", job_dir]
    if out_dir is not None:
        args += ["--out", out_dir]
    proc = run_cli(args)
    assert proc.returncode == 0, out_text(proc)
    base = Path(out_dir) if out_dir is not None else Path(job_dir)
    html_path, txt_path = base / "quote.html", base / "quote.txt"
    assert html_path.is_file(), f"quote.html not written by render: {out_text(proc)}"
    assert txt_path.is_file(), f"quote.txt not written by render: {out_text(proc)}"
    return html_path.read_text(), txt_path.read_text()


_MONEY_RE = r"\$?(-?[\d,]+\.\d{2})"


def totals_from_text(text):
    """Extract {'subtotal': Decimal, 'tax': Decimal, 'total': Decimal}
    from a rendered plain-text quote."""
    found = {}
    for label, key in (("Subtotal", "subtotal"), ("Tax", "tax"), ("Total", "total")):
        m = re.search(rf"^{label}\b[^\n]*?{_MONEY_RE}\s*$", text,
                      flags=re.MULTILINE)
        if not m:
            # Tax line carries '(rate% on $X)' before its amount; fall back
            # to the LAST money amount on the labelled line.
            for line in text.splitlines():
                if line.startswith(label):
                    amounts = re.findall(_MONEY_RE, line)
                    if amounts:
                        m_val = amounts[-1]
                        found[key] = Decimal(m_val.replace(",", ""))
                        break
            continue
        found[key] = Decimal(m.group(1).replace(",", ""))
    return found


def make_png(path, width=1, height=1):
    """Write a real PNG of the given dimensions (stdlib only)."""
    import struct, zlib

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\x00" * (width * 4) for _ in range(height))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend)
    return Path(path)
