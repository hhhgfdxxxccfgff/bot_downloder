import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.config import settings
from app.db.base import init_db
from app.handlers import admin, drops, start, upload
from app.middlewares.db import DbSessionMiddleware
from app.services.scheduler import run_scheduler
from app.web import set_bot
from app.web.routes import app as web_app


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

    # تنظیم بات برای وب
    routes.set_bot(bot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    # اگه WEBAPP_URL تنظیم شده، منوی وب‌اپ رو ست می‌کنیم
    if settings.webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🎧 پنل موزیک",
                    web_app=WebAppInfo(url=settings.webapp_url)
                )
            )
            logging.info(f"منوی وب‌اپ ست شد: {settings.webapp_url}")
        except Exception as e:
            logging.warning(f"خطا در تنظیم منوی وب‌اپ: {e}")

    # زمان‌بدنده انتشار خودکار
    scheduler_task = asyncio.create_task(run_scheduler(bot))

    # راه‌اندازی وب‌سرور FastAPI در پس‌زمینه
    web_config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=settings.web_port,
        log_level="warning",
    )
    web_server = uvicorn.Server(web_config)
    web_task = asyncio.create_task(web_server.serve())

    logging.info("بات بالا اومد ✅")
    try:
        await dp.start_polling(
            bot, allowed_updates=["message", "callback_query", "my_chat_member"]
        )
    finally:
        scheduler_task.cancel()
        web_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("بات خاموش شد 👋")
