"""Money arithmetic: Decimal end to end, ROUND_HALF_UP to cents.

Prices and quantities are stored in JSON as strings so no binary float
ever touches a price. Parsing a non-decimal value is an error, not a
silent coercion.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

CENTS = Decimal("0.01")


class QuoteShotError(Exception):
    """User-facing error. CLI maps it to exit code 1 (bad input) or,
    when ``fatal`` is set, exit code 2 (could not proceed)."""

    def __init__(self, message: str, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal


def parse_decimal(value, field: str) -> Decimal:
    """Parse a decimal from a string/int/Decimal, naming the field on error."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        raise QuoteShotError(f"{field}: not a number: {value!r}")
    if isinstance(value, float):
        # Floats arrive only from hand-edited JSON numbers; go through str
        # so 0.1 means 0.1, and say so nowhere - it still parses exactly
        # as written in the file.
        value = str(value)
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise QuoteShotError(f"{field}: not a valid decimal: {value!r}") from None
    if not parsed.is_finite():
        # Decimal happily parses "NaN" / "Infinity": NaN then poisons
        # every total downstream and Infinity crashes quantize. A price,
        # quantity, or tax rate is never legitimately non-finite, so the
        # field is rejected here, at the single parse gate (polish A1).
        raise QuoteShotError(f"{field}: not a finite number: {value!r}")
    return parsed


def _wide_prec(*values: Decimal) -> int:
    """Context precision that cannot round or overflow for these values.

    The default context (28 significant digits) makes quantize() raise
    InvalidOperation on large-but-legitimate amounts (a 1e30 price
    crashed totals before the polish, A2) and makes multiplication of
    two long decimals silently round. Size the context from the
    operands instead: digits + integer magnitude + slack, per operand.
    """
    prec = 50
    for v in values:
        if isinstance(v, Decimal) and v.is_finite() and v:
            prec += len(v.as_tuple().digits) + max(v.adjusted(), 0) + 4
    return prec


def money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise QuoteShotError(f"amount: not a finite number: {value!r}")
    with localcontext() as ctx:
        ctx.prec = _wide_prec(value)
        return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def fmt_money(value: Decimal, currency: str = "USD") -> str:
    """Human format: $1,234.56 for USD, otherwise '1,234.56 CUR'."""
    q = money(value)
    sign = "-" if q < 0 else ""
    q = abs(q)
    body = f"{q:,.2f}"
    if currency.upper() == "USD":
        return f"{sign}${body}"
    return f"{sign}{body} {currency.upper()}"


def dec_str(value: Decimal) -> str:
    """Stable string for JSON storage (no exponent notation for money/qty).

    Built from the exact ``format(..., "f")`` rendering with trailing
    zeros trimmed by hand: ``normalize()`` / ``quantize()`` here would
    apply the ambient context precision and silently round (or raise
    on) values with more than 28 significant digits (polish A2).
    """
    if not isinstance(value, Decimal) or not value.is_finite():
        raise QuoteShotError(f"amount: not a finite number: {value!r}")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text
