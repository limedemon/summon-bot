import time

from aiogram import Bot, Router
from aiogram.types import (
    ChosenInlineResult,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputMediaPhoto,
    InputTextMessageContent,
)

import db
from config import COOLDOWN_SECONDS
from utils import (
    DIV,
    esc,
    exp_word,
    format_chance,
    format_duration,
    rarity_badge,
    rarity_badges,
    weighted_pick,
)

router = Router(name="inline")


@router.inline_query()
async def handle_inline_query(query: InlineQuery):
    summons = await db.list_summons_with_cards()
    text = query.query.strip().lower()
    if text:
        summons = [s for s in summons if text in s["name"].lower()]

    results = []
    now = int(time.time())
    for s in summons[:50]:
        last_used = await db.get_cooldown(query.from_user.id, s["id"])
        if last_used is not None and now - last_used < COOLDOWN_SECONDS:
            remaining = COOLDOWN_SECONDS - (now - last_used)
            description = f"⏳ Ещё {format_duration(remaining)}"
        else:
            description = "✅ Готово к саммону"

        # A reply markup is required so Telegram returns inline_message_id
        # in the chosen_inline_result update.
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎲", callback_data="noop")]]
        )
        results.append(
            InlineQueryResultArticle(
                id=str(s["id"]),
                title=f"🎲  {s['name']}",
                description=description,
                input_message_content=InputTextMessageContent(
                    message_text=f"🎲 <b>{esc(s['name'])}</b>\n<i>раскрываем карточку…</i>",
                    parse_mode="HTML",
                ),
                reply_markup=kb,
            )
        )

    await query.answer(results, cache_time=1, is_personal=True)


@router.chosen_inline_result()
async def handle_chosen_result(chosen: ChosenInlineResult, bot: Bot):
    summon_id = int(chosen.result_id)
    user_id = chosen.from_user.id
    inline_message_id = chosen.inline_message_id
    if inline_message_id is None:
        return

    await db.ensure_user(user_id)

    summon = await db.get_summon(summon_id)
    if summon is None:
        await bot.edit_message_text(
            inline_message_id=inline_message_id, text="⚠️ <i>Этот саммон больше не существует.</i>"
        )
        return

    now = int(time.time())
    last_used = await db.get_cooldown(user_id, summon_id)
    if last_used is not None and now - last_used < COOLDOWN_SECONDS:
        remaining = COOLDOWN_SECONDS - (now - last_used)
        await bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=(
                f"⏳ <b>{esc(summon['name'])}</b>\n"
                f"<i>перезарядка</i> · <code>{format_duration(remaining)}</code>"
            ),
        )
        return

    cards = await db.list_cards_in_summon(summon_id)
    if not cards:
        await bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=f"⚠️ <i>В саммоне</i> <b>{esc(summon['name'])}</b> <i>пока нет карточек.</i>",
        )
        return

    card = weighted_pick(cards, "rarity_chance")
    await db.set_cooldown(user_id, summon_id)
    await db.add_exp(user_id, card["exp_reward"])
    is_new = not await db.owns_card(user_id, card["id"])
    await db.grant_card(user_id, card["id"])

    badges = rarity_badges(await db.list_rarities_sorted())
    badge = rarity_badge(card["rarity_chance"], badges)
    exp = int(card["exp_reward"])
    status = (
        "🆕 <b>Новая карточка в коллекции</b>"
        if is_new
        else "🔁 <i>Такая уже есть в коллекции</i>"
    )

    caption = (
        f"{badge} <b>{esc(card['name'])}</b>\n"
        f"<i>{esc(card['rarity_name'])} · {format_chance(card['rarity_chance'])}%"
        f" · {esc(summon['name'])}</i>\n"
        f"{DIV}\n"
        f"{status}\n"
        f"✨ <b>+{exp}</b> {exp_word(exp)}"
    )

    try:
        await bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=InputMediaPhoto(media=card["photo_file_id"], caption=caption, parse_mode="HTML"),
            reply_markup=None,
        )
    except Exception:
        await bot.edit_message_text(
            inline_message_id=inline_message_id, text=caption, parse_mode="HTML"
        )
