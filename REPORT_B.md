# QuoteShot v0.1 - Report B (tests / README / examples)

Owner: Agent B. Scope owned: `tests/**`, `README.md`, `examples/**`, this report.
Not touched: `src/**`, `pyproject.toml`, `PLAN.md` (Agent A).

## Result

**31 passed** (`python3 -m pytest tests/ -q`, Python 3.12, run against
Agent A's completed core in the same tree). No xfails, no skips.

## What was delivered

### Tests (`tests/`, 31 tests)

- `conftest.py` - CLI entrypoint discovery (`quoteshot` script or
  `python -m quoteshot` with `src/` on PYTHONPATH; behavioural tests
  fail, never skip, if the core is missing), price-book/job helpers,
  a rendered-text totals parser, and a stdlib PNG writer for fixtures.
  The contract from PLAN.md is documented in its docstring.
- `test_calculations.py` (12) - the required calculation tests against
  `quoteshot.job.totals` / `line_total`, all hand-computed:
  - **Subtotal**: 75.00 + 2x85.00 + 129.99 = 374.99; per-line totals.
  - **Tax**: taxable subtotal only (374.99 x 0.0825 = 30.94); PLAN
    golden mixed case (taxable 229.99 of 259.99 subtotal, fractional
    qty 2.5, non-taxable items excluded, tax 18.97).
  - **Total**: 405.93 simple case; 278.96 golden case; total always
    equals subtotal + tax.
  - **Empty job**: all totals 0.00, no lines.
  - Rounding: ROUND_HALF_UP proven distinct from banker's rounding
    (50.00 x 0.0625 = 3.125 -> tax 3.13); line-level half-up
    (3 x 33.335 -> 100.01); no float dust (0.10 + 0.20 = 0.30 exactly).
  - Cross-check: shipped sample job recomputes to its `expected` block.
- `test_cli_render.py` (8) - full CLI flow (init, add-item by SKU,
  render): totals parsed from `quote.txt` match hand arithmetic
  (374.99 / 30.94 / 405.93); same totals in `quote.html`; empty job
  renders 0.00s and says "no line items"; SAMPLE PRICES banner present
  in both outputs from a sample book and absent from a non-sample book;
  price snapshotting (book raised to 999.00 after add, quote still
  85.00); unknown SKU errors and names the SKU; ad-hoc item without
  `--price` is refused; every quote footer states no AI was used and
  prices came from the local price book.
- `test_examples.py` (6) - independent Decimal recomputation of the
  shipped examples (core error cannot hide behind itself): sample book
  schema + SAMPLE labelling on every item, core validation passes,
  sample job = 374.99 / 30.94 / 405.93 and every item snapshotted at
  the book price, photo record's size/sha256/dimensions match the
  actual 1x1 PNG file, empty job example is zero, and the sample job
  renders in-process with banner and expected totals.
- `test_photos_and_safety.py` (5) - PNG added via CLI records format
  and 4x3 dimensions with null EXIF fields (nothing invented);
  a `.txt` file is rejected by name and not recorded; a job carrying
  GPS coordinates renders the photo by filename with the coordinates
  nowhere in HTML or text; HTML escapes a `<script>` customer name
  while text output is verbatim; source scan finds no
  urllib/requests/socket/http.client/httpx/openai/anthropic/aiohttp
  import anywhere in `src/quoteshot`.

### README.md

Plain-language: what it does, the no-AI stance in its own section
(does not analyse photos, guess quantities, or invent prices), the
five-step everyday workflow with the exact CLI commands from PLAN.md,
price book format and management commands, price snapshotting, sample
labelling, the totals formula (line = qty x price; tax on taxable
lines only; Decimal, half-up), photo/privacy rules (GPS never printed
on a quote), an explicit does-not-do list, and a check-your-numbers
responsibility note. No em dashes.

### Examples (`examples/`)

- `pricebook.sample.json` - version 1 book, `"sample": true`, four
  items in PLAN schema (sku / name / description / unit / decimal-text
  `unit_price` / taxable), SAMPLE in every description.
- `sample-job/job.json` - a job file in the exact shape `init` writes
  (customer/business objects, tax rate as text, notes, measurements,
  photo records, snapshotted items) plus an `expected` totals block.
  Arithmetic: 374.99 subtotal, 30.94 tax at 0.0825, 405.93 total.
- `sample-job/photos/before.png` - a real 68-byte 1x1 PNG (no one's
  real photo); its job.json record's size, sha256, and dimensions are
  the values the tool itself records, verified by test.
- `empty-job/job.json` - valid empty job, all totals 0.00.
- `README.md` - file guide, hand-checked arithmetic for both the
  sample job and the golden mixed-tax job, and the job-folder shape.

Also verified manually outside pytest: rendering the shipped sample
job via the CLI from inside its folder prints the SAMPLE warning,
writes both outputs, and shows Subtotal $374.99 / Tax $30.94 /
Total $405.93.

## Contract alignment note

Agent A's PLAN and core landed while these tests were being written,
so the tests target the real API, not a guess: `quoteshot.job.totals`,
CLI commands `init / add-photo / add-item / render / pricebook`, and
the version 1 job/price-book schemas. One early draft of the examples
used a different schema (float prices, `id` instead of `sku`); it was
replaced with the PLAN schema before the final run. Relative price
book references in `job.json` (for example `../pricebook.sample.json`)
resolve against the current working directory, so the shipped sample
renders when run from inside its folder, which the render test
documents.

## Gates honoured

Local only. No push, no publish, no announcements, no spend. No
network used by the tests (subprocess CLI runs are local; the
no-network source scan is part of the suite).
