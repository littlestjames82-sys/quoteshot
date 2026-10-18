# QuoteShot - Photo-to-Quote Workflow for Trades
Working name, prepared Oct 14, 2026. Wave 3, business-side tool for Ghost Developer Studio.
Decision: NOT Goliath. Goliath stays reserved for a non-agent product (Ryan, Oct 11-12, 2026).
Decision: NOT a hackathon submission. QuoteShot was the runner-up to LoadMaster in Ryan's Oct 14, 2026 Meta Global AI Developer Hackathon pick. It is built here as a local Ghost Developer Studio tool. Any hackathon use is a separate Ryan gate.

## Why this name
- QuoteShot: plain job, plain name. A tradesperson takes shots of a job, QuoteShot turns those shots plus human notes into a quote.
- Checked against the family: sits next to GhostCut / GhostSlice as a Ghost Developer Studio tool, but it is deliberately *not* a GhostSlice companion. It serves trades customers, not agent workflows, so it does not borrow Slice's bundle format or vocabulary.
- Alternatives held in reserve: JobQuote, SnapQuote (both generic and crowded). Treat QuoteShot as a working name until a name check runs at any public gate, same discipline as GhostSlice on Oct 12, 2026.

## The problem
A solo tradesperson or small crew finishes a walk-through with:
- Photos of the job scattered in a phone camera roll, with no job attached to them.
- Measurements and notes on paper, in a text thread, or in memory.
- Prices in their head, in a supplier list, or in last year's invoices.
- A customer waiting on a number, who usually gets it late, as a text message, with no line items, no tax breakdown, and no record either side can point back to.

The tools that fix this properly are field-service platforms: accounts, cloud sync, per-seat pricing, and a setup project before the first quote. That is the wrong shape for the East Tennessee shops Ghost Developer Studio already pitches (no website, no system, owner does the quoting at night).

Today there is no local, offline, no-account way to say: this folder is this job, these are its photos, these are the human's notes and measurements, price it from *my* price book, and hand the customer a clean quote I can also keep.

## Position in the Ghost stack
- QuoteShot is a business-side studio tool, in the same family as the After-Hours Front Desk and the digital storefront bundle: it helps a small trade business look professional and respond fast, on hardware it already owns.
- LoadMaster (the hackathon project Ryan chose Oct 14, 2026) checks a *haul* from a photo. QuoteShot does not check, judge, or measure anything in a photo. It organises photos a human took and prices work a human scoped.
- GhostSlice / Seatbelt / Ghost Hands / the Wave 1-3 agent tools govern what agents read and do. QuoteShot has no agent in it at all in v0.1. Nothing in this plan changes any gate on those tools.

Story: walk the job -> photos into the job folder -> human notes and measurements in -> line items priced from the local price book -> clean HTML + plain-text quote out, photos listed by filename.

## What v0.1 is, plainly
- **No external AI or API in v0.1.** No image AI, no vision model, no OCR, no cloud call, no network at all. That is stated here, in the README, in `--help`, and on every rendered quote.
- **The tool does not look inside a photo and decide anything.** It records photo filenames and EXIF basics (capture time, camera make/model, pixel dimensions, GPS only if the photo already carries it) using Python stdlib parsing only. It does not identify objects, measure from pixels, estimate quantities, or judge condition or safety.
- **The human scopes the job.** Notes, measurements, quantities, and which line items apply are entered by the human. QuoteShot does arithmetic and formatting, nothing more.
- **No invented prices.** Every price comes from a local price book JSON the user supplies and owns. The bundled sample price book is labelled SAMPLE in the file, in CLI output, and on any quote rendered from it, and its prices are illustrative placeholders, not market prices, not Ryan's prices, and not any real business's prices.

## How it works, concretely
Data the tool owns, all local files, no database, no account:
- A **job folder**: `job.json` (customer, title, business, tax rate, currency, notes, measurements, photos, line items), a `photos/` subfolder, and rendered output (`quote.html`, `quote.txt`) written into the job folder or an `--out` folder the user names.
- A **price book JSON**: `{version, currency, sample: true|false, items: [{sku, name, description, unit, unit_price, taxable}]}`. One price book can serve many jobs. Prices are stored and passed through as decimal strings, never binary floats.
- Photo records: `{filename, stored_as, size_bytes, sha256, format, width, height, captured_at, camera_make, camera_model, has_gps, gps_lat, gps_lon}`. GPS fields are present only when the source EXIF already contains them; the tool never adds location it was not given.

Integration contract:
- Input: a job folder path for every command after `init`. Humans and scripts drive it the same way; it is a CLI first, like Slice v0.1.
- Output: `quote.html` (self-contained, inline CSS, no external assets, photos referenced by relative filename) + `quote.txt` (plain text, photos listed by filename). Both are the customer-facing quote. `job.json` stays the machine-readable record.
- Money: `decimal.Decimal` end to end, `ROUND_HALF_UP` to cents, per-line totals, taxable subtotal separated from non-taxable, one tax rate per job in v0.1.

## MVP (v0.1) - local CLI first, no dashboard, no mobile app
Rationale: same as GhostSlice v0.1. A CLI proves the workflow on real job folders in days. A phone UI is the obvious v0.2 candidate once the quote itself is trusted, and it is a separate Ryan gate.

1. Init a job: `quoteshot init <job-dir> --title "..." --customer "..." [--contact ...] [--business ...] [--tax-rate 0.0825] [--currency USD] [--pricebook <path>]`
   - Creates the job folder, `photos/`, and `job.json`. Refuses to overwrite an existing `job.json` unless `--force` is passed.
   - Tax rate is user-supplied per job. The tool ships no tax table and guesses no jurisdiction's rate.

2. Photos: `quoteshot add-photo <job-dir> <photo> [<photo> ...]`
   - Copies each photo into `photos/` (a name collision gets a `-2`, `-3` suffix, never a silent overwrite), records filename, size, sha256, format, and EXIF basics parsed with stdlib only (JPEG APP1/Exif TIFF IFD0 + Exif IFD, JPEG SOF dimensions, PNG IHDR, GIF header).
   - A photo with no EXIF is still recorded; its EXIF fields are `null` and the record says so. A file that is not a recognised image is rejected by name, not silently stored.
   - `quoteshot photos <job-dir>` lists what is recorded.

3. Human input: `quoteshot note <job-dir> --text "..." [--measurement key=value ...]`
   - Notes are free text, appended, timestamped. Measurements are `key=value` pairs (for example `length_ft=24`), stored as entered. The tool does not parse, convert, or check measurements against photos.

4. Price book: `quoteshot pricebook init|list|add|validate`
   - `pricebook init <path> [--sample]`: creates an empty price book, or with `--sample` a small illustrative one with `sample: true` and SAMPLE labelling in every item description.
   - `pricebook add <path> --sku ... --name ... --unit ... --price ... [--description ...] [--no-tax]`: adds or replaces one item by SKU. Duplicate SKU without `--replace` is an error.
   - `pricebook list <path>` / `pricebook validate <path>`: shows items, and checks schema, duplicate SKUs, negative prices, and non-decimal prices. Validation errors name the SKU and the field.

5. Line items: `quoteshot add-item <job-dir> (--sku <sku> | --name "..." --price ...) --qty ... [--unit ...] [--description ...] [--no-tax]`
   - With `--sku`, name / description / unit / unit price / taxable come from the job's price book. The price is snapshotted into `job.json` at add time, so later price-book edits never silently change an already-quoted job.
   - With `--name` + `--price`, it is an ad-hoc item the human typed for this job only. Both paths require an explicit quantity; there is no default quantity of anything but `1` when `--qty` is omitted, and that default is printed in the add output.
   - `quoteshot items <job-dir>` lists items with line totals. `quoteshot remove-item <job-dir> <index>` removes one by its listed index.

6. Totals and render: `quoteshot render <job-dir> [--out <dir>]`
   - Totals: line total = qty x unit price; subtotal = sum of line totals; tax = taxable subtotal x job tax rate; total = subtotal + tax. All Decimal, all rounded half-up to cents at line level, shown with the rate that produced them.
   - `quote.html`: business, customer, job title, date, notes, measurements, a line-item table, subtotal / tax / total, and a photo section listing each photo by filename (with capture time and dimensions when known) and referencing it by relative path. Sample price book in use adds a visible SAMPLE PRICES banner.
   - `quote.txt`: the same content in plain text, photos listed by filename only.
   - Every quote carries the plain footer: prices come from the business's local price book, photos were listed not analysed, and no AI was used to produce the quote.
   - Exit codes: 0 = done, 1 = user error (bad input, missing price book item, invalid job), 2 = could not proceed (unreadable job, corrupt price book). Errors name the file and the field.

## Out of scope for v0.1
- Any image AI, vision model, OCR, object detection, measurement-from-photo, or condition/safety judgement. (LoadMaster explores photo analysis as a separate hackathon project; it is not smuggled into QuoteShot.)
- Any network call, API, account, cloud sync, telemetry, or sending the quote anywhere. Rendering a file the human then sends themselves is the whole delivery story.
- Invoicing, payments, deposits, signatures, or quote acceptance tracking. A quote is a document, not a transaction.
- A tax engine, jurisdiction lookup, or tax advice. One user-supplied rate per job.
- Scheduling, CRM, customer databases, or importing contacts.
- Mobile app, dashboard, or photo capture. The phone's own camera app takes the photos; QuoteShot starts from files.
- Editing, enhancing, or re-encoding photos. Files are copied byte for byte and hashed, never modified.

## Build estimate
- Job model + price book + money arithmetic: 2-3 days
- Stdlib EXIF / image-header parsing (JPEG, PNG, GIF) with adversarial fixtures: 2-3 days
- CLI (init, add-photo, note, pricebook, add-item, items, render, show): 2 days
- HTML + text renderers with escaping and sample labelling: 1-2 days
- Tests, README, end-to-end demo on a synthetic job folder: 2 days
Total: roughly 1.5 to 2 weeks to a verified v0.1 if built straight through. EXIF parsing is the part most likely to slip; JPEG + PNG cover the real phone-photo cases and GIF is header-only.

## Pricing draft (NOT public, NOT decided)
- MIT core CLI free, same pattern as Slice / Seatbelt / Ghost Hands, is the candidate shape only.
- Paid candidate later only: a packaged version bundled into the studio's digital storefront offer for trades (site + quote workflow + after-hours desk). Do not build a paid layer, licensing, or accounts before a free v0.1 validates that a real shop will use it.

## Verification bar
- Golden totals test: a hand-computed job (mixed taxable and non-taxable items, fractional quantities, a tax rate with 4 decimal places) must match the rendered subtotal, tax, and total to the cent.
- Snapshot test: change the price book after an item is added; the rendered quote must still show the snapshotted price, and say the price book changed if asked to validate.
- EXIF tests: a JPEG with known DateTime / Make / Model / dimensions, a PNG with known dimensions, and a photo with no EXIF must each record exactly the fields they carry, no invented fields.
- Sample labelling test: a quote rendered from a sample price book must carry the SAMPLE banner in both HTML and text; a quote from a non-sample book must not.
- Escaping test: customer names, notes, and item descriptions containing HTML must render escaped in `quote.html` and verbatim in `quote.txt`.
- No-network test: the package imports and runs with no socket use; a source scan finds no `urllib`, `requests`, `socket`, or model/API client in `src/`.

## Risks / honest notes
- EXIF is messy in the wild: messaging apps strip it, editors rewrite it, and some cameras write malformed TIFF offsets. The parser must fail soft per field (record `null`, keep the photo), never crash a job over one photo's metadata.
- GPS in EXIF is a privacy surface. v0.1 records it only because the photo already carries it and the job folder is the user's own local record; rendered customer quotes list photos by filename and do **not** print GPS coordinates. That split is deliberate and must not drift.
- A clean quote can make a guessed price look authoritative. The quote shows the price book snapshot and the tax rate used, so the human can defend every number on it. Copy must never say the tool "estimated" or "assessed" the job.
- Trades pricing varies by business and by week. That is exactly why there are no shipped real prices: the sample is labelled, and everything real is user-supplied.

## Next gate
Ryan's go on: (1) QuoteShot as working name for a business-side tool, (2) CLI-first with phone UI deferred to a separate v0.2 gate, (3) the no-AI-in-v0.1 stance staying absolute even though LoadMaster explores photo analysis separately, (4) whether a real pilot shop tries v0.1 before any packaging into the storefront offer.
