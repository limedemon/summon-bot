from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import db
from config import PAGE_SIZE
from handlers.admin_menu import require_admin
from keyboards import cancel_kb, card_view_kb, cards_admin_kb, confirm_kb, summons_pick_kb
from states import AddCard, EditCard
from utils import format_chance, parse_positive_int

router = Router(name="admin_cards")


def rarity_pick_for_card_kb(rarities, cb_prefix: str, back_cb: str):
    b = InlineKeyboardBuilder()
    for r in rarities:
        label = f"{r['name']} ({format_chance(r['chance'])}%)"
        b.row(InlineKeyboardButton(text=label, callback_data=f"{cb_prefix}:{r['id']}"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb))
    return b.as_markup()


async def show_summon_picker(target, edit: bool = True):
    summons = await db.list_summons()
    if not summons:
        text = "🎴 <b>Карточки</b>\n\nСначала создай саммон в разделе «🎲 Саммоны»."
        kb = summons_pick_kb([], "adm_cards_summon", "adm:menu")
    else:
        text = "🎴 <b>Карточки</b>\n\nВыбери саммон:"
        kb = summons_pick_kb(summons, "adm_cards_summon", "adm:menu")
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def show_cards_list(target, summon_id: int, page: int = 0, edit: bool = True):
    summon = await db.get_summon(summon_id)
    cards = await db.list_cards_in_summon(summon_id)
    text = f"🎴 <b>Карточки саммона «{summon['name']}»</b>" if summon else "🎴 Карточки"
    if not cards:
        text += "\n\nПока ни одной карточки нет."
    kb = cards_admin_kb(summon_id, cards, page, PAGE_SIZE)
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


def render_card_caption(card) -> str:
    return (
        f"🎴 <b>{card['name']}</b>\n"
        f"💎 Редкость: {card['rarity_name']} ({format_chance(card['rarity_chance'])}%)\n"
        f"✨ Опыт: {card['exp_reward']}"
    )


async def send_card_view(message: Message, card_id: int):
    card = await db.get_card(card_id)
    await message.answer_photo(
        photo=card["photo_file_id"],
        caption=render_card_caption(card),
        reply_markup=card_view_kb(card_id, card["summon_id"]),
    )


async def refresh_card_view(bot: Bot, chat_id: int, message_id: int, card_id: int, new_photo: str | None = None):
    card = await db.get_card(card_id)
    caption = render_card_caption(card)
    kb = card_view_kb(card_id, card["summon_id"])
    if new_photo:
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media=InputMediaPhoto(media=new_photo, caption=caption, parse_mode="HTML"),
            reply_markup=kb,
        )
    else:
        await bot.edit_message_caption(
            chat_id=chat_id, message_id=message_id, caption=caption, parse_mode="HTML", reply_markup=kb
        )


# ---------- navigation ----------

@router.callback_query(F.data == "adm:cards")
async def cb_cards(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    await show_summon_picker(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("adm_cards_summon:"))
async def cb_cards_summon(call: CallbackQuery):
    if not await require_admin(call):
        return
    summon_id = int(call.data.split(":")[1])
    await show_cards_list(call.message, summon_id)
    await call.answer()


@router.callback_query(F.data.startswith("adm_cards_page:"))
async def cb_cards_page(call: CallbackQuery):
    if not await require_admin(call):
        return
    _, summon_id, page = call.data.split(":")
    await show_cards_list(call.message, int(summon_id), int(page))
    await call.answer()


@router.callback_query(F.data.startswith("adm_card_view:"))
async def cb_card_view(call: CallbackQuery):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    await call.message.delete()
    await send_card_view(call.message, card_id)
    await call.answer()


# ---------- add card ----------

@router.callback_query(F.data.startswith("adm_card_add:"))
async def cb_card_add(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    summon_id = int(call.data.split(":")[1])
    rarities = await db.list_rarities_sorted()
    if not rarities:
        await call.answer("⛔ Сначала создай хотя бы одну редкость.", show_alert=True)
        return
    await state.update_data(summon_id=summon_id)
    await state.set_state(AddCard.photo)
    await call.message.edit_text(
        "🖼 Отправь фото карточки:", reply_markup=cancel_kb(f"adm_cards_summon:{summon_id}")
    )
    await call.answer()


@router.message(AddCard.photo)
async def process_add_card_photo(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    if not message.photo:
        await message.answer("⚠️ Нужно отправить именно фото. Попробуй ещё раз:")
        return
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AddCard.name)
    await message.answer("✏️ Введи название карточки:")


@router.message(AddCard.name)
async def process_add_card_name(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("⚠️ Название не может быть пустым. Попробуй ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(AddCard.rarity)
    rarities = await db.list_rarities_sorted()
    data = await state.get_data()
    await message.answer(
        "💎 Выбери редкость карточки:",
        reply_markup=rarity_pick_for_card_kb(
            rarities, "adm_card_pick_rarity", f"adm_cards_summon:{data['summon_id']}"
        ),
    )


@router.callback_query(AddCard.rarity, F.data.startswith("adm_card_pick_rarity:"))
async def process_add_card_rarity(call: CallbackQuery, state: FSMContext):
    if not await db.is_admin(call.from_user.id):
        return
    rarity_id = int(call.data.split(":")[1])
    await state.update_data(rarity_id=rarity_id)
    await state.set_state(AddCard.exp)
    await call.message.edit_text("✨ Введи количество опыта за карточку (целое число > 0):")
    await call.answer()


@router.message(AddCard.exp)
async def process_add_card_exp(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    exp = parse_positive_int(message.text or "")
    if exp is None:
        await message.answer("⚠️ Нужно целое число больше 0. Попробуй ещё раз:")
        return
    data = await state.get_data()
    card_id = await db.add_card(data["summon_id"], data["photo_file_id"], data["name"], data["rarity_id"], exp)
    await state.clear()
    await message.answer("✅ Карточка добавлена.")
    await send_card_view(message, card_id)


# ---------- edit card ----------

@router.callback_query(F.data.startswith("adm_card_edit_photo:"))
async def cb_edit_photo(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    await state.update_data(card_id=card_id, view_chat_id=call.message.chat.id, view_message_id=call.message.message_id)
    await state.set_state(EditCard.photo)
    await call.message.answer("🖼 Отправь новое фото карточки:")
    await call.answer()


@router.message(EditCard.photo)
async def process_edit_photo(message: Message, state: FSMContext, bot: Bot):
    if not await db.is_admin(message.from_user.id):
        return
    if not message.photo:
        await message.answer("⚠️ Нужно отправить именно фото. Попробуй ещё раз:")
        return
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    await db.update_card_field(data["card_id"], "photo_file_id", file_id)
    await state.clear()
    await refresh_card_view(bot, data["view_chat_id"], data["view_message_id"], data["card_id"], new_photo=file_id)
    await message.answer("✅ Фото обновлено.")


@router.callback_query(F.data.startswith("adm_card_edit_name:"))
async def cb_edit_name(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    await state.update_data(card_id=card_id, view_chat_id=call.message.chat.id, view_message_id=call.message.message_id)
    await state.set_state(EditCard.name)
    await call.message.answer("✏️ Введи новое название карточки:")
    await call.answer()


@router.message(EditCard.name)
async def process_edit_name(message: Message, state: FSMContext, bot: Bot):
    if not await db.is_admin(message.from_user.id):
        return
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("⚠️ Название не может быть пустым. Попробуй ещё раз:")
        return
    data = await state.get_data()
    await db.update_card_field(data["card_id"], "name", name)
    await state.clear()
    await refresh_card_view(bot, data["view_chat_id"], data["view_message_id"], data["card_id"])
    await message.answer("✅ Название обновлено.")


@router.callback_query(F.data.startswith("adm_card_edit_rarity:"))
async def cb_edit_rarity(call: CallbackQuery):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    rarities = await db.list_rarities_sorted()
    b = InlineKeyboardBuilder()
    for r in rarities:
        label = f"{r['name']} ({format_chance(r['chance'])}%)"
        b.row(InlineKeyboardButton(text=label, callback_data=f"adm_card_set_rarity:{card_id}:{r['id']}"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_card_view_back:{card_id}"))
    await call.message.edit_caption(caption="💎 Выбери новую редкость:", reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adm_card_set_rarity:"))
async def cb_set_rarity(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    _, card_id, rarity_id = call.data.split(":")
    await db.update_card_field(int(card_id), "rarity_id", int(rarity_id))
    await refresh_card_view(bot, call.message.chat.id, call.message.message_id, int(card_id))
    await call.answer("✅ Редкость обновлена")


@router.callback_query(F.data.startswith("adm_card_view_back:"))
async def cb_card_view_back(call: CallbackQuery, bot: Bot):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    await refresh_card_view(bot, call.message.chat.id, call.message.message_id, card_id)
    await call.answer()


@router.callback_query(F.data.startswith("adm_card_edit_exp:"))
async def cb_edit_exp(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    await state.update_data(card_id=card_id, view_chat_id=call.message.chat.id, view_message_id=call.message.message_id)
    await state.set_state(EditCard.exp)
    await call.message.answer("✨ Введи новое количество опыта (целое число > 0):")
    await call.answer()


@router.message(EditCard.exp)
async def process_edit_exp(message: Message, state: FSMContext, bot: Bot):
    if not await db.is_admin(message.from_user.id):
        return
    exp = parse_positive_int(message.text or "")
    if exp is None:
        await message.answer("⚠️ Нужно целое число больше 0. Попробуй ещё раз:")
        return
    data = await state.get_data()
    await db.update_card_field(data["card_id"], "exp_reward", exp)
    await state.clear()
    await refresh_card_view(bot, data["view_chat_id"], data["view_message_id"], data["card_id"])
    await message.answer("✅ Опыт обновлён.")


# ---------- delete card ----------

@router.callback_query(F.data.startswith("adm_card_del:"))
async def cb_card_del(call: CallbackQuery):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    card = await db.get_card(card_id)
    if not card:
        await call.answer("Уже удалена", show_alert=True)
        return
    await call.message.edit_caption(
        caption=f"Удалить карточку «{card['name']}»?",
        reply_markup=confirm_kb(f"adm_card_del_yes:{card_id}", f"adm_card_view_back:{card_id}"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_card_del_yes:"))
async def cb_card_del_yes(call: CallbackQuery):
    if not await require_admin(call):
        return
    card_id = int(call.data.split(":")[1])
    card = await db.get_card(card_id)
    summon_id = card["summon_id"] if card else None
    await db.delete_card(card_id)
    await call.message.delete()
    if summon_id:
        await show_cards_list(call.message, summon_id, edit=False)
    await call.answer("Удалено")
