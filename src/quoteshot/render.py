"""Render a job as quote.html + quote.txt.

Photos are listed by filename (HTML also references each by its relative
photos/ path). GPS coordinates are never rendered. All user text is
HTML-escaped in the HTML output and verbatim in the text output.
Every quote states plainly: prices came from the local price book, the
photos were listed not analysed, and no AI was used.
"""
from __future__ import annotations

import html
from decimal import localcontext
from pathlib import Path

from .job import PHOTOS_DIR, pricebook_is_sample, totals
from .money import _wide_prec, fmt_money, parse_decimal

FOOTER = ("Prices are from the business's local price book as recorded in "
          "this quote. Photos are listed by filename only; they were not "
          "analysed. No AI or external service was used to produce this quote.")


def _pct(rate) -> str:
    """Tax rate as a percent string without noisy trailing zeros."""
    # Multiply and normalize under a context sized to the rate: the
    # ambient 28-digit context used to round the displayed rate on
    # long rates, so the quote's tax label disagreed with its maths.
    with localcontext() as ctx:
        ctx.prec = _wide_prec(rate)
        pct = (rate * 100).normalize()
    return format(pct, "f")


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _esc_multiline(value) -> str:
    """Escaped text that keeps the author's line breaks in HTML.

    Escape first (a typed "<br>" in a note stays inert text), then turn
    real newlines into <br>: before the polish, a multi-line note was
    one run-on line in the browser while the text quote kept its
    breaks, so the two quotes disagreed (polish A7).
    """
    return _esc(value).replace("\r\n", "\n").replace("\n", "<br>")


def _photo_line(p: dict) -> str:
    bits = [p.get("original_filename") or p.get("filename") or "?"]
    meta = []
    if p.get("width") and p.get("height"):
        meta.append(f"{p['width']}x{p['height']}")
    if p.get("captured_at"):
        meta.append(f"captured {p['captured_at']}")
    if p.get("camera_make") or p.get("camera_model"):
        meta.append(" ".join(x for x in [p.get("camera_make"), p.get("camera_model")] if x))
    if meta:
        bits.append("(" + ", ".join(meta) + ")")
    stored = p.get("stored_as")
    if stored and stored != f"{PHOTOS_DIR}/{bits[0]}":
        bits.append(f"[stored as {stored}]")
    return " ".join(bits)


def render_text(job: dict) -> str:
    """Return the plain-text quote (quote.txt content) for a job.

    Layout, top to bottom: business, SAMPLE banner if any, title /
    date / customer, notes, measurements, numbered items as
    ``qty unit x unit price = line total``, then Subtotal, a Tax line
    that names the rate and the taxable amount it was charged on,
    Total, the photo list (file names only), and the no-AI footer.
    """
    t = totals(job)
    cur = t["currency"]
    sample = pricebook_is_sample(job)
    out: list[str] = []
    business = (job.get("business") or {}).get("name") or "Quote"
    out.append(business)
    out.append("=" * max(len(business), 6))
    out.append("")
    if sample:
        out.append("*** SAMPLE PRICES - illustrative placeholders only ***")
        out.append("")
    out.append(f"Quote: {job.get('title', '')}")
    out.append(f"Date: {(job.get('created_at') or '')[:10]}")
    cust = job.get("customer") or {}
    out.append(f"Customer: {cust.get('name', '')}")
    if cust.get("contact"):
        out.append(f"Contact: {cust['contact']}")
    out.append("")
    if job.get("notes"):
        out.append("Notes:")
        for n in job["notes"]:
            note_lines = str(n.get("text", "")).splitlines() or [""]
            out.append(f"  - {note_lines[0]}")
            for extra in note_lines[1:]:
                out.append(f"    {extra}")
        out.append("")
    if job.get("measurements"):
        out.append("Measurements:")
        for k, v in job["measurements"].items():
            out.append(f"  - {k}: {v}")
        out.append("")
    out.append("Items:")
    if not t["lines"]:
        out.append("  (no line items yet)")
    for i, line in enumerate(t["lines"], 1):
        qty = parse_decimal(line.get("qty", "1"), "qty")
        price = parse_decimal(line.get("unit_price", "0"), "unit_price")
        desc = f" - {line['description']}" if line.get("description") else ""
        tax_note = "" if line.get("taxable", True) else " (not taxable)"
        out.append(
            f"  {i}. {line.get('name', '')}{desc}: {qty} {line.get('unit', 'each')} "
            f"x {fmt_money(price, cur)} = "
            f"{fmt_money(parse_decimal(line['line_total'], 'line_total'), cur)}{tax_note}")
    out.append("")
    out.append(f"Subtotal: {fmt_money(t['subtotal'], cur)}")
    out.append(f"Tax ({_pct(t['tax_rate'])}% on {fmt_money(t['taxable_subtotal'], cur)}): "
               f"{fmt_money(t['tax'], cur)}")
    out.append(f"Total: {fmt_money(t['total'], cur)}")
    out.append("")
    out.append("Photos:")
    if not job.get("photos"):
        out.append("  (none)")
    for p in job.get("photos", []):
        out.append(f"  - {_photo_line(p)}")
    out.append("")
    out.append(FOOTER)
    out.append("")
    return "\n".join(out)


_CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:2rem auto;
max-width:760px;padding:0 1rem;color:#1c1c22}
h1{font-size:1.5rem;margin-bottom:.2rem} h2{font-size:1.05rem;margin-top:1.6rem}
.muted{color:#555} .sample{background:#fff3cd;border:1px solid #d9a400;
padding:.6rem .8rem;border-radius:6px;font-weight:600}
table{border-collapse:collapse;width:100%;margin-top:.5rem}
th,td{border-bottom:1px solid #ddd;padding:.45rem .5rem;text-align:left;vertical-align:top}
td.num,th.num{text-align:right;white-space:nowrap}
.totals td{border-bottom:none} .totals .grand{font-weight:700;font-size:1.1rem}
figure{display:inline-block;margin:.4rem .6rem .4rem 0;text-align:center}
figure img{max-width:220px;max-height:220px;border:1px solid #ccc;border-radius:4px}
figcaption{font-size:.8rem;color:#555;max-width:220px;overflow-wrap:anywhere}
footer{margin-top:2rem;font-size:.85rem;color:#555;border-top:1px solid #ddd;padding-top:.6rem}
""".strip()


def render_html(job: dict) -> str:
    """Return the HTML quote (quote.html content) for a job.

    Same content and totals as :func:`render_text`, as a single
    self-contained page: all user text is HTML-escaped, photos are
    shown with ``<figure>`` elements, and GPS is never rendered.
    """
    t = totals(job)
    cur = t["currency"]
    sample = pricebook_is_sample(job)
    cust = job.get("customer") or {}
    business = (job.get("business") or {}).get("name") or "Quote"
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append(f"<title>Quote - {_esc(job.get('title', ''))}</title>")
    parts.append(f"<style>{_CSS}</style></head><body>")
    parts.append(f"<h1>{_esc(business)}</h1>")
    parts.append(f'<p class="muted">Quote: {_esc(job.get("title", ""))}<br>')
    parts.append(f"Date: {_esc((job.get('created_at') or '')[:10])}<br>")
    parts.append(f"Customer: {_esc(cust.get('name', ''))}")
    if cust.get("contact"):
        parts.append(f"<br>Contact: {_esc(cust['contact'])}")
    parts.append("</p>")
    if sample:
        parts.append('<p class="sample">SAMPLE PRICES - illustrative '
                     "placeholders only. Replace the sample price book "
                     "with your own prices before sending a real quote.</p>")
    if job.get("notes"):
        parts.append("<h2>Notes</h2><ul>")
        for n in job["notes"]:
            parts.append(f"<li>{_esc_multiline(n.get('text', ''))}</li>")
        parts.append("</ul>")
    if job.get("measurements"):
        parts.append("<h2>Measurements</h2><ul>")
        for k, v in job["measurements"].items():
            parts.append(f"<li>{_esc(k)}: {_esc_multiline(v)}</li>")
        parts.append("</ul>")
    parts.append("<h2>Items</h2>")
    parts.append('<table><thead><tr><th scope="col">Item</th>'
                 '<th scope="col" class="num">Qty</th>'
                 '<th scope="col" class="num">Unit price</th>'
                 '<th scope="col" class="num">Line total</th>'
                 "</tr></thead><tbody>")
    if not t["lines"]:
        parts.append('<tr><td colspan="4" class="muted">No line items yet.</td></tr>')
    for line in t["lines"]:
        qty = parse_decimal(line.get("qty", "1"), "qty")
        price = parse_decimal(line.get("unit_price", "0"), "unit_price")
        lt = parse_decimal(line["line_total"], "line_total")
        name = _esc(line.get("name", ""))
        if line.get("description"):
            name += f'<br><span class="muted">{_esc_multiline(line["description"])}</span>'
        if not line.get("taxable", True):
            name += ' <span class="muted">(not taxable)</span>'
        parts.append(
            f"<tr><td>{name}</td>"
            f'<td class="num">{_esc(qty)} {_esc(line.get("unit", "each"))}</td>'
            f'<td class="num">{_esc(fmt_money(price, cur))}</td>'
            f'<td class="num">{_esc(fmt_money(lt, cur))}</td></tr>')
    parts.append("</tbody></table>")
    parts.append('<table class="totals"><tbody>')
    parts.append(f'<tr><td>Subtotal</td><td class="num">{_esc(fmt_money(t["subtotal"], cur))}</td></tr>')
    parts.append(
        f"<tr><td>Tax ({_esc(_pct(t['tax_rate']))}% on "
        f"{_esc(fmt_money(t['taxable_subtotal'], cur))})</td>"
        f'<td class="num">{_esc(fmt_money(t["tax"], cur))}</td></tr>')
    parts.append(f'<tr class="grand"><td>Total</td><td class="num">'
                 f"{_esc(fmt_money(t['total'], cur))}</td></tr>")
    parts.append("</tbody></table>")
    parts.append("<h2>Photos</h2>")
    if not job.get("photos"):
        parts.append('<p class="muted">None recorded.</p>')
    for p in job.get("photos", []):
        stored = p.get("stored_as") or ""
        caption = _esc(_photo_line(p))
        # stored_as is a tool-generated relative path (photos/<name>);
        # escape it for the attribute all the same.
        parts.append(
            f'<figure><img src="{_esc(stored)}" alt="{caption}">'
            f"<figcaption>{caption}</figcaption></figure>")
    parts.append(f"<footer>{_esc(FOOTER)}</footer>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def render_job(job_dir, job: dict, out_dir=None) -> tuple[Path, Path]:
    """Write quote.html and quote.txt; return ``(html_path, txt_path)``.

    Output goes to ``out_dir`` if given, otherwise into the job
    folder itself.
    """
    out = Path(out_dir) if out_dir else Path(job_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / "quote.html"
    txt_path = out / "quote.txt"
    html_path.write_text(render_html(job), encoding="utf-8")
    txt_path.write_text(render_text(job), encoding="utf-8")
    return html_path, txt_path
