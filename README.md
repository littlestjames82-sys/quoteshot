# QuoteShot

**Walk the job, take photos, price it from your own price book, hand the customer a clean quote. All on your own computer, with no AI and no internet.**

A solo tradesperson finishes a walk-through with photos scattered in a
camera roll, notes on paper, and prices in their head. The customer
gets a number late, usually as a text message with no line items and
no tax breakdown.

QuoteShot gives that job a folder instead:

- Photos a human took, copied in and listed by file name.
- Notes and measurements a human entered.
- Line items a human chose, priced from a local price book the
  business owns, or typed in for that one job.
- A clean HTML quote and a plain-text quote, with subtotal, tax, and
  total worked out and shown.

By Ghost Developer Studio.

In this README:

- [No AI in this tool](#no-ai-in-this-tool-at-all) and
  [what you need](#you-need)
- [Try it in two minutes](#try-it-in-two-minutes) with the sample files
- [The everyday workflow](#the-everyday-workflow) and a
  [command cheat sheet](#command-cheat-sheet)
- [Checking a job before you send the quote](#checking-a-job-before-you-send-the-quote)
- [Your price book](#your-price-book): every field, explained
- [Photos: the workflow in detail](#photos-the-workflow-in-detail)
- [Reading the rendered quote](#reading-the-rendered-quote): an
  annotated example
- [How the numbers work](#how-the-numbers-work),
  [troubleshooting](#troubleshooting), and
  [exit codes](#exit-codes)

## No AI in this tool. At all.

QuoteShot does **not** look inside a photo and decide anything. It
does not identify objects, measure from pictures, guess quantities,
judge condition, or estimate a price. It records a photo's file name
and basic file details (and camera details already inside the photo
file, when they are there), and that is all.

Every line item, quantity, measurement, and price on a quote was
entered by a person, or taken from a price book that person owns.
QuoteShot does arithmetic and formatting, nothing more.

Nothing is sent anywhere. There are no accounts, no uploads, no cloud
sync, and no network use.

## You need

- Python 3.10 or newer. No third-party packages: QuoteShot uses only
  the Python standard library.
- Your own price book file (see [Your price book](#your-price-book)),
  or the supplied sample one to try the tool out.

### How the commands are written in this README

Commands are shown short, as `quoteshot ...`. That is the command you
get after installing the package (`pip install -e .` from this
folder). Without installing, run the same commands from this folder
in the long form:

```bash
PYTHONPATH=src python3 -m quoteshot ...
```

For example, `quoteshot render my-job` and
`PYTHONPATH=src python3 -m quoteshot render my-job` do exactly the
same thing. Every command also documents itself:

```bash
quoteshot --help            # command list, workflow, and examples
quoteshot init --help       # one command in full, every flag explained
quoteshot pricebook --help  # the price book format, in brief
```

## Try it in two minutes

No price book of your own yet? Use the sample one. Sample prices are
made-up placeholders (see
[Sample prices are labelled sample](#sample-prices-are-labelled-sample)),
so this run is for seeing the shape of the tool, not for quoting a
real job.

```bash
# Start a job priced from the sample price book
quoteshot init demo-job --title "Kitchen faucet" --customer "Sample Customer" --tax-rate 0.0825 --pricebook examples/pricebook.sample.json

# Copy in the sample photo that ships with the tool
quoteshot add-photo demo-job examples/sample-job/photos/before.png

# Add two lines from the book (watch the prices get copied in)
quoteshot add-item demo-job --sku SERVICE-CALL --qty 1
quoteshot add-item demo-job --sku LABOUR-HR --qty 2

# Render, then open demo-job/quote.html or read demo-job/quote.txt
quoteshot render demo-job
```

You should see a total of $245.00 plus $20.21 tax = $265.21, and a
warning that a SAMPLE price book is in use. The rendered quote carries
the SAMPLE PRICES banner for the same reason.

A ready-made sample job is also in `examples/`. See
`examples/README.md` for the hand-checked arithmetic behind it, and
[Reading the rendered quote](#reading-the-rendered-quote) below for
how to read what `render` writes.

## The everyday workflow

Six steps, in order. Steps 2 to 4 can be repeated in any order until
you render.

```bash
# 1. Start a job folder
#    --tax-rate is a decimal fraction: 0.0825 means 8.25% (not 8.25)
quoteshot init my-job --title "Kitchen faucet" --customer "Sample Customer" --tax-rate 0.0825 --pricebook pricebook.json

# 2. Add the photos you took on the walk-through
#    One file, or several at once. JPEG, PNG, or GIF only.
quoteshot add-photo my-job IMG_0001.jpg
quoteshot photos my-job

# 3. Add your notes and measurements
#    A measurement is key=value; repeat --measurement for more.
quoteshot note my-job --text "Shut-off valve corroded" --measurement length_ft=24

# 4. Add line items: priced from your price book by SKU,
#    or typed in for this job only (QuoteShot never guesses a price)
quoteshot add-item my-job --sku LABOUR-HR --qty 2
quoteshot add-item my-job --name "Extra fitting" --price 12.50 --qty 1
quoteshot items my-job

# 5. Render the quote: writes quote.html and quote.txt into my-job/
#    (or into another folder with: render my-job --out some-folder)
quoteshot render my-job

# 6. Before you send it, check the job
quoteshot check my-job
```

What `init` creates, and where everything lives afterwards:

```text
my-job/
  job.json        the job record: customer, title, tax rate, notes,
                  measurements, photo records, and line items with
                  their prices already copied in
  photos/         job photos, copied in by add-photo
  quote.html      the formatted quote (after render)
  quote.txt       the plain-text quote (after render)
```

### Command cheat sheet

| Command | What it does |
|---|---|
| `init <job-dir> --title ... --customer ...` | Create a job folder. Optional: `--contact`, `--business`, `--tax-rate`, `--currency`, `--pricebook`. |
| `add-photo <job-dir> <photo>...` | Copy photo(s) into the job and record them. |
| `photos <job-dir>` | List the photos recorded for the job. |
| `note <job-dir> --text ... [--measurement k=v ...]` | Add a note and/or measurements. |
| `add-item <job-dir> --sku SKU --qty N` | Add a line priced from the job's price book. |
| `add-item <job-dir> --name ... --price N --qty N` | Add a one-off line with a price you type. |
| `items <job-dir>` | List lines with totals. The numbers shown are the indexes `remove-item` uses. |
| `remove-item <job-dir> <index>` | Remove the line at that 1-based index. |
| `show <job-dir>` | One-screen summary: counts, price book, totals. |
| `check <job-dir>` | Pre-send audit: photo integrity, item validity, price book drift. |
| `render <job-dir> [--out <dir>]` | Write `quote.html` and `quote.txt`. |
| `pricebook init <path> [--sample]` | Create a price book file. |
| `pricebook add <path> --sku ... --name ... --unit ... --price ...` | Add one item to a book (`--replace` overwrites the same SKU). |
| `pricebook list <path>` | List a book's items and prices. |
| `pricebook validate <path>` | Check a book and name every problem found. |

## Checking a job before you send the quote

`quoteshot check <job-dir>` is a read-only pre-send audit. It changes
nothing and exits 0 only when the job is clean:

- Every recorded photo is still in the job folder, with the size and
  sha256 recorded when it was added. A missing, replaced, or corrupted
  photo is named as a problem.
- Every line item quantity and price, and the job tax rate, are valid
  finite numbers (a bad hand edit to `job.json` is reported by item
  and field).
- Each price book item's snapshot is compared with the current price
  book. A price that moved, a renamed or re-taxed item, or a SKU that
  is gone is reported as drift. Drift never changes the quote, the
  snapshot still governs; the check just says the book changed, so
  you can decide whether to re-quote before sending.

If the price book was moved or deleted, the check says so and still
finishes: the quote stands on its own snapshots, as it does when
rendered.

## Your price book

A price book is one JSON file you own: a small header plus a list of
items. You can build it with the `pricebook` commands (below), or
write it in a text editor. Prices are written as decimal text in
quotes, exactly as you type them. They are never JSON numbers, so no
binary float ever touches a price.

```json
{
  "version": 1,
  "currency": "USD",
  "sample": false,
  "items": [
    {"sku": "LABOUR-HR", "name": "Labour", "description": "Per hour",
     "unit": "hour", "unit_price": "85.00", "taxable": true}
  ]
}
```

Top-level fields:

| Field | Meaning |
|---|---|
| `version` | Must be `1`. |
| `currency` | Currency code for the book, e.g. `"USD"`. When a job is created with this book, the book's currency becomes the job's currency. |
| `sample` | `true` only for a labelled sample book. Any quote from a sample book carries a SAMPLE PRICES banner (see below). Your real book should say `false`. |
| `items` | The list of priced items. It may be empty while you are building the book. |

Each entry in `items`:

| Field | Meaning | Example |
|---|---|---|
| `sku` | Your short code for the item, used with `add-item --sku`. Must be unique in the book and match exactly, including capitals. | `"LABOUR-HR"` |
| `name` | The name printed on the quote. | `"Labour"` |
| `description` | Optional detail printed under the name on the quote. May be empty (`""`). | `"Per hour"` |
| `unit` | What one unit of the price buys. The quantity on a line is counted in this unit. | `"hour"`, `"each"`, `"ft"` |
| `unit_price` | Price per unit, as decimal text in quotes. Must be zero or more. | `"85.00"` |
| `taxable` | `true` if tax is charged on this item, `false` if not. If omitted, the item counts as taxable. | `true` |

Common price book mistakes:

- `"unit_price": 85.00` without quotes. Write `"85.00"`. Prices are
  decimal text so they are recorded exactly as typed.
- Two items with the same `sku`. `pricebook validate` reports it, and
  `pricebook add` refuses a duplicate unless you pass `--replace`.
- A made-up price left in a real book. QuoteShot uses the book as
  written; it cannot tell a placeholder from a real price unless the
  book is marked `"sample": true`.

Manage a book with the commands instead of editing JSON, if you
prefer:

```bash
quoteshot pricebook init my-prices.json
quoteshot pricebook add my-prices.json --sku LABOUR-HR --name Labour --unit hour --price 85.00
quoteshot pricebook add my-prices.json --sku HAUL-AWAY --name "Haul away" --unit each --price 25.00 --no-tax
quoteshot pricebook list my-prices.json
quoteshot pricebook validate my-prices.json
```

Two things worth knowing before you rely on a book:

- **Prices are snapshots.** When you add an item to a job by SKU, its
  name, description, unit, price, and taxable flag are copied into
  the job at that moment. Editing your price book later does **not**
  change a job you already quoted.
- **The sample flag is a snapshot too.** The job also records at
  creation whether its price book was a sample book, and a finished
  quote still renders if the price book file is later moved or
  deleted, because everything on the quote comes from the job's own
  records.

## Sample prices are labelled sample

The price book in `examples/pricebook.sample.json` has `"sample": true`
and SAMPLE in every item description. Its prices are made-up
placeholders to show the arithmetic. They are not market prices, not
any real business's prices, and not an offer to do work.

Any quote rendered from a sample price book carries a visible
**SAMPLE PRICES** banner in both the HTML and the text version.

## Photos: the workflow in detail

1. Take the photos with your usual camera app. QuoteShot starts from
   files; it does not take photos itself.
2. Copy the files to the computer and run
   `quoteshot add-photo <job-dir> <photo>...` once per photo, or once
   with several files named.
3. Run `quoteshot photos <job-dir>` to check what was recorded.

What happens at step 2:

- Supported files are JPEG, PNG, and GIF. Anything else is rejected
  by name and is not recorded, instead of being silently stored.
- The file is copied byte for byte into the job's `photos/` folder.
  It is never edited, resized, or re-encoded. If a file with that
  name is already in the job, the new copy is stored as `name-2`,
  `name-3`, and so on, never as a silent overwrite.
- QuoteShot records the file name, size, a SHA-256 hash, the format,
  the pixel dimensions, and, when the file already carries them,
  camera details from the file itself (capture time, camera make and
  model). A photo with no camera details is still recorded, with
  those fields empty.
- That record is all QuoteShot takes from a photo. See
  [Photos, privacy, and what a quote shows](#photos-privacy-and-what-a-quote-shows)
  for what does and does not reach the customer.

## Reading the rendered quote

`render` writes two files with the same content and the same totals:
`quote.html` (formatted, with the photos shown on the page) and
`quote.txt` (plain text, photos listed by file name). You send
whichever file suits the customer, yourself, however you normally
send files. QuoteShot sends nothing.

A text quote looks like this (a job using the sample job's prices
from `examples/`, with plainer item names):

```text
Sample Business
===============

Quote: Kitchen faucet replacement
Date: 2026-10-14
Customer: Sample Customer

Notes:
  - Shut-off valve corroded

Measurements:
  - length_ft: 24

Items:
  1. Service call: 1 each x $75.00 = $75.00
  2. Labour - Per hour: 2 hour x $85.00 = $170.00
  3. Kitchen faucet, supply only: 1 each x $129.99 = $129.99

Subtotal: $374.99
Tax (8.25% on $374.99): $30.94
Total: $405.93

Photos:
  - before.png (1x1)

Prices are from the business's local price book as recorded in this quote. Photos are listed by filename only; they were not analysed. No AI or external service was used to produce this quote.
```

How to read it, section by section:

- **Header.** Business name (or "Quote" if none was set), the job
  title after `Quote:`, the date the job was created, and the
  customer (plus contact, if one was given).
- **SAMPLE banner.** If the job's price book was a sample book, a
  `*** SAMPLE PRICES ***` line appears right under the header here,
  and a highlighted banner appears in the HTML version. No banner
  means the prices came from a book that was not marked sample.
- **Notes and Measurements.** Exactly what you typed with `note`,
  in the order recorded. If there are none, the section is omitted.
- **Items.** One numbered line per item, in the order added:
  `number. name - description: quantity unit x unit price = line total`.
  A line with no tax charged ends with `(not taxable)`. In the HTML
  version the same lines are a table with Qty, Unit price, and Line
  total columns.
- **Subtotal, Tax, Total.** Subtotal is every line total added up.
  The Tax line names the rate as a percent and, after `on`, the
  amount the tax was actually charged on: the taxable lines only.
  If some lines are non-taxable, that amount is smaller than the
  subtotal, and that is correct (see
  [How the numbers work](#how-the-numbers-work)). Total is subtotal
  plus tax, and it is the number the customer is being quoted.
- **Photos.** Every recorded photo listed by file name, with its
  dimensions and capture time when known. No GPS coordinates are
  ever printed (see below).
- **Footer.** The same statement on every quote: prices came from
  the business's local price book as recorded in the quote, photos
  were listed and not analysed, and no AI or external service was
  used.

Before sending: check every line, quantity, and the tax rate against
your own notes. The totals are arithmetic on what was entered; they
cannot catch a wrong price or a missed item. See
[Your responsibility](#your-responsibility).

## How the numbers work

- Line total = quantity x unit price.
- Subtotal = all line totals added up.
- Tax = taxable line totals only, x the job's tax rate.
- Total = subtotal + tax.

Money is decimal arithmetic, rounded half up to cents. Quantities may
be fractional (for example `2.5` hours). The tax rate is one rate per
job, supplied by you as a decimal fraction (`0.0825` for 8.25%).
QuoteShot ships no tax table and gives no tax advice.

A job with no line items yet is valid. Its subtotal, tax, and total
are all 0.00, and the quote says it has no line items instead of
inventing any.

## Photos, privacy, and what a quote shows

- Photos are copied byte for byte, never edited or re-encoded.
- If a photo file already carries camera details (capture time, camera
  model, size), QuoteShot records them in the job's own record.
- A customer quote lists photos by file name only. It does **not**
  print GPS coordinates, even if a photo file contains them.
- A file that is not a recognised image is rejected by name, not
  silently stored. A photo with no camera details is still recorded,
  with those fields empty.

## Troubleshooting

| What you see | What it means, and the fix |
|---|---|
| `no job at ... (missing job.json)` | The folder is not a job folder, or the path is wrong. Run `init` first, or check the `<job-dir>` argument. |
| `job.json already exists; refusing to overwrite` | That folder is already a job. Use it, or pick a new folder name for a new job. |
| `this job has no price book` on `add-item --sku` | The job was created without `--pricebook`. Add the line as an ad-hoc item (`--name` + `--price`), or start the job again with `--pricebook`. |
| `SKU ... not in price book ...; known SKUs: ...` | The SKU is mistyped or not in the book yet. The error lists the SKUs that exist; add the item with `pricebook add` or fix the spelling, capitals included. |
| `ad-hoc item ...: --price is required` | `--name` without `--price`. Type the price: QuoteShot never invents one. |
| `not a recognised image` on `add-photo` | The file is not JPEG, PNG, or GIF (a screenshot saved as another format, or the wrong file). Export or pick the image file itself. |
| A SAMPLE PRICES banner, or a sample warning at render | The job was created from a book with `"sample": true`. The numbers are placeholders. Create the job again from your real price book before sending anything. |
| Tax looks too big by about 100x | The rate was typed as a percent. Use the decimal fraction: `0.0825`, not `8.25`, when you create the job. To fix it, start the job again with the right `--tax-rate`. |
| Totals are 0.00 and the quote says no line items | No items have been added yet. That is a valid empty quote, not an error. Add lines with `add-item`, then render again. |

More detail on any failure: errors name the file and the field at
fault, and [exit codes](#exit-codes) tell scripts how the run ended.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Done. |
| `1` | User error: bad input, an unknown SKU, a missing price, an invalid price book item. Fix the input and run again. |
| `2` | Could not proceed: no job there, an unreadable or corrupt job or price book file, or no command given (help is printed instead). |

For `check` specifically, exit `1` means problems or price book drift
were found; the quote itself is unchanged either way.

## What QuoteShot does not do

- No image AI, vision model, OCR, or measurement from photos.
- No network, accounts, cloud sync, telemetry, or sending the quote.
  You send the rendered file yourself, however you normally would.
- No invoicing, payments, deposits, signatures, or acceptance tracking.
- No tax engine or jurisdiction lookup.
- No scheduling, CRM, or customer database.
- No phone app or dashboard in this version. Your phone's camera app
  takes the photos; QuoteShot starts from files.

## Your responsibility

A clean quote can make a guessed price look official. Check every
line item, quantity, and the tax rate before you send a quote. The
quote shows the price book prices and the rate used, so you can
stand behind every number on it.
