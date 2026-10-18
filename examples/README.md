# QuoteShot examples

All prices in these examples are **SAMPLE prices**. They are made-up
numbers to show the arithmetic. They are not real prices, not a real
quote, and not an offer to do work.

| File | What it is |
|---|---|
| `pricebook.sample.json` | A local price book in QuoteShot format (version 1): `sku`, `name`, `description`, `unit`, `unit_price` as decimal text, and `taxable` per item, plus `"sample": true`. Copy it and put your own real prices in your own copy. |
| `sample-job/job.json` | A sample job file in the exact shape `quoteshot init` writes: customer, business, tax rate as text, notes, measurements, photo records, and line items with prices snapshotted from the price book. |
| `sample-job/photos/before.png` | A real 1x1 PNG standing in for a job photo, so the sample ships no one's real pictures. Its record in `job.json` (size, sha256, 1x1, no EXIF) is what the tool itself records for it. |
| `empty-job/job.json` | A valid job with no line items yet. Its totals are all 0.00. |

## Sample job arithmetic (check it by hand)

From `sample-job/job.json` (every item is taxable):

- 1 x service call at 75.00 = 75.00
- 2 x labour at 85.00 = 170.00
- 1 x faucet (supply) at 129.99 = 129.99
- **Subtotal = 374.99**
- Tax at 8.25% (0.0825) = 374.99 x 0.0825 = 30.936675, rounded half up to **30.94**
- **Total = 374.99 + 30.94 = 405.93**

Those three numbers are also stored in the sample job's `expected`
block, and the test suite checks the example files, the core totals
function, and the rendered quote against them.

## Golden mixed-tax job (used by the tests, built in a temp folder)

- 2.5 x 40.00 taxable = 100.00
- 1 x 129.99 taxable = 129.99
- 3 x 10.00 non-taxable = 30.00
- **Subtotal = 259.99**, taxable subtotal = 229.99
- Tax at 0.0825 = 18.974175, rounded half up to **18.97**
- **Total = 278.96**

## How a job folder is shaped

```text
my-job/
  job.json        the job record: customer, notes, measurements,
                  photo records, and human-entered line items
  photos/         job photos, copied in by `quoteshot add-photo`
  quote.html      rendered quote (after `quoteshot render`)
  quote.txt       plain-text quote (after `quoteshot render`)
```

QuoteShot never analyses a photo, never uploads a photo, and never
guesses a line item or a price from a photo. A person enters every
line item and every price.
