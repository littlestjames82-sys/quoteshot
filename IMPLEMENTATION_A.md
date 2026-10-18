# QuoteShot v0.1 - Implementation Report (Agent A, core owner)
Built Oct 14, 2026. Agent A owns: PLAN.md, src/**, pyproject.toml, this file.
Agent B owns: tests, README, examples (REPORT_B.md).

## Gates honoured
Local only, stdlib only (`dependencies = []`), no push, no publish, no
announcements, no spend, no network. No external AI/API anywhere in v0.1 -
there is no image analysis of any kind; photos are recorded by filename
plus EXIF basics parsed from file headers. No invented prices: every
price comes from the user's local price book (snapshotted into the job at
add time) or from an ad-hoc `--price` the human typed; the sample price
book is labelled SAMPLE in the file, in CLI output, and on rendered quotes.
Verified by grep: no `urllib`, `requests`, `socket`, or `http.client`
anywhere in `src/`. QuoteShot is NOT a hackathon submission; it is a
local Ghost Developer Studio tool (separate Ryan gate, see PLAN.md).

## Files
- `PLAN.md` - full plan in GhostSlice format (name, problem, stack
  position, v0.1 plainly/no-AI statement, data contract, MVP, out of
  scope, build estimate, pricing draft NOT decided, verification bar,
  risks, next gate).
- `pyproject.toml` - quoteshot 0.1.0, MIT, Python >=3.10, console script
  `quoteshot = quoteshot.cli:main`, zero dependencies.
- `src/quoteshot/__init__.py` - version 0.1.0 + no-AI statement docstring.
- `src/quoteshot/__main__.py` - `python -m quoteshot`.
- `src/quoteshot/money.py` - Decimal arithmetic, ROUND_HALF_UP cents,
  `QuoteShotError` (fatal flag -> exit 2 vs 1), money formatting.
- `src/quoteshot/photos.py` - photo records: filename, size, sha256,
  format, dimensions, EXIF basics. Hand-written stdlib parsers: JPEG
  segments + SOF dimensions, APP1 Exif TIFF (IFD0 Make/Model/DateTime,
  Exif IFD DateTimeOriginal preferred, GPS IFD lat/lon when the photo
  already carries them), PNG IHDR, GIF header. Every EXIF field fails
  soft to None; non-images are rejected by name.
- `src/quoteshot/pricebook.py` - price book v1 schema, load/save,
  validation (duplicate SKU, negative / non-decimal price, missing
  fields, each error naming SKU + field), upsert, and `SAMPLE_ITEMS`
  labelled placeholders behind `sample: true`.
- `src/quoteshot/job.py` - job folder model: init (refuses overwrite),
  load/save `job.json`, photo copying with `-2`/`-3` collision suffixes
  (never silent overwrite, same-file safe), notes + measurements,
  price-book and ad-hoc line items (price snapshot), remove-item,
  Decimal totals (taxable subtotal separated).
- `src/quoteshot/render.py` - `quote.html` (self-contained, inline CSS,
  all user text HTML-escaped, photos as figures referenced by relative
  `photos/<name>` path with filename caption) + `quote.txt` (verbatim
  text, photos listed by filename). SAMPLE banner in both when the job's
  price book is a sample. GPS coordinates are never rendered. Every quote
  carries the footer: prices from the local price book, photos listed
  not analysed, no AI used.
- `src/quoteshot/cli.py` - argparse CLI, exit codes 0/1/2.

## Commands
```
quoteshot init <job-dir> --title ... --customer ... [--contact ...]
               [--business ...] [--tax-rate 0.0825] [--currency USD]
               [--pricebook <path>]
quoteshot add-photo <job-dir> <photo> [<photo> ...]
quoteshot photos <job-dir>
quoteshot note <job-dir> --text "..." [--measurement key=value ...]
quoteshot add-item <job-dir> (--sku SKU | --name "..." --price N)
               [--qty 1] [--unit ...] [--description ...] [--no-tax]
quoteshot items <job-dir>
quoteshot remove-item <job-dir> <index>
quoteshot show <job-dir>
quoteshot render <job-dir> [--out <dir>]
quoteshot pricebook init <path> [--sample] [--currency USD] [--force]
quoteshot pricebook list <path>
quoteshot pricebook add <path> --sku ... --name ... --unit ... --price ...
               [--description ...] [--no-tax] [--replace]
quoteshot pricebook validate <path>
```
`qty` defaults to 1 only when omitted, and add-item output says so
("(source: pricebook, qty defaulted to 1)").

## Smoke test (Agent A, /tmp/qs-demo, Python 3.12.3)
Fixtures built from scratch in stdlib: a JPEG with hand-built EXIF
(TestCam / TC-1, DateTime 2026:10:14 08:30:00, DateTimeOriginal
08:31:05, SOF 800x600) and a PNG (24x18).

- EXIF: captured time recorded as DateTimeOriginal (08:31:05), make/model
  read, JPEG 800x600 and PNG 24x18 dimensions correct, PNG has_exif false.
- Photo flow: two photos copied + recorded; re-adding the same file made
  `site-2.jpg` (no overwrite); a `.txt` file was rejected by name, exit 1.
- Golden totals (hand-computed): boards 10 x 12.50 = 125.00, labour
  3.5 x 60 = 210.00, non-taxable permit 75.00, ad-hoc haul-off 40.00 ->
  subtotal 450.00, taxable 375.00, tax 375 x 0.0825 = 30.9375 -> 30.94
  (half-up), total 480.94. Tool output matched exactly.
- Snapshot: price book DECK-BOARD changed to 99.00 (--replace) after the
  item was added; `show`/render still priced the job at 12.50.
- Sample labelling: job on the sample book printed the SAMPLE warning at
  init and at render, and both quote.html and quote.txt carry the banner;
  the real-book job's quotes do not.
- Escaping: a job title containing `<script>alert(1)</script>` rendered
  as `&lt;script&gt;...` in HTML and verbatim in text.
- GPS: no GPS string appears in rendered HTML (GPS is record-only, per
  PLAN privacy split).
- Errors: unknown SKU exit 1 (known SKUs listed), ad-hoc item without
  `--price` exit 1, missing price book exit 2, duplicate price book init
  refused, duplicate SKU without `--replace` refused.
- `python3 -m compileall src` clean.

## Known limits / notes for Agent B and parent verification
- EXIF parser is fail-soft by design: malformed TIFF yields null fields,
  never a crash. GPS rounding is 7 dp. JPEGs whose EXIF lives after SOS
  are not read (headers-only scan, standard practice).
- Tax is one user-supplied rate per job on the taxable subtotal; no tax
  table, no jurisdiction logic (per PLAN, out of scope).
- `render --out` to a folder outside the job writes quote files whose
  `photos/...` image references are relative to the job folder; the text
  quote is unaffected. In-job render (the default) is fully self-contained.
- Prices stored as decimal strings in JSON; hand-edited JSON numbers
  (floats) are parsed via `str()` in money.parse_decimal.
- No tests/README/examples from Agent A (Agent B's surface). Suggested
  Agent B fixtures: the PLAN verification bar (golden totals, snapshot,
  EXIF, sample labelling, escaping, no-network source scan) maps 1:1 to
  test cases; the smoke above is reproducible as an end-to-end test.
