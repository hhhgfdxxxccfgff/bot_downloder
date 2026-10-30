from datetime import datetime

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Drop, FileRequest, MediaFile, Referral, User
from app.keyboards.reply import ADMIN_MENU
from app.middlewares.db import get_db_user

router = Router(name="start")


@router.message(CommandStart())
async def entry(msg: Message, state: FSMContext, session: AsyncSession):
    # پارامترهای deep link: f_<code> برای گرفتن فایل و r_<tg_id> برای دعوت
    payload = msg.text.split(" ", 1)[1] if " " in msg.text else ""
    user = await get_db_user(msg)
    await state.clear()

    if payload.startswith("f_"):
        await deliver_file(msg, session, payload[2:].strip(), user.id)
        return
    if payload.startswith("r_") and payload[2:].isdigit():
        inviter_id = int(payload[2:])
        if inviter_id != user.tg_id:
            await tag_referral(session, msg.bot, inviter_id, user.tg_id)

    if user.tg_id in settings.admin_ids:
        await msg.answer("سلام ادمین عزیز 🙌\nاز منوی زیر انتخاب کن:", reply_markup=ADMIN_MENU)
    else:
        await msg.answer("سلام! خوش اومدی 👋 آهنگساز مرسی که هستی.")


async def deliver_file(
    msg: Message, session: AsyncSession, code: str, user_id: int
) -> None:
    f = await session.scalar(select(MediaFile).where(MediaFile.code == code))
    if f is None:
        await msg.answer("این لینک اشتباهه یا منقضی شده 🤔")
        return

    # فاز دراپ: اگه آهنگ تازه هنوز پخش نشده، فقط اعلام می‌کنیم
    drop = await session.scalar(select(Drop).where(Drop.file_id == f.id))
    if drop and drop.is_active and drop.release_at and datetime.now() < drop.release_at:
        until = drop.release_at.strftime("%Y-%m-%d %H:%M")
        await msg.answer(
            f"⏰ این آهنگ هنوز رسماً منتشر نشده!\nزمان انتشار: {until}"
        )
        return

    caption = "🎧 " + (f.title or f.code)
    if f.artist:
        caption += "\n🎙 " + f.artist

    if f.kind is f.kind.AUDIO:
        await msg.answer_audio(f.file_id, caption=caption[:1024])
    elif f.kind is f.kind.VIDEO:
        await msg.answer_video(f.file_id, caption=caption[:1024])
    elif f.kind is f.kind.PHOTO:
        await msg.answer_photo(f.file_id, caption=caption[:1024])
    else:
        await msg.answer_document(f.file_id, caption=caption[:1024])

    session.add(FileRequest(file_id=f.id, user_id=user_id))
    await session.commit()


async def tag_referral(
    session: AsyncSession, bot, inviter_tg: int, referred_tg: int
) -> None:
    # توی جدول، کلیدها شناسهٔ رکورد کاربر هستن نه آیدی تلگرام
    inviter_id = await session.scalar(
        select(User.id).where(User.tg_id == inviter_tg)
    )
    referred_id = await session.scalar(
        select(User.id).where(User.tg_id == referred_tg)
    )
    if not inviter_id or not referred_id:
        return
    exists = await session.scalar(
        select(Referral).where(Referral.referred_id == referred_id)
    )
    if exists is not None:
        return
    session.add(Referral(referred_id=referred_id, inviter_id=inviter_id))
    await session.commit()
    try:
        await bot.send_message(
            inviter_tg, "🎁 یه نفر با لینک دعوتت اومد و امتیاز گرفت!"
        )
    except Exception:
        pass  # اگه دعوت‌کننده باتو استارت نکرده، پیام نمیرسد اشک ندارد
