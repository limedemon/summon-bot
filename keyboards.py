from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils import format_chance, rarity_badge


def rarity_label(rarity, badges: dict[str, str] | None = None) -> str:
    """Button label for a rarity: colour dot, name and chance."""
    dot = f"{rarity_badge(rarity['chance'], badges)} " if badges else ""
    return f"{dot}{rarity['name']} · {format_chance(rarity['chance'])}%"


def main_menu_kb(is_admin: bool):
    b = InlineKeyboardBuilder()
    b.button(text="👤 Профиль", callback_data="menu:profile")
    b.button(text="🎴 Коллекция", callback_data="menu:collection")
    if is_admin:
        b.button(text="⚙️ Админка", callback_data="adm:menu")
    b.adjust(2, 1)
    return b.as_markup()


def back_kb(callback_data: str, text: str = "⬅️ Назад"):
    b = InlineKeyboardBuilder()
    b.button(text=text, callback_data=callback_data)
    return b.as_markup()


def admin_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🎲 Саммоны", callback_data="adm:summons")
    b.button(text="🎴 Карточки", callback_data="adm:cards")
    b.button(text="💎 Редкости", callback_data="adm:rarities")
    b.button(text="👤 Админы", callback_data="adm:admins")
    b.button(text="⬅️ Назад", callback_data="menu:main")
    b.adjust(2, 2, 1)
    return b.as_markup()


def paginate(items, page, page_size):
    start = page * page_size
    chunk = items[start:start + page_size]
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    return chunk, total_pages


def with_pagination(builder: InlineKeyboardBuilder, page: int, total_pages: int, cb_prefix: str):
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{cb_prefix}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{cb_prefix}:{page + 1}"))
        builder.row(*nav)


# ---------- summons ----------

def summons_admin_kb(summons, page, page_size):
    chunk, total_pages = paginate(summons, page, page_size)
    b = InlineKeyboardBuilder()
    for s in chunk:
        b.row(InlineKeyboardButton(text=f"🗑 {s['name']}", callback_data=f"adm_summon_del:{s['id']}"))
    b.row(InlineKeyboardButton(text="➕ Добавить саммон", callback_data="adm_summon_add"))
    with_pagination(b, page, total_pages, "adm_summons_page")
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:menu"))
    return b.as_markup()


def confirm_kb(yes_cb: str, no_cb: str):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да", callback_data=yes_cb)
    b.button(text="❌ Отмена", callback_data=no_cb)
    b.adjust(2)
    return b.as_markup()


# ---------- rarities ----------

def rarities_admin_kb(rarities, page, page_size, badges: dict[str, str] | None = None):
    chunk, total_pages = paginate(rarities, page, page_size)
    b = InlineKeyboardBuilder()
    for r in chunk:
        label = rarity_label(r, badges)
        b.row(
            InlineKeyboardButton(text=label, callback_data="noop"),
            InlineKeyboardButton(text="✏️", callback_data=f"adm_rarity_edit:{r['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"adm_rarity_del:{r['id']}"),
        )
    b.row(InlineKeyboardButton(text="➕ Добавить редкость", callback_data="adm_rarity_add"))
    with_pagination(b, page, total_pages, "adm_rarities_page")
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:menu"))
    return b.as_markup()


def rarity_edit_kb(rarity_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Название", callback_data=f"adm_rarity_edit_name:{rarity_id}")
    b.button(text="✏️ Шанс", callback_data=f"adm_rarity_edit_chance:{rarity_id}")
    b.button(text="⬅️ Назад", callback_data="adm:rarities")
    b.adjust(2, 1)
    return b.as_markup()


def rarity_pick_kb(rarities, cb_prefix: str, badges: dict[str, str] | None = None):
    b = InlineKeyboardBuilder()
    for r in rarities:
        b.row(InlineKeyboardButton(text=rarity_label(r, badges), callback_data=f"{cb_prefix}:{r['id']}"))
    return b.as_markup()


# ---------- cards ----------

def summons_pick_kb(summons, cb_prefix: str, back_cb: str):
    b = InlineKeyboardBuilder()
    for s in summons:
        b.row(InlineKeyboardButton(text=s["name"], callback_data=f"{cb_prefix}:{s['id']}"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb))
    return b.as_markup()


def cards_admin_kb(summon_id, cards, page, page_size):
    chunk, total_pages = paginate(cards, page, page_size)
    b = InlineKeyboardBuilder()
    for c in chunk:
        label = f"{c['name']} · {c['rarity_name']}"
        b.row(InlineKeyboardButton(text=label, callback_data=f"adm_card_view:{c['id']}"))
    b.row(InlineKeyboardButton(text="➕ Добавить карточку", callback_data=f"adm_card_add:{summon_id}"))
    with_pagination(b, page, total_pages, f"adm_cards_page:{summon_id}")
    b.row(InlineKeyboardButton(text="⬅️ К саммонам", callback_data="adm:cards"))
    return b.as_markup()


def card_view_kb(card_id: int, summon_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🖼 Фото", callback_data=f"adm_card_edit_photo:{card_id}")
    b.button(text="✏️ Название", callback_data=f"adm_card_edit_name:{card_id}")
    b.button(text="💎 Редкость", callback_data=f"adm_card_edit_rarity:{card_id}")
    b.button(text="✨ Опыт", callback_data=f"adm_card_edit_exp:{card_id}")
    b.button(text="🗑 Удалить", callback_data=f"adm_card_del:{card_id}")
    b.button(text="⬅️ Назад", callback_data=f"adm_cards_page:{summon_id}:0")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


# ---------- admins ----------

def admins_kb(admin_ids, main_admin_id):
    b = InlineKeyboardBuilder()
    for uid in admin_ids:
        if uid == main_admin_id:
            b.row(InlineKeyboardButton(text=f"👑 {uid}", callback_data="noop"))
        else:
            b.row(
                InlineKeyboardButton(text=str(uid), callback_data="noop"),
                InlineKeyboardButton(text="🗑", callback_data=f"adm_admin_del:{uid}"),
            )
    b.row(InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm_admin_add"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:menu"))
    return b.as_markup()


def cancel_kb(cb: str):
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=cb)
    return b.as_markup()
