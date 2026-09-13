from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from config import PAGE_SIZE
from handlers.admin_menu import require_admin
from keyboards import cancel_kb, confirm_kb, summon_hub_kb, summons_admin_kb
from states import AddSummon
from utils import DIV, esc

router = Router(name="admin_summons")


async def show_summons(target, page: int = 0, edit: bool = True):
    summons = await db.list_summons()
    text = (
        f"🎲 <b>Саммоны</b>\n{DIV}\n<i>Всего: {len(summons)}</i>"
        if summons
        else f"🎲 <b>Саммоны</b>\n{DIV}\n<i>Пока ни одного саммона нет.</i>"
    )
    kb = summons_admin_kb(summons, page, PAGE_SIZE)
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def show_summon_hub(target, summon_id: int, edit: bool = True):
    summon = await db.get_summon(summon_id)
    title = esc(summon["name"]) if summon else "Саммон"
    rarities_count = await db.count_rarities_in_summon(summon_id)
    cards_count = await db.count_cards_in_summon(summon_id)
    text = (
        f"🎲 <b>{title}</b>\n{DIV}\n"
        f"<i>Редкостей: {rarities_count} · Юнитов: {cards_count}</i>"
    )
    kb = summon_hub_kb(summon_id)
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm:summons")
async def cb_summons(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    await show_summons(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("adm_summon_hub:"))
async def cb_summon_hub(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    summon_id = int(call.data.split(":")[1])
    summon = await db.get_summon(summon_id)
    if not summon:
        await call.answer("Уже удалён", show_alert=True)
        await show_summons(call.message)
        return
    await state.clear()
    await show_summon_hub(call.message, summon_id)
    await call.answer()


@router.callback_query(F.data.startswith("adm_summons_page:"))
async def cb_summons_page(call: CallbackQuery):
    if not await require_admin(call):
        return
    page = int(call.data.split(":")[1])
    await show_summons(call.message, page)
    await call.answer()


@router.callback_query(F.data == "adm_summon_add")
async def cb_summon_add(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.set_state(AddSummon.name)
    await call.message.edit_text(
        "✏️ Введи название нового саммона:", reply_markup=cancel_kb("adm:summons")
    )
    await call.answer()


@router.message(AddSummon.name)
async def process_summon_name(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("⚠️ Название не может быть пустым. Попробуй ещё раз:")
        return
    await db.add_summon(name)
    await state.clear()
    await message.answer(f"✅ Саммон <b>{esc(name)}</b> добавлен.")
    await show_summons(message, edit=False)


@router.callback_query(F.data.startswith("adm_summon_del:"))
async def cb_summon_del(call: CallbackQuery):
    if not await require_admin(call):
        return
    summon_id = int(call.data.split(":")[1])
    summon = await db.get_summon(summon_id)
    if not summon:
        await call.answer("Уже удалён", show_alert=True)
        return
    card_count = await db.count_cards_in_summon(summon_id)
    rarity_count = await db.count_rarities_in_summon(summon_id)
    warn = (
        f"\n<i>⚠️ Вместе с ним удалятся юниты ({card_count}) и редкости ({rarity_count})</i>"
        if card_count or rarity_count
        else ""
    )
    await call.message.edit_text(
        f"🗑 Удалить саммон <b>{esc(summon['name'])}</b>?{warn}",
        reply_markup=confirm_kb(f"adm_summon_del_yes:{summon_id}", f"adm_summon_hub:{summon_id}"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_summon_del_yes:"))
async def cb_summon_del_yes(call: CallbackQuery):
    if not await require_admin(call):
        return
    summon_id = int(call.data.split(":")[1])
    await db.delete_summon(summon_id)
    await call.answer("Удалено")
    await show_summons(call.message)
