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

import botinfo
import db
from config import COOLDOWN_SECONDS
from leveling import compute_level
from utils import (
    DIV,
    esc,
    exp_word,
    fmt_num,
    format_chance,
    format_duration,
    weighted_pick,
)

router = Router(name="inline")


def collection_kb() -> InlineKeyboardMarkup | None:
    """Wide CTA under a summon result: a deep link into the bot's private chat.

    The result message usually lives in someone else's group, where a callback
    button would be useless — so it has to be a t.me link with a /start payload.
    """
    if not botinfo.BOT_USERNAME:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🗂 Смотреть индекс",
                url=f"https://t.me/{botinfo.BOT_USERNAME}?start=collection",
            )
        ]]
    )


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

    user_before = await db.get_user(user_id)
    old_exp = int(user_before["exp"]) if user_before else 0
    old_level, _, _ = compute_level(old_exp)

    card = weighted_pick(cards, "rarity_chance")
    await db.set_cooldown(user_id, summon_id)
    await db.add_exp(user_id, card["exp_reward"])
    is_new = not await db.owns_card(user_id, card["id"])
    await db.grant_card(user_id, card["id"])

    exp = int(card["exp_reward"])
    user = await db.get_user(user_id)
    total_exp = int(user["exp"]) if user else exp
    new_level, _, _ = compute_level(total_exp)

    header = (
        "🎊 <b>Новая карточка!</b>"
        if is_new
        else "🔄 <b>Повтор</b> — <i>такая уже в коллекции</i>"
    )

    caption = (
        f"{header}\n"
        f"🎴 <b>{esc(card['name'])}</b>\n"
        f"{DIV}\n"
        f"💎 Редкость · <b>{esc(card['rarity_name'])}</b> "
        f"<i>{format_chance(card['rarity_chance'])}%</i>\n"
        f"🌀 Саммон · <i>{esc(summon['name'])}</i>\n"
        f"✨ Опыт · <b>+{fmt_num(exp)}</b> → "
        f"<b>{fmt_num(total_exp)}</b> {exp_word(total_exp)}"
    )

    kb = collection_kb()
    try:
        await bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=InputMediaPhoto(media=card["photo_file_id"], caption=caption, parse_mode="HTML"),
            reply_markup=kb,
        )
    except Exception:
        await bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )

    if new_level > old_level:
        # Best-effort DM: the roll usually happens inline in someone else's chat,
        # so this only reaches players who have a private chat with the bot open.
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Новый уровень!</b>\nТеперь у тебя <b>{new_level}</b> уровень.",
            )
        except Exception:
            pass
