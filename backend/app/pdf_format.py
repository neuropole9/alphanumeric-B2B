from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def compact_decimal(value) -> str:
    """Render stored decimals without meaningless trailing zeroes."""
    amount = Decimal(str(value or 0))
    if not amount:
        return "0"
    return format(amount.normalize(), "f")


def indian_number(value, places: int = 2) -> str:
    """Format a Decimal using Indian digit grouping and fixed decimal places."""
    quantum = Decimal(1).scaleb(-places)
    amount = Decimal(str(value or 0)).quantize(quantum, rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.{places}f}".split(".")
    if len(whole) > 3:
        tail = whole[-3:]
        lead = whole[:-3]
        groups: list[str] = []
        while lead:
            groups.insert(0, lead[-2:])
            lead = lead[:-2]
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}.{fraction}" if places else f"{sign}{whole}"


def inr(value) -> str:
    return f"INR {indian_number(value)}"


def percent(value) -> str:
    return f"{compact_decimal(value)}%"
