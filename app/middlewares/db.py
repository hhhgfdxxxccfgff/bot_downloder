from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TgUser
from sqlalchemy import select

from app.db import Session
from app.db.models import User


class DbSessionMiddleware(BaseMiddleware):
    """یه سشن برای کل آپدیت باز می‌کنه و کاربر رو هم ثبت/آپدیت می‌کنه"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        async with Session() as session:
            data["session"] = session
            db_user = None
            if tg_user is not None:
                db_user = await session.scalar(
                    select(User).where(User.tg_id == tg_user.id)
                )
                if db_user is None:
                    db_user = User(tg_id=tg_user.id, username=tg_user.username)
                    session.add(db_user)
                elif db_user.username != tg_user.username:
                    db_user.username = tg_user.username
                await session.commit()
            data["db_user"] = db_user
            return await handler(event, data)


async def get_db_user(event: Message | CallbackQuery) -> User:
    """هندلرهایی که میدل‌ور روی‌شون نیفتاده (کیس نادر) بکار میان"""
    tg_user = event.from_user
    async with Session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_user.id))
        if user is None:
            user = User(tg_id=tg_user.id, username=tg_user.username)
            session.add(user)
            await session.commit()
        return user
