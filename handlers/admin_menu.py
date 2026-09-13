from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import db
from keyboards import admin_menu_kb
from utils import DIV

router = Router(name="admin_menu")


async def require_admin(call: CallbackQuery) -> bool:
    if not await db.is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(call: CallbackQuery, state: FSMContext):
    if not await require_admin(call):
        return
    await state.clear()
    text = f"⚙️ <b>Админ-панель</b>\n{DIV}\n<i>Выбери раздел:</i>"
    kb = admin_menu_kb()
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.delete()
        await call.message.answer(text, reply_markup=kb)
    await call.answer()
