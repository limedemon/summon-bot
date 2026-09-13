from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import db
from keyboards import admin_menu_kb

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
    await call.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_menu_kb())
    await call.answer()
