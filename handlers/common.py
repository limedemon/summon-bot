from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import config
import db
import rendering
from keyboards import back_kb, index_kb, main_menu_kb
from leveling import MAX_LEVEL, compute_level
from utils import DIV, esc

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
        photo, kb = await render_index(bot, message.from_user.id, "general", None, 0)
        await message.answer_photo(
            photo=BufferedInputFile(photo.getvalue(), filename="index.jpg"), reply_markup=kb
        )
        return
    await show_main_menu(message, bot)


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await show_main_menu(call.message, bot, edit=True)
    await call.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    user = await db.get_user(user_id)
    total_exp = int(user["exp"]) if user else 0
    level, exp_into, exp_needed = compute_level(total_exp)

    collection = await db.get_collection(user_id)
    total_cards = await db.count_cards_total()
    best_card = min(collection, key=lambda c: float(c["rarity_chance"])) if collection else None
    avatar_file_id = await get_avatar_file_id(bot, user_id)

    photo = await rendering.render_profile_image(
        bot,
        avatar_file_id,
        call.from_user.first_name or "Игрок",
        level,
        MAX_LEVEL,
        exp_into,
        exp_needed,
        len(collection),
        total_cards,
        best_card,
    )
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer_photo(
        photo=BufferedInputFile(photo.getvalue(), filename="profile.jpg"),
        reply_markup=back_kb("menu:main"),
    )
    await call.answer()


async def render_index(bot: Bot, user_id: int, scope: str, scope_id: int | None, page: int):
    """Builds the visual index photo + its keyboard — shared by the menu button,
    the /start deep link and in-place pagination/filter navigation."""
    owned_ids = await db.get_owned_card_ids(user_id)

    summon = await db.get_summon(scope_id) if scope == "summon" and scope_id is not None else None
    if summon is not None:
        cards = await db.list_cards_in_summon(scope_id)
        scope_label = summon["name"]
        effective_scope, effective_id = "summon", scope_id
    else:
        cards = await db.list_all_cards()
        scope_label = "Все саммоны"
        effective_scope, effective_id = "general", None

    total_count = len(cards)
    unlocked_count = sum(1 for c in cards if c["id"] in owned_ids)
    page_size = config.INDEX_PAGE_SIZE
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    page_cards = cards[page * page_size:(page + 1) * page_size]

    photo = await rendering.render_index_image(
        bot, page_cards, owned_ids, scope_label, page, total_pages, unlocked_count, total_count
    )
    summons = await db.list_summons_with_cards()
    kb = index_kb(summons, effective_scope, effective_id, page, total_pages)
    return photo, kb


@router.callback_query(F.data.startswith("idx:"))
async def cb_index(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    if parts[1] == "general":
        scope, scope_id, page = "general", None, int(parts[2])
    else:
        scope, scope_id, page = "summon", int(parts[2]), int(parts[3])

    photo, kb = await render_index(bot, call.from_user.id, scope, scope_id, page)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer_photo(
        photo=BufferedInputFile(photo.getvalue(), filename="index.jpg"), reply_markup=kb
    )
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


@router.message(StateFilter(None))
async def fallback(message: Message, bot: Bot):
    await show_main_menu(message, bot)
