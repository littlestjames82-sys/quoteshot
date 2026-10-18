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

- Python 3.10 or newer.
- Your own price book file (see below), or the supplied sample one to
  try the tool out.

## The everyday workflow

```bash
# 1. Start a job folder
PYTHONPATH=src python3 -m quoteshot init my-job --title "Kitchen faucet" --customer "Sample Customer" --tax-rate 0.0825 --pricebook pricebook.json

# 2. Add the photos you took on the walk-through
PYTHONPATH=src python3 -m quoteshot add-photo my-job IMG_0001.jpg
PYTHONPATH=src python3 -m quoteshot photos my-job

# 3. Add your notes and measurements
PYTHONPATH=src python3 -m quoteshot note my-job --text "Shut-off valve corroded" --measurement length_ft=24

# 4. Add line items, priced from your price book by SKU,
#    or typed in for this job only
PYTHONPATH=src python3 -m quoteshot add-item my-job --sku LABOUR-HR --qty 2
PYTHONPATH=src python3 -m quoteshot add-item my-job --name "Extra fitting" --price 12.50 --qty 1
PYTHONPATH=src python3 -m quoteshot items my-job

# 5. Render the quote: writes quote.html and quote.txt
PYTHONPATH=src python3 -m quoteshot render my-job
```

A worked sample job and a sample price book are in `examples/`. See
`examples/README.md` for the hand-checked arithmetic.

## Your price book

A price book is one JSON file you own. Prices are written as decimal
text, exactly as you type them:

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

Manage it with:

```bash
PYTHONPATH=src python3 -m quoteshot pricebook init my-prices.json
PYTHONPATH=src python3 -m quoteshot pricebook add my-prices.json --sku LABOUR-HR --name Labour --unit hour --price 85.00
PYTHONPATH=src python3 -m quoteshot pricebook list my-prices.json
PYTHONPATH=src python3 -m quoteshot pricebook validate my-prices.json
```

When you add an item to a job by SKU, its price is copied into the
job at that moment. Editing your price book later does **not** change
a job you already quoted. The job also records at creation whether
its price book was a sample book, and a finished quote still renders
if the price book file is later moved or deleted, because everything
on the quote comes from the job's own records.

## Sample prices are labelled sample

The price book in `examples/pricebook.sample.json` has `"sample": true`
and SAMPLE in every item description. Its prices are made-up
placeholders to show the arithmetic. They are not market prices, not
any real business's prices, and not an offer to do work.

Any quote rendered from a sample price book carries a visible
**SAMPLE PRICES** banner in both the HTML and the text version.

## How the numbers work

- Line total = quantity x unit price.
- Subtotal = all line totals added up.
- Tax = taxable line totals only, x the job's tax rate.
- Total = subtotal + tax.

Money is decimal arithmetic, rounded half up to cents. The tax rate
is one rate per job, supplied by you. QuoteShot ships no tax table
and gives no tax advice.

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
