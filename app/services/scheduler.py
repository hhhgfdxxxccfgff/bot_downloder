import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.db.models import Drop, MediaFile
from app.services.channels import default_channel
from app.services.publish import file_btn, publish_to_channel

logger = logging.getLogger(__name__)


async def release_drop(session: AsyncSession, bot: Bot, drop: Drop) -> bool:
    """خود دراپ رو منتشر می‌کند (پست چنل + نوتیف به بازکرده‌ها)؛ False یعنی قبلا ریله شد"""
    if drop.released:
        return False
    f = await session.get(MediaFile, drop.file_id)
    if f is None:
        logger.warning("دراپ %s به فایل %s وصله که وجود ندارد", drop.id, drop.file_id)
        drop.released = True
        drop.is_active = False
        await session.commit()
        return False

    ch = await default_channel(session)
    if ch is None:
        logger.error("هیچ چنلی نداریم؛ دراپ %s مانده رو زمین", drop.id)
        return False

    try:
        msg_id = await publish_to_channel(bot, ch.chat_id, f)
    except Exception as e:
        logger.error("انتشار دراپ %s شکست خورد: %s", drop.id, e)
        return False

    f.published = True
    f.channel_msg_id = msg_id
    drop.released = True
    drop.is_active = False
    await session.commit()

    from app.services.drop_check import unlocked_users_tg
    tg_ids = await unlocked_users_tg(session, f.id)
    for tg in tg_ids:
        try:
            await bot.send_message(
                tg,
                "🔥 آهنگمون منتشر شد! برو گوشش کن:",
                reply_markup=file_btn(f.code),
            )
        except Exception:
            continue
    logger.info("دراپ %s منتشر شد (پست=%s)", drop.id, msg_id)
    return True


async def _tick(session: AsyncSession, bot: Bot) -> int:
    now = datetime.now()
    due = list(
        await session.scalars(
            select(Drop).where(
                Drop.released.is_(False),
                Drop.is_active.is_(True),
                Drop.release_at <= now,
            )
        )
    )
    done = 0
    for d in due:
        try:
            if await release_drop(session, bot, d):
                done += 1
        except Exception:
            logger.exception("تیک دراپ %s خورد", d.id)
    return done


async def run_scheduler(bot: Bot) -> None:
    logger.info("زمان‌بدنده روشن شد ⏱")
    while True:
        try:
            async with Session() as session:
                await _tick(session, bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("زمان‌بدنده یه خطا خورد ولی ادامه می‌دهم")
        await asyncio.sleep(30)
