# -*- coding: utf-8 -*-
"""Pillow-based visuals: the card index grid and the profile screen.

Both are rendered as a single PNG and sent as a photo — Telegram has no way
to lay out a grid of thumbnails plus progress bars in one text message, so
the bot draws the whole screen itself.
"""

import hashlib
import io
import os

from PIL import Image, ImageDraw, ImageFont

from config import INDEX_COLS, INDEX_ROWS, THUMB_CACHE_DIR
from utils import format_chance

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(PROJECT_DIR, "assets", "fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


F_TITLE = _font("DejaVuSans-Bold.ttf", 36)
F_SUB = _font("DejaVuSans.ttf", 22)
F_CARD_NAME = _font("DejaVuSans-Bold.ttf", 18)
F_CARD_SUB = _font("DejaVuSans.ttf", 15)
F_QMARK = _font("DejaVuSans-Bold.ttf", 50)
F_BADGE = _font("DejaVuSans-Bold.ttf", 22)
F_NICK = _font("DejaVuSans-Bold.ttf", 32)
F_BAR_LABEL = _font("DejaVuSans-Bold.ttf", 19)
F_BAR_NUM = _font("DejaVuSans-Bold.ttf", 17)
F_SMALL = _font("DejaVuSans.ttf", 15)

# ---------- palette ----------
BG_TOP = (20, 22, 34)
BG_BOTTOM = (13, 14, 22)
PANEL = (28, 30, 46)
PANEL_BORDER = (46, 49, 74)
WHITE = (240, 241, 248)
DIM = (150, 154, 178)
GOLD = (247, 197, 88)

# A small fixed palette cycled by chance rank, so rarer tiers read as more
# vivid/warm regardless of what an admin actually names a rarity.
_RARITY_PALETTE = [
    ((90, 110, 150), (60, 75, 110), (150, 175, 220)),    # common-ish (lowest chance rank last)
    ((70, 170, 120), (45, 120, 90), (110, 220, 160)),
    ((150, 90, 210), (100, 55, 160), (195, 140, 250)),
    ((240, 175, 60), (190, 120, 30), (255, 205, 100)),
]


def _chance_rank(chance_pct: float) -> int:
    """Maps a drop chance to a fixed rarity tier, independent of what else is on screen."""
    if chance_pct < 2:
        return 3  # legendary-ish
    if chance_pct < 10:
        return 2  # epic-ish
    if chance_pct < 30:
        return 1  # rare-ish
    return 0  # common-ish


def _rarity_style(chance_rank: int):
    top, bottom, text = _RARITY_PALETTE[min(chance_rank, len(_RARITY_PALETTE) - 1)]
    return (top, bottom), text


# ---------- low-level drawing ----------

def _vgrad(w, h, top, bottom):
    img = Image.new("RGB", (max(1, w), max(1, h)), top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    return img


def _rrect(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def _text_center(draw, xy, text, fnt, fill):
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=fnt)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - w / 2, y - h / 2 - bbox[1]), text, font=fnt, fill=fill)


def _fit_text(draw, text, fnt, max_width):
    """Truncates with an ellipsis so a long unit/card name never bleeds into
    the neighbouring tile's caption."""
    if draw.textlength(text, font=fnt) <= max_width:
        return text
    ellipsis = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textlength(text[:mid] + ellipsis, font=fnt) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ellipsis if lo > 0 else ellipsis


# ---------- small vector icons (no emoji font dependency) ----------

def _icon_folder(size, color=GOLD):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, size * 0.28, size, size * 0.9), radius=size * 0.08, fill=color)
    d.polygon([(0, size * 0.28), (size * 0.4, size * 0.28), (size * 0.5, size * 0.14),
               (0, size * 0.14)], fill=color)
    return img


def _icon_sparkle(size, color=(120, 220, 150)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    d.polygon([(c, 0), (c * 1.22, c * 0.78), (size, c), (c * 1.22, c * 1.22),
               (c, size), (c * 0.78, c * 1.22), (0, c), (c * 0.78, c * 0.78)], fill=color)
    return img


def _icon_card(size, color=(140, 165, 240)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((size * 0.08, size * 0.05, size * 0.75, size * 0.75),
                         radius=size * 0.1, fill=(0, 0, 0, 60))
    d.rounded_rectangle((size * 0.25, size * 0.25, size * 0.92, size * 0.95),
                         radius=size * 0.1, fill=color)
    return img


def _icon_gem(size, color=GOLD):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(size * 0.5, 0), (size, size * 0.38), (size * 0.5, size), (0, size * 0.38)], fill=color)
    return img


def _icon_text_left(draw, base_img, xy, icon_img, text, text_font, fill, gap=8):
    x, y = xy
    isz = icon_img.size[1]
    base_img.paste(icon_img, (int(x), int(y - isz / 2)), icon_img)
    tb = draw.textbbox((0, 0), text, font=text_font)
    th = tb[3] - tb[1]
    draw.text((x + isz + gap - tb[0], y - th / 2 - tb[1]), text, font=text_font, fill=fill)


# ---------- thumbnail cache ----------

_THUMB_DIR = os.path.join(PROJECT_DIR, THUMB_CACHE_DIR)


def _thumb_cache_path(file_id: str) -> str:
    key = hashlib.sha1(file_id.encode("utf-8")).hexdigest()[:20]
    return os.path.join(_THUMB_DIR, f"{key}.png")


async def _load_unit_photo(bot, file_id: str) -> Image.Image:
    """Downloads a card's Telegram photo once, then reuses the cached PNG on disk."""
    path = _thumb_cache_path(file_id)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")

    os.makedirs(_THUMB_DIR, exist_ok=True)
    buf = await bot.download(file_id)
    img = Image.open(buf).convert("RGBA")
    img.thumbnail((256, 256), Image.LANCZOS)
    img.save(path, format="PNG")
    return img


# ---------- card tile ----------

def _card_tile(size, unlocked, unit_photo, chance_rank):
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    if not unlocked:
        _rrect(d, (0, 0, size - 1, size - 1), 16, fill=(14, 15, 22), outline=(38, 40, 56), width=2)
        _text_center(d, (size / 2, size / 2 - 4), "?", F_QMARK, (70, 73, 92))
        return tile

    (top, bottom), _ = _rarity_style(chance_rank)
    backdrop = _vgrad(size, size, top, bottom)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=16, fill=255)
    tile.paste(backdrop, (0, 0), mask)

    if unit_photo is not None:
        pad = 12
        box = size - pad * 2
        fitted = unit_photo.copy()
        fitted.thumbnail((box, box), Image.LANCZOS)
        px = (size - fitted.width) // 2
        py = (size - fitted.height) // 2 - 2
        tile.paste(fitted, (px, py), fitted)

    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=16, outline=(0, 0, 0, 90), width=2)
    return tile


# ---------- index screen ----------

async def render_index_image(
    bot,
    cards: list,
    owned_ids: set,
    scope_label: str,
    page: int,
    total_pages: int,
    unlocked_count: int,
    total_count: int,
) -> bytes:
    cols, rows = INDEX_COLS, INDEX_ROWS
    tile_size = 118
    gap = 14
    cap_h = 46
    margin = 34
    header_h = 130
    footer_h = 40

    grid_w = cols * tile_size + (cols - 1) * gap
    grid_h = rows * (tile_size + cap_h) + (rows - 1) * gap
    W = grid_w + margin * 2
    H = header_h + grid_h + footer_h + margin * 2

    img = _vgrad(W, H, BG_TOP, BG_BOTTOM)
    d = ImageDraw.Draw(img, "RGBA")

    icon = _icon_folder(34)
    ib = d.textbbox((0, 0), "ИНДЕКС", font=F_TITLE)
    title_w = icon.width + 12 + (ib[2] - ib[0])
    tx0 = W / 2 - title_w / 2
    img.paste(icon, (int(tx0), int(46 - icon.height / 2)), icon)
    d.text((tx0 + icon.width + 12, 46 - (ib[3] - ib[1]) / 2 - ib[1]), "ИНДЕКС", font=F_TITLE, fill=WHITE)

    _text_center(d, (W / 2, 84), _fit_text(d, scope_label, F_SUB, W - margin * 2), F_SUB, DIM)

    bar_w = 260
    bx0 = W / 2 - bar_w / 2
    by0 = 100
    frac = (unlocked_count / total_count) if total_count else 0
    _rrect(d, (bx0, by0, bx0 + bar_w, by0 + 10), 5, fill=PANEL, outline=PANEL_BORDER, width=1)
    if frac > 0:
        _rrect(d, (bx0, by0, bx0 + bar_w * frac, by0 + 10), 5, fill=GOLD)
    _text_center(d, (W / 2, by0 + 26), f"{unlocked_count}/{total_count} карточек открыто", F_SMALL, DIM)

    y = header_h + margin
    idx = 0
    for r in range(rows):
        x = margin
        for c in range(cols):
            if idx >= len(cards):
                break
            card = cards[idx]
            unlocked = card["id"] in owned_ids
            unit_photo = await _load_unit_photo(bot, card["photo_file_id"]) if unlocked else None
            rank = _chance_rank(float(card["rarity_chance"]))
            tile = _card_tile(tile_size, unlocked, unit_photo, rank)
            img.paste(tile, (x, y), tile)

            if unlocked:
                _, text_color = _rarity_style(rank)
                shown_name = _fit_text(d, card["name"], F_CARD_NAME, tile_size - 6)
                _text_center(d, (x + tile_size / 2, y + tile_size + 16), shown_name, F_CARD_NAME, WHITE)
                _text_center(d, (x + tile_size / 2, y + tile_size + 34),
                             f"{format_chance(card['rarity_chance'])}%", F_CARD_SUB, text_color)
            else:
                _text_center(d, (x + tile_size / 2, y + tile_size + 16), "?????", F_CARD_NAME, (90, 93, 112))
                _text_center(d, (x + tile_size / 2, y + tile_size + 34), "— %", F_CARD_SUB, (70, 73, 92))

            x += tile_size + gap
            idx += 1
        y += tile_size + cap_h + gap

    _text_center(d, (W / 2, H - margin / 2 - 4), f"стр. {page + 1}/{total_pages}", F_SMALL, (90, 93, 112))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=92)
    out.seek(0)
    return out


def _health_bar(draw, base_img, box, frac, label, value_text, fill_top, fill_bottom, icon_img):
    x0, y0, x1, y1 = box
    h = y1 - y0
    _rrect(draw, box, h / 2, fill=(18, 19, 30), outline=PANEL_BORDER, width=2)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        inner = (x0 + 3, y0 + 3, x0 + 3 + (x1 - x0 - 6) * frac, y1 - 3)
        grad = _vgrad(int(inner[2] - inner[0]) or 1, int(inner[3] - inner[1]), fill_top, fill_bottom)
        mask = Image.new("L", grad.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, grad.size[0] - 1, grad.size[1] - 1),
                                                 radius=(inner[3] - inner[1]) / 2, fill=255)
        base_img.paste(grad, (int(inner[0]), int(inner[1])), mask)
    _icon_text_left(draw, base_img, (x0 + 2, y0 - 20), icon_img, label, F_BAR_LABEL, WHITE)
    tb = draw.textbbox((0, 0), value_text, font=F_BAR_NUM)
    draw.text((x1 - (tb[2] - tb[0]) - 10, y0 + h / 2 - (tb[3] - tb[1]) / 2 - tb[1]),
              value_text, font=F_BAR_NUM, fill=WHITE)


async def render_profile_image(
    bot,
    avatar_file_id: str | None,
    nickname: str,
    level: int,
    max_level: int,
    exp_into: int,
    exp_needed: int | None,
    got_cards: int,
    total_cards: int,
    best_card: dict | None,
) -> bytes:
    W, H = 760, 540 if best_card else 380
    img = _vgrad(W, H, BG_TOP, BG_BOTTOM)
    d = ImageDraw.Draw(img, "RGBA")

    av_size = 132
    av_x, av_y = 44, 44
    av = Image.new("RGBA", (av_size, av_size), (0, 0, 0, 0))
    if avatar_file_id:
        photo = await _load_unit_photo(bot, avatar_file_id)
        fitted = photo.copy()
        fitted = fitted.resize((av_size, av_size), Image.LANCZOS) if fitted.size != (av_size, av_size) else fitted
        av.paste(fitted, (0, 0), fitted)
    else:
        ad = ImageDraw.Draw(av)
        ad.ellipse((0, 0, av_size, av_size), fill=(70, 90, 150))
        ad.ellipse((av_size * 0.30, av_size * 0.20, av_size * 0.70, av_size * 0.58), fill=(150, 168, 210))
        ad.pieslice((av_size * 0.12, av_size * 0.55, av_size * 0.88, av_size * 1.25), 180, 360, fill=(150, 168, 210))
    mask = Image.new("L", (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
    img.paste(av, (av_x, av_y), mask)
    d.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), outline=GOLD, width=4)

    badge_r = 26
    bx, by = av_x + av_size - 6, av_y + av_size - 6
    d.ellipse((bx - badge_r, by - badge_r, bx + badge_r, by + badge_r), fill=GOLD, outline=(20, 22, 34), width=4)
    _text_center(d, (bx, by), str(level), F_BADGE, (30, 22, 8))

    name_x = av_x + av_size + 28
    shown_nick = _fit_text(d, nickname, F_NICK, W - name_x - 20)
    d.text((name_x, 56), shown_nick, font=F_NICK, fill=WHITE)
    d.text((name_x, 100), f"Уровень {level} из {max_level}", font=F_SUB, fill=DIM)

    bar_x0, bar_x1 = 44, W - 44
    maxed = exp_needed is None
    exp_frac = 1.0 if maxed else (exp_into / exp_needed if exp_needed else 0)
    exp_value_text = "MAX" if maxed else f"{exp_into}/{exp_needed}"
    _health_bar(d, img, (bar_x0, 210, bar_x1, 246), exp_frac, "Опыт", exp_value_text,
                (110, 210, 130), (55, 150, 90), _icon_sparkle(20))

    coll_frac = (got_cards / total_cards) if total_cards else 0
    _health_bar(d, img, (bar_x0, 300, bar_x1, 336), coll_frac, "Карточки", f"{got_cards}/{total_cards}",
                (120, 150, 240), (70, 90, 190), _icon_card(20))

    hint_y = 366
    if maxed:
        d.text((bar_x0, hint_y), "Максимальный уровень достигнут", font=F_SMALL, fill=DIM)
    else:
        d.text((bar_x0, hint_y), f"До {level + 1} уровня: ещё {exp_needed - exp_into} опыта", font=F_SMALL, fill=DIM)

    if best_card:
        panel_box = (bar_x0, 410, bar_x1, 500)
        _rrect(d, panel_box, 18, fill=PANEL, outline=PANEL_BORDER, width=1)
        _icon_text_left(d, img, (bar_x0 + 20, 430), _icon_gem(20), "Лучшая карта", F_BAR_LABEL, GOLD)
        best_line = (
            f"{best_card['name']}  ·  {best_card['rarity_name']}  ·  "
            f"{format_chance(best_card['rarity_chance'])}%"
        )
        best_line = _fit_text(d, best_line, F_SUB, W - (bar_x0 + 20) - 20)
        d.text((bar_x0 + 20, 456), best_line, font=F_SUB, fill=WHITE)

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=92)
    out.seek(0)
    return out
