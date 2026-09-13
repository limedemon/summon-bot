from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from keyboards import back_kb, main_menu_kb
from utils import format_chance

router = Router(name="common")


async def show_main_menu(message: Message, edit: bool = False):
    admin = await db.is_admin(message.chat.id)
    text = (
        "🎲 <b>Саммон-бот</b>\n\n"
        "Чтобы призвать карточку, напиши в любом чате юзернейм бота через @ "
        "и выбери саммон из списка.\n\n"
        "Опыт и коллекцию карточек можно посмотреть здесь."
    )
    kb = main_menu_kb(admin)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message)


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(call.message, edit=True)
    await call.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    exp = user["exp"] if user else 0
    collection = await db.get_collection(call.from_user.id)
    text = (
        f"👤 <b>Твой профиль</b>\n\n"
        f"✨ Опыт: <b>{exp}</b>\n"
        f"🎴 Карточек в коллекции: <b>{len(collection)}</b>"
    )
    await call.message.edit_text(text, reply_markup=back_kb("menu:main"))
    await call.answer()


@router.callback_query(F.data == "menu:collection")
async def cb_collection(call: CallbackQuery):
    collection = await db.get_collection(call.from_user.id)
    if not collection:
        text = "🎴 <b>Коллекция</b>\n\nПока пусто. Иди саммонить через @бота в любом чате!"
    else:
        lines = ["🎴 <b>Твоя коллекция</b>\n"]
        for c in collection:
            lines.append(
                f"• {c['name']} — {c['rarity_name']} ({format_chance(c['rarity_chance'])}%) "
                f"[{c['summon_name']}]"
            )
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_kb("menu:main"))
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


@router.message(StateFilter(None))
async def fallback(message: Message):
    await show_main_menu(message)
