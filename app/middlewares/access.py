from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from app.config import settings


class AdminOnly(BaseMiddleware):
    """ورودی رو فقط برای ادمین/مالک رد می‌کنه؛ بقیه بی‌سروصدا دستوری‌شو بی‌پاسخ می‌زنیم"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Any],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return

        if tg_user.id in settings.admin_ids:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("این بخش فقط برای ادمینه 🔒", show_alert=True)
        return
