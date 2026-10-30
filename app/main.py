import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db.base import init_db
from app.handlers import admin, drops, start, upload
from app.middlewares.db import DbSessionMiddleware
from app.services.scheduler import run_scheduler


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    await init_db()

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_routers(start.router, upload.router, drops.router, admin.router)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    scheduler_task = asyncio.create_task(run_scheduler(bot))
    logging.info("بات بالا اومد ✅")
    try:
        await dp.start_polling(
            bot, allowed_updates=["message", "callback_query", "my_chat_member"]
        )
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("بات خاموش شد 👋")
