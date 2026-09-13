import asyncio
import logging
from typing import Any, Awaitable, Callable, Union

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, ChosenInlineResult, InlineQuery, Message, TelegramObject

import botinfo
import db
from config import BOT_TOKEN
from handlers import get_root_router

logging.basicConfig(level=logging.INFO)

EventWithUser = Union[Message, CallbackQuery, InlineQuery, ChosenInlineResult]


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[EventWithUser, dict[str, Any]], Awaitable[Any]],
        event: EventWithUser,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            await db.ensure_user(user.id)
        return await handler(event, data)


async def main():
    await db.init_db()
    try:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = await bot.get_me()
        botinfo.BOT_USERNAME = me.username
        logging.info("Запущен как @%s", me.username)

        dp = Dispatcher()

        tracker = UserTrackingMiddleware()
        dp.message.middleware(tracker)
        dp.callback_query.middleware(tracker)
        dp.inline_query.middleware(tracker)
        dp.chosen_inline_result.middleware(tracker)

        dp.include_router(get_root_router())

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
