"""QuoteShot - offline photo-to-quote workflow for trades.

v0.1: a job folder holds photos (filenames + EXIF basics recorded with
stdlib parsing only, no image AI), human-entered notes / measurements /
line items, prices from a local user-supplied price book JSON, and a
rendered customer quote (HTML + plain text).

No external AI or API. No network. Prices are never invented: they come
from the user's price book, or from an ad-hoc price the human typed.

Typical use is through the CLI (``quoteshot`` or
``python3 -m quoteshot``; see :mod:`quoteshot.cli`). The submodules are
the building blocks behind it:

- :mod:`quoteshot.job` - the job folder and its totals
- :mod:`quoteshot.pricebook` - the user's price book JSON
- :mod:`quoteshot.photos` - photo records (headers only, no analysis)
- :mod:`quoteshot.money` - Decimal money arithmetic
- :mod:`quoteshot.render` - quote.html / quote.txt rendering
"""
__version__ = "0.1.0"
__all__ = ["__version__"]
