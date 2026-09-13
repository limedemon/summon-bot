from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from handlers.admin_menu import require_admin
from keyboards import admins_kb, cancel_kb
from states import AddAdmin
from utils import DIV

router = Router(name="admin_admins")


async def show_admins(target, edit: bool = True):
    admin_ids = await db.get_admin_ids()
    main_admin_id = await db.get_main_admin_id()
    text = f"👤 <b>Админы</b>\n{DIV}\n<i>👑 — главный, его нельзя снять.</i>"
    kb = admins_kb(admin_ids, main_admin_id)
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm:admins")
async def cb_admins(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    await show_admins(call.message)
    await call.answer()


@router.callback_query(F.data == "adm_admin_add")
async def cb_admin_add(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.set_state(AddAdmin.target)
    await call.message.edit_text(
        "➕ Перешли сюда любое сообщение от нового админа, либо пришли его числовой Telegram ID:",
        reply_markup=cancel_kb("adm:admins"),
    )
    await call.answer()


@router.message(AddAdmin.target)
async def process_add_admin(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id):
        return

    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    elif message.forward_origin is not None:
        sender = getattr(message.forward_origin, "sender_user", None)
        if sender:
            target_id = sender.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        target_id = int(message.text.strip())

    if target_id is None:
        await message.answer(
            "⚠️ Не удалось определить пользователя. Перешли сообщение от него "
            "(с открытым профилем) или пришли его числовой ID:"
        )
        return

    if await db.is_admin(target_id):
        await message.answer("⚠️ Этот пользователь уже админ.")
    else:
        await db.add_admin(target_id)
        await message.answer(f"✅ Пользователь <code>{target_id}</code> назначен админом.")
    await state.clear()
    await show_admins(message, edit=False)


@router.callback_query(F.data.startswith("adm_admin_del:"))
async def cb_admin_del(call: CallbackQuery):
    if not await require_admin(call):
        return
    target_id = int(call.data.split(":")[1])
    main_admin_id = await db.get_main_admin_id()
    if target_id == main_admin_id:
        await call.answer("⛔ Нельзя снять главного админа.", show_alert=True)
        return
    await db.remove_admin(target_id)
    await call.answer("Удалено")
    await show_admins(call.message)
