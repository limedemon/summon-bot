import html
import random
from decimal import Decimal, InvalidOperation

# ---------- visual language ----------
# A single thin divider used across every screen so the bot feels like one product.
DIV = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

# From the most common rarity to the rarest one. Rarities are created by admins with
# arbitrary names, so the colour is derived from the rarity's rank among all existing
# rarities (sorted by chance), never from a hardcoded name.
RARITY_PALETTE = ("⚪", "🟢", "🔵", "🟣", "🟠", "🔴")


def esc(value) -> str:
    """Escapes admin/user supplied text before putting it into HTML markup."""
    return html.escape(str(value if value is not None else ""), quote=False)


def rarity_badges(rarities) -> dict[str, str]:
    """Maps every distinct rarity chance to a colour emoji by its rank.

    `rarities` is the output of db.list_rarities_sorted() (chance descending).
    The most common chance gets the first palette colour, the rarest the last one.
    """
    chances = sorted({float(r["chance"]) for r in rarities}, reverse=True)
    last = len(RARITY_PALETTE) - 1
    if not chances:
        return {}
    if len(chances) == 1:
        return {format(chances[0], "f"): RARITY_PALETTE[0]}
    return {
        format(c, "f"): RARITY_PALETTE[round(i * last / (len(chances) - 1))]
        for i, c in enumerate(chances)
    }


def rarity_badge(chance, badges: dict[str, str]) -> str:
    """Colour emoji for one rarity chance; falls back to a neutral dot."""
    try:
        return badges.get(format(float(chance), "f"), "⚪")
    except (TypeError, ValueError):
        return "⚪"


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Picks the Russian plural form for n (1 карточка / 2 карточки / 5 карточек)."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def exp_word(n: int) -> str:
    return plural_ru(n, "опыт", "опыта", "опыта")


def cards_word(n: int) -> str:
    return plural_ru(n, "карточка", "карточки", "карточек")


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
