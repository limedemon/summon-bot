import random
from decimal import Decimal, InvalidOperation


def parse_chance(text: str) -> str | None:
    """Validates and normalizes a rarity chance string.

    Rules: > 0, < 100, at most 20 digits after the decimal point.
    Returns the canonical string form, or None if invalid.
    """
    cleaned = text.strip().replace(",", ".").rstrip("%").strip()
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if value <= 0 or value >= 100:
        return None
    exponent = value.as_tuple().exponent
    decimals = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if decimals > 20:
        return None
    return format(value, "f")


def format_chance(raw: str) -> str:
    d = Decimal(raw)
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def parse_positive_int(text: str) -> int | None:
    text = text.strip()
    if not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def weighted_pick(rows, weight_key: str):
    weights = [float(r[weight_key]) for r in rows]
    return random.choices(rows, weights=weights, k=1)[0]


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    if m:
        return f"{m} мин {s} сек"
    return f"{s} сек"
