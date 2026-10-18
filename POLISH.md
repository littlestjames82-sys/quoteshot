# QuoteShot v0.1 - Polish Report
Oct 14, 2026, at Ryan's "Polishing" direction, after Wave 3 parent
verification (31 tests passing). House loop: audit first, then two
distinct improvement passes, demonstrate-then-fix. Sole folder owner:
this polish round touched only `~/workspace/quoteshot/`.
No version bump, no release, no push, no publish, no announcements,
no spend. Stdlib only, no network, no external AI/API, no invented
prices - all gates from the build still hold.

## Audit findings (each demonstrated before any fix)

Method: read the whole core, ran the shipped suite (31 passed), then
ran two probe scripts against the unmodified code: a header fuzz
probe (a hand-built valid EXIF JPEG with GPS, truncated at every
length, 600 seeded random mutations, 200 magic-prefixed garbage
files, targeted corrupt TIFFs, plus money probes) and a lifecycle
probe (real CLI jobs whose price book was edited, deleted, and
corrupted after quoting), plus a realistic rendered quote read by eye.

- **A1 - Non-finite money values got through.** `Decimal` parses
  "NaN" and "Infinity" without complaint. Demonstrated: NaN price /
  qty / tax rate made `totals()` return NaN totals (a quote could
  print $NaN); an Infinity price passed `pricebook validate` as OK
  and then crashed `totals()` with an uncaught
  `decimal.InvalidOperation`; a NaN price crashed
  `pricebook validate` itself with a Python traceback.
- **A2 - Ambient Decimal precision (28 digits) broke big amounts.**
  Demonstrated: a finite price of 1e30 crashed `money()` with
  InvalidOperation, escaping the CLI's clean exit codes; products of
  long decimals were silently rounded at 28 significant digits before
  the deliberate cents rounding; `dec_str` used `normalize()` /
  `quantize()`, which apply that same context when writing prices
  back to JSON.
- **A3 - Zero dimensions did not fail soft consistently.** A PNG or
  GIF header claiming 0 width/height was recorded as a literal `0`;
  the JPEG path already mapped 0 to null.
- **A4 - The EXIF/header parsers were genuinely crash-proof.**
  Across all ~1,034 fuzz cases in the audit probe, every malformed or
  truncated JPEG/PNG/GIF produced either a record with null fields or
  a clean rejection by name. Zero exceptions escaped. Malformed TIFF
  byte order, magic, IFD counts, and out-of-range offsets all failed
  soft per field, GPS included. This needed locking in, not fixing.
- **A5 - The SAMPLE state was not snapshotted.** Item prices were,
  but `pricebook_is_sample()` re-read the live price book on every
  render and show. Demonstrated with the lifecycle probe: quoting
  from a sample book, then flipping the book's `sample` flag off,
  stripped the SAMPLE PRICES banner from the already-quoted job;
  deleting the book made `render` and `show` fail with exit 2, and
  corrupting it did the same, even though every number on the quote
  comes from the job's own snapshot.
- **A6 - Item field snapshots were solid.** Editing the book's price,
  name, unit, taxable flag, and description after quoting changed
  nothing on the rendered quote (subtotal $170.00, tax $14.03 held).
  The shipped test only pinned the price; the rest needed pinning.
- **A7 - Multi-line notes rendered badly.** In HTML a three-line note
  sat in one `<li>` with raw newlines, which browsers collapse into
  run-on text; in the text quote the continuation lines lost their
  indentation. The two quotes disagreed about the same note.
- **A8 - GPS was clean everywhere, but only two surfaces were
  tested.** Verified by probe: coordinates appear in `job.json` only
  (record-only, by design in PLAN.md); `render` output, render
  `--out` output, and the `photos` / `show` CLI listings show the
  photo by filename with no coordinates. Only the default render
  files had a regression test.

## Pass 1 - money gates and header fail-soft (A1, A2, A3, A4)

`src/quoteshot/money.py`
- `parse_decimal` now rejects non-finite values (NaN, sNaN,
  +/-Infinity, any spelling) with a `QuoteShotError` naming the
  field. It is the single parse gate for prices, quantities, and tax
  rates, so totals, validation, and the CLI all inherit the rule:
  validation now reports the field and exits 1 cleanly.
- `money()` quantizes under a local context sized from the value
  (`_wide_prec`), and `dec_str` is rebuilt on the exact
  `format(..., "f")` rendering with hand-trimmed zeros, so neither
  raises on nor silently rounds values past 28 significant digits.
  `money()` also raises `QuoteShotError` on a non-finite amount
  instead of letting a NaN reach a rendered quote.

`src/quoteshot/job.py`
- `line_total` multiplies, and `totals` sums and applies the tax
  rate, under operand-sized contexts, so the only rounding that ever
  happens to a quote is the deliberate ROUND_HALF_UP to cents.

`src/quoteshot/photos.py`
- PNG/GIF dimensions pass through the same `_dim` rule as JPEG:
  a claimed 0 is a malformed header and records as null.

Regression tests: `tests/test_polish_exif_money.py` (21 tests).
The audit fuzz corpus is now a permanent suite: valid EXIF+GPS JPEG
parses every field; truncation at every length, 250 seeded
mutations, magic-prefixed garbage, and the targeted corrupt-TIFF set
all fail soft; empty/unrecognised files are rejected by name; zero
dimensions record as null. Money tests pin non-finite rejection in
each field (parse, totals, price book validation, CLI exit code with
no traceback), exact large-amount arithmetic (1e30 subtotal, a
25-digit price x 6-digit quantity checked against exact fraction
arithmetic), and `dec_str` round-tripping long prices digit-for-digit.

## Pass 2 - snapshot completeness and the rendered quote (A5-A8)

`src/quoteshot/job.py`
- `init_job` records `pricebook_sample` in `job.json`, captured from
  the book at creation, with the same snapshot philosophy as item
  prices. `pricebook_is_sample` reads the recorded flag first.
  Jobs written before this polish have no flag: they fall back to
  the live book exactly as before, except an unreadable or missing
  book now fails soft to "not sample" instead of failing render and
  show outright. Demonstrated after the fix on a fresh lifecycle
  probe: banner survives the book's flag being flipped, and render /
  show return 0 with correct totals after the book is deleted or
  corrupted. The shipped examples' sample job deliberately keeps no
  recorded flag, so its test exercises the legacy fallback.

`src/quoteshot/render.py`
- New `_esc_multiline`: user text is escaped first (a typed "<br>"
  stays inert, pinned by test), then real newlines become `<br>`.
  Applied to notes, item descriptions, and measurement values, so
  the HTML quote keeps the author's line breaks.
- Text quote: continuation lines of a multi-line note are indented
  under the note bullet.
- Item table headers gained `scope="col"`.

`README.md`
- The snapshotting paragraph now also states that the job records
  whether its book was a sample book, and that a finished quote
  still renders if the price book is moved or deleted.

Regression tests: `tests/test_polish_snapshot_render.py` (9 tests).
Banner correctness in both flip directions; render and show survive
book deletion and corruption with totals intact; legacy-job fallback
and its soft failure; the full item snapshot (price, name, unit,
taxable, description) pinned against book edits; multi-line note
breaks in HTML and indentation in text; a typed "<br>" stays inert.
The GPS test is extended to every customer-visible surface: default
render, render `--out`, and the `photos` and `show` listings, with
the coordinates asserted present in `job.json` (record-only by
design) and absent from all of them.

## What was left alone, deliberately

- `describe_photo` reads the whole file into memory. The record
  requires a full-file sha256 anyway; a streaming rewrite would add
  risk to the parser the fuzz corpus just proved out, for a local
  CLI working on phone photos. Noted as a known limit, not a bug.
- EXIF located after the JPEG start-of-scan marker is not read
  (headers-only scan, documented in IMPLEMENTATION_A.md), and
  `captured_at` strings are recorded as the camera wrote them, not
  validated. Both are v0.1 scope calls from the PLAN.
- Decimal strings with underscores ("1_000") still parse, as
  Decimal accepts them and job/price-book files are the user's own;
  non-finite values were the actual hazard.
- Render `--out` to a folder outside the job still writes photo
  `src` paths relative to the job folder (documented limit from the
  build). The text quote is unaffected, and the default in-job
  render is self-contained.
- GPS storage in `job.json` itself stays exactly as designed: the
  photo already carried it, the folder is the user's own record,
  and no rendered or listed surface prints it.
- Examples were not modified: the sample job doubles as the
  legacy-format fixture for the fallback in pass 2.

## Final verification

- Full suite: see the count reported with this polish handoff; the
  pre-polish 31 tests all still pass, plus 30 new polish tests
  (21 pass 1 + 9 pass 2), no skips or xfails added.
- Both audit probe scripts re-run after the fixes: every previously
  demonstrated failure now behaves correctly (clean named errors,
  exact large-amount totals, banner stability, render/show survival,
  formatted multi-line notes), and the header fuzz still shows zero
  crashes.
- `python3 -m compileall src` clean; the suite's source scan still
  finds no network or AI imports anywhere in `src/quoteshot`.
