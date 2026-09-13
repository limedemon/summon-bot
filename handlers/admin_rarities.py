from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from config import PAGE_SIZE
from handlers.admin_menu import require_admin
from keyboards import cancel_kb, confirm_kb, rarities_admin_kb, rarity_edit_kb
from states import AddRarity, EditRarity
from utils import DIV, esc, format_chance, parse_chance, rarity_badge, rarity_badges

router = Router(name="admin_rarities")


async def show_rarities(target, page: int = 0, edit: bool = True):
    rarities = await db.list_rarities_sorted()
    if rarities:
        text = (
            f"💎 <b>Редкости</b>\n{DIV}\n"
            "<i>От самой частой к самой редкой — цвет метки берётся отсюда.</i>"
        )
    else:
        text = f"💎 <b>Редкости</b>\n{DIV}\n<i>Пока ни одной редкости нет.</i>"
    kb = rarities_admin_kb(rarities, page, PAGE_SIZE, rarity_badges(rarities))
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm:rarities")
async def cb_rarities(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    await show_rarities(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("adm_rarities_page:"))
async def cb_rarities_page(call: CallbackQuery):
    if not await require_admin(call):
        return
    page = int(call.data.split(":")[1])
    await show_rarities(call.message, page)
    await call.answer()


@router.callback_query(F.data == "adm_rarity_add")
async def cb_rarity_add(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.set_state(AddRarity.name)
    await call.message.edit_text(
        "✏️ Введи название новой редкости:", reply_markup=cancel_kb("adm:rarities")
    )
    await call.answer()


@router.message(AddRarity.name)
async def process_rarity_name(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("⚠️ Название не может быть пустым. Попробуй ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(AddRarity.chance)
    await message.answer(
        "📊 Теперь укажи шанс редкости в процентах (например 15.5). "
        "Не может быть 0% или 100%, до 20 знаков после запятой:",
        reply_markup=cancel_kb("adm:rarities"),
    )


@router.message(AddRarity.chance)
async def process_rarity_chance(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    chance = parse_chance(message.text or "")
    if chance is None:
        await message.answer(
            "⚠️ Некорректное значение. Число больше 0 и меньше 100, до 20 знаков после запятой. Ещё раз:"
        )
        return
    data = await state.get_data()
    name = data["name"]
    await db.add_rarity(name, chance)
    await state.clear()
    await message.answer(
        f"✅ Редкость <b>{esc(name)}</b> · <code>{format_chance(chance)}%</code> добавлена."
    )
    await show_rarities(message, edit=False)


@router.callback_query(F.data.startswith("adm_rarity_edit:"))
async def cb_rarity_edit(call: CallbackQuery):
    if not await require_admin(call):
        return
    rarity_id = int(call.data.split(":")[1])
    rarity = await db.get_rarity(rarity_id)
    if not rarity:
        await call.answer("Уже удалена", show_alert=True)
        return
    badges = rarity_badges(await db.list_rarities_sorted())
    await call.message.edit_text(
        f"{rarity_badge(rarity['chance'], badges)} <b>{esc(rarity['name'])}</b>\n"
        f"<i>шанс · {format_chance(rarity['chance'])}%</i>\n"
        f"{DIV}\n<i>Что изменить?</i>",
        reply_markup=rarity_edit_kb(rarity_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_rarity_edit_name:"))
async def cb_rarity_edit_name(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    rarity_id = int(call.data.split(":")[1])
    await state.update_data(rarity_id=rarity_id)
    await state.set_state(EditRarity.name)
    await call.message.edit_text(
        "✏️ Введи новое название редкости:", reply_markup=cancel_kb("adm:rarities")
    )
    await call.answer()


@router.message(EditRarity.name)
async def process_edit_rarity_name(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("⚠️ Название не может быть пустым. Попробуй ещё раз:")
        return
    data = await state.get_data()
    await db.update_rarity_name(data["rarity_id"], name)
    await state.clear()
    await message.answer("✅ Название обновлено.")
    await show_rarities(message, edit=False)


@router.callback_query(F.data.startswith("adm_rarity_edit_chance:"))
async def cb_rarity_edit_chance(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    rarity_id = int(call.data.split(":")[1])
    await state.update_data(rarity_id=rarity_id)
    await state.set_state(EditRarity.chance)
    await call.message.edit_text(
        "📊 Введи новый шанс в процентах (0 < x < 100, до 20 знаков после запятой):",
        reply_markup=cancel_kb("adm:rarities"),
    )
    await call.answer()


@router.message(EditRarity.chance)
async def process_edit_rarity_chance(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    chance = parse_chance(message.text or "")
    if chance is None:
        await message.answer(
            "⚠️ Некорректное значение. Число больше 0 и меньше 100, до 20 знаков после запятой. Ещё раз:"
        )
        return
    data = await state.get_data()
    await db.update_rarity_chance(data["rarity_id"], chance)
    await state.clear()
    await message.answer(f"✅ Шанс обновлён на {format_chance(chance)}%.")
    await show_rarities(message, edit=False)


@router.callback_query(F.data.startswith("adm_rarity_del:"))
async def cb_rarity_del(call: CallbackQuery):
    if not await require_admin(call):
        return
    rarity_id = int(call.data.split(":")[1])
    rarity = await db.get_rarity(rarity_id)
    if not rarity:
        await call.answer("Уже удалена", show_alert=True)
        return
    used = await db.count_cards_with_rarity(rarity_id)
    if used:
        await call.answer(
            f"⛔ Нельзя удалить: используется в {used} карточках.", show_alert=True
        )
        return
    await call.message.edit_text(
        f"🗑 Удалить редкость <b>{esc(rarity['name'])}</b>?",
        reply_markup=confirm_kb(f"adm_rarity_del_yes:{rarity_id}", "adm:rarities"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_rarity_del_yes:"))
async def cb_rarity_del_yes(call: CallbackQuery):
    if not await require_admin(call):
        return
    rarity_id = int(call.data.split(":")[1])
    used = await db.count_cards_with_rarity(rarity_id)
    if used:
        await call.answer(f"⛔ Нельзя удалить: используется в {used} карточках.", show_alert=True)
        return
    await db.delete_rarity(rarity_id)
    await call.answer("Удалено")
    await show_rarities(call.message)
