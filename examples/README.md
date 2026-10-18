# QuoteShot examples

All prices in these examples are **SAMPLE prices**. They are made-up
numbers to show the arithmetic. They are not real prices, not a real
quote, and not an offer to do work.

New to QuoteShot? Start with the main `README.md` (one folder up) for
the workflow, then use this page to check the example files and the
arithmetic by hand. Commands below are written as `quoteshot ...`;
without an install, run them from the repository root as
`PYTHONPATH=src python3 -m quoteshot ...`.

## Run the sample yourself

The fastest way to see a finished quote is to render a copy of the
sample job. Copy the whole `examples/` folder, not just `sample-job/`:
the sample job refers to its price book as `../pricebook.sample.json`,
so the two need to stay side by side, and you need to run the render
from inside the copied job folder for that relative path to resolve.
Work on a copy so the shipped example stays unchanged:

```bash
cp -r examples /tmp/quoteshot-examples
cd /tmp/quoteshot-examples/sample-job
quoteshot render .
# Then open quote.html or read quote.txt in that folder.
cd -   # back to where you were
```

Skip the copy and the banner disappears: with no price book found at
the recorded path, a job written in this older format renders without
the SAMPLE banner (the totals are unaffected). That is exactly why
the copy keeps the book next to the job.

What to look for in the output:

- A SAMPLE PRICES banner, because the sample job's price book has
  `"sample": true`.
- Subtotal $374.99, tax $30.94, total $405.93. The breakdown is
  checked line by line in
  [Sample job arithmetic](#sample-job-arithmetic-check-it-by-hand)
  below.
- The photo `before.png` listed by file name, with no GPS or other
  location information anywhere in the quote.

To build a job like this one from scratch (init, add-photo, note,
add-item, render), follow "Try it in two minutes" in the main README.

## What is in this folder

| File | What it is |
|---|---|
| `pricebook.sample.json` | A local price book in QuoteShot format (version 1): `sku`, `name`, `description`, `unit`, `unit_price` as decimal text, and `taxable` per item, plus `"sample": true`. Copy it and put your own real prices in your own copy. The main README explains every field. |
| `sample-job/job.json` | A sample job file in the exact shape `quoteshot init` writes: customer, business, tax rate as text, notes, measurements, photo records, and line items with prices snapshotted from the price book. |
| `sample-job/photos/before.png` | A real 1x1 PNG standing in for a job photo, so the sample ships no one's real pictures. Its record in `job.json` (size, sha256, 1x1, no EXIF) is what the tool itself records for it. |
| `empty-job/job.json` | A valid job with no line items yet. Its totals are all 0.00, and rendering it produces a quote that says it has no line items instead of inventing any. Try: copy it to a scratch folder and run `quoteshot render` on that folder. |

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

Reading the rendered tax line: it will say
`Tax (8.25% on $374.99): $30.94`. The amount after `on` is the
taxable part of the subtotal, the amount the rate was charged on.
Here every item is taxable, so it equals the subtotal.

## Golden mixed-tax job (used by the tests, built in a temp folder)

This one is not a shipped folder; the tests build it to pin down how
non-taxable lines behave. It is worth reading because the tax line
looks different from the all-taxable sample above:

- 2.5 x 40.00 taxable = 100.00
- 1 x 129.99 taxable = 129.99
- 3 x 10.00 non-taxable = 30.00
- **Subtotal = 259.99**, taxable subtotal = 229.99
- Tax at 0.0825 = 18.974175, rounded half up to **18.97**
- **Total = 278.96**

Its rendered tax line says `Tax (8.25% on $229.99): $18.97`: the
amount after `on` (229.99) is smaller than the subtotal (259.99)
because the 30.00 of non-taxable lines is left out of the tax, but
still counted in the subtotal and the total.

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
