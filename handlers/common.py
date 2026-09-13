from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from keyboards import back_kb, main_menu_kb
from utils import format_chance

router = Router(name="common")


async def get_avatar_file_id(bot: Bot, user_id: int) -> str | None:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
    except Exception:
        return None
    if photos.total_count > 0:
        return photos.photos[0][-1].file_id
    return None


async def show_main_menu(message: Message, bot: Bot, edit: bool = False):
    user_id = message.chat.id
    admin = await db.is_admin(user_id)
    text = (
        "🎲 <b>Саммон-бот</b>\n\n"
        "Чтобы призвать карточку, напиши в любом чате юзернейм бота через @ "
        "и выбери саммон из списка.\n\n"
        "Опыт и коллекцию карточек можно посмотреть здесь."
    )
    kb = main_menu_kb(admin)
    avatar = await get_avatar_file_id(bot, user_id)

    if edit:
        try:
            await message.delete()
        except Exception:
            pass

    if avatar:
        await message.answer_photo(photo=avatar, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await show_main_menu(message, bot)


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await show_main_menu(call.message, bot, edit=True)
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
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(text, reply_markup=back_kb("menu:main"))
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
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(text, reply_markup=back_kb("menu:main"))
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


@router.message(StateFilter(None))
async def fallback(message: Message, bot: Bot):
    await show_main_menu(message, bot)
