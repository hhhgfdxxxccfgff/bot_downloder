from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, FileRequest, MediaFile, User
from app.middlewares.access import AdminOnly
from app.services.caption import human_size
from app.services.channels import add_channel

router = Router(name="admin")
router.message.middleware(AdminOnly())


@router.message(F.text == "📄 فایل‌های من")
async def my_files(msg: Message, session: AsyncSession):
    files = list(
        await session.scalars(
            select(MediaFile).order_by(MediaFile.id.desc()).limit(15)
        )
    )
    if not files:
        await msg.answer("هنوز فایلی آپلود نکردی")
        return
    lines = []
    for f in files:
        status = "✅" if f.published else "⏳"
        size = human_size(f.size) if f.size else ""
        lines.append(f"{status} <code>{f.code}</code> — {f.title or 'بی‌نام'} {size}")
    await msg.answer("آخرین فایل‌ها:\n" + "\n".join(lines))


@router.message(F.text == "📢 چنل‌ها")
async def channels_list(msg: Message, session: AsyncSession):
    channels = list(await session.scalars(select(Channel).order_by(Channel.id)))
    if not channels:
        await msg.answer(
            "هیچ چنلی ثبت نشده ❗\n"
            "برای افزودن: /addch @channel یا /addch -100xxxx"
        )
        return
    lines = [
        f"{'⭐' if c.is_default else '•'} {c.title} (<code>{c.chat_id}</code>)"
        for c in channels
    ]
    await msg.answer("چنل‌ها:\n" + "\n".join(lines))


@router.message(F.text.startswith("/addch "))
async def add_channel_cmd(msg: Message, session: AsyncSession, bot):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("راه درستش: /addch @channel یا /addch -1001234567")
        return
    target = parts[1].strip()
    try:
        chat = await bot.get_chat(target)
    except Exception:
        await msg.answer("به این چنل دسترسی ندارم؛ بات رو اول عضو/ادمینش کن بعد امتحان کن ☝️")
        return
    ch = await add_channel(session, chat.id, chat.title or "", make_default=True)
    kind = "⭐ پیش‌فرض" if ch.is_default else "عادی"
    await msg.answer(f"چنل اضافه شد ✅\n«{chat.title}» ({kind})")


@router.message(F.text == "📊 آمار")
async def stats(msg: Message, session: AsyncSession):
    users_total = await session.scalar(select(func.count(User.id)))
    files_total = await session.scalar(select(func.count(MediaFile.id)))
    req_total = await session.scalar(select(func.count(FileRequest.id)))
    day_ago = datetime.now() - timedelta(days=1)
    req_today = await session.scalar(
        select(func.count(FileRequest.id)).where(FileRequest.created_at >= day_ago)
    )
    await msg.answer(
        "📊 آمار:\n"
        f"👤 کاربرا: {users_total}\n"
        f"🗂 فایل‌ها: {files_total}\n"
        f"📥 کل دانلودها: {req_total}\n"
        f"📥 ۲۴ ساعت اخیر: {req_today}"
    )
