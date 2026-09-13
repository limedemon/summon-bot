from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import db
from keyboards import back_kb, main_menu_kb
from utils import DIV, cards_word, esc, exp_word, format_chance

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
    try:
        mention = f"@{(await bot.me()).username}"
    except Exception:
        mention = "@бота"
    text = (
        "🎴 <b>Саммон карточек</b>\n"
        f"{DIV}\n"
        f"Напиши <code>{esc(mention)}</code> в любом чате, выбери саммон — "
        "и выпадет случайная карточка.\n\n"
        "<i>Чем ниже шанс редкости, тем ценнее находка.</i>"
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
async def cmd_start(message: Message, state: FSMContext, bot: Bot, command: CommandObject):
    await state.clear()
    # Deep link from the "смотреть коллекцию" button under an inline summon result.
    if (command.args or "").strip() == "collection":
        text = await render_collection(message.from_user.id)
        await message.answer(text, reply_markup=back_kb("menu:main"))
        return
    await show_main_menu(message, bot)


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await show_main_menu(call.message, bot, edit=True)
    await call.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    exp = int(user["exp"]) if user else 0
    collection = await db.get_collection(call.from_user.id)

    lines = [
        f"👤 <b>{esc(call.from_user.first_name)}</b>",
        DIV,
        f"✨ Опыт · <b>{exp}</b> {exp_word(exp)}",
        f"🎴 Коллекция · <b>{len(collection)}</b> {cards_word(len(collection))}",
    ]
    if collection:
        best = min(collection, key=lambda c: float(c["rarity_chance"]))
        lines.append(
            f"💎 Жемчужина · "
            f"<b>{esc(best['name'])}</b> <i>({esc(best['rarity_name'])})</i>"
        )
    text = "\n".join(lines)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(text, reply_markup=back_kb("menu:main"))
    await call.answer()


async def render_collection(user_id: int) -> str:
    """Collection screen text — shared by the menu button and the /start deep link."""
    collection = await db.get_collection(user_id)
    if not collection:
        text = (
            "🎴 <b>Коллекция</b>\n"
            f"{DIV}\n"
            "<i>Пока пусто.</i>\n"
            "Вызови бота через @ в любом чате — и здесь появится первая карточка."
        )
    else:
        # rarest groups first, cards inside a group alphabetically
        groups: dict[str, list] = {}
        for c in collection:
            groups.setdefault(c["rarity_name"], []).append(c)
        order = sorted(groups, key=lambda name: float(groups[name][0]["rarity_chance"]))

        total = len(collection)
        lines = [
            f"🎴 <b>Коллекция</b> · <b>{total}</b> {cards_word(total)}",
            DIV,
        ]
        for name in order:
            cards = groups[name]
            chance = cards[0]["rarity_chance"]
            lines.append(
                f"\n<b>{esc(name)}</b> "
                f"<i>{format_chance(chance)}%</i> · {len(cards)}"
            )
            for c in sorted(cards, key=lambda x: x["name"].lower()):
                lines.append(f"   <i>{esc(c['summon_name'])}</i> — {esc(c['name'])}")

        text = "\n".join(lines)
        if len(text) > 3900:
            text = text[:3900].rsplit("\n", 1)[0] + "\n\n<i>…и ещё немного — список длинный.</i>"
    return text


@router.callback_query(F.data == "menu:collection")
async def cb_collection(call: CallbackQuery):
    text = await render_collection(call.from_user.id)
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
