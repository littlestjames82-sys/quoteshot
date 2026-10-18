"""QuoteShot - offline photo-to-quote workflow for trades.

v0.1: a job folder holds photos (filenames + EXIF basics recorded with
stdlib parsing only, no image AI), human-entered notes / measurements /
line items, prices from a local user-supplied price book JSON, and a
rendered customer quote (HTML + plain text).

No external AI or API. No network. Prices are never invented: they come
from the user's price book, or from an ad-hoc price the human typed.
"""
__version__ = "0.1.0"
__all__ = ["__version__"]
