import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Drop, FileRequest, MediaFile, Referral, User
from app.keyboards.reply import ADMIN_MENU
from app.middlewares.db import get_db_user
from app.services.drop_check import (
    check as check_conditions,
    locked_text,
    mark_unlocked,
    unlocked,
)
from app.utils.persian_time import countdown

logger = logging.getLogger(__name__)

router = Router(name="start")

# چک دوباره / وارد کردن کد برای دراپ‌های قفل
RECHECK = "evr"  # callback: evr:<file_db_id>
ASK_CODE = "evc"


class UserStates(StatesGroup):
    entering_code = State()


@router.message(CommandStart())
async def entry(msg: Message, state: FSMContext, session: AsyncSession):
    # پارامترهای deep link: f_<code> برای گرفتن فایل و r_<tg_id> برای دعوت
    payload = msg.text.split(" ", 1)[1] if " " in msg.text else ""
    user = await get_db_user(msg)
    await state.clear()

    if payload.startswith("f_"):
        await handle_file_link(msg, session, state, user, payload[2:].strip())
        return
    if payload.startswith("r_") and payload[2:].isdigit():
        inviter_id = int(payload[2:])
        if inviter_id != user.tg_id:
            await tag_referral(session, msg.bot, inviter_id, user.tg_id)

    if user.tg_id in settings.admin_ids:
        await msg.answer("سلام ادمین عزیز 🙌\nاز منوی زیر انتخاب کن:", reply_markup=ADMIN_MENU)
    else:
        await msg.answer("سلام! خوش اومدی 👋")


async def handle_file_link(
    msg: Message, session: AsyncSession, state: FSMContext, user, code: str
) -> None:
    f = await session.scalar(select(MediaFile).where(MediaFile.code == code))
    if f is None:
        await msg.answer("این لینک اشتباهه یا منقضی شده 🤔")
        return

    drop = await session.scalar(select(Drop).where(Drop.file_id == f.id))
    if drop and drop.is_active and not drop.released and datetime.now() >= drop.release_at:
        # ساعت رسیده ولی زمان‌بدنده هنوز تیک نخورده؛ مستقیم منتشرش کنیم
        from app.services.scheduler import release_drop
        try:
            await release_drop(session, msg.bot, drop)
        except Exception:
            logger.exception("انتشار دراپ تو همون لحظه شکست خورد")
        drop = await session.scalar(select(Drop).where(Drop.file_id == f.id))

    if drop and drop.is_active and not drop.released:
        if await unlocked(session, f.id, user.id):
            await msg.answer(
                f"🔓 تو لیستِ زودتر شنیدن هستی!\n⏳ تا پخش رسمی: {countdown(drop.release_at)}"
            )
            return

        passed, checklist = await check_conditions(
            session, msg.bot, drop, user.tg_id, user.id
        )
        if passed:
            await mark_unlocked(session, f.id, user.id)
            await msg.answer(
                "🎉 تبریک، شرط‌ها کامل شد و قفل باز شد!\n"
                f"⏳ تا پخش رسمی: {countdown(drop.release_at)}\n"
                "وقتی پخش شد همونجا خبرت می‌کنم ✅"
            )
            return

        kb_rows = [[{"text": "🔄 بررسی دوباره", "callback_data": f"{RECHECK}:{f.id}"}]]
        if "🔑" in checklist:
            kb_rows.append([{"text": "🔑 وارد کردن کد", "callback_data": f"{ASK_CODE}:{f.id}"}])
        invite_line = ""
        if "دعوت" in checklist:
            invite_line = (
                f"\n\n🔗 لینک دعوت مخصوص خودت:\n"
                f"https://t.me/{settings.bot_username}?start=r_{user.tg_id}"
            )
        await msg.answer(
            locked_text(drop, f, checklist) + invite_line,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
            disable_web_page_preview=True,
        )
        return

    await deliver_file(msg, session, code, user.id, f=f)


async def deliver_file(
    msg: Message, session: AsyncSession, code: str, user_id: int, f: MediaFile | None = None
) -> None:
    if f is None:
        f = await session.scalar(select(MediaFile).where(MediaFile.code == code))
        if f is None:
            await msg.answer("این لینک اشتباهه یا منقضی شده 🤔")
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


@router.callback_query(F.data.startswith(RECHECK + ":"))
async def recheck(cb: CallbackQuery, session: AsyncSession, db_user):
    await _evaluate(cb, session, db_user, "")


@router.callback_query(F.data.startswith(ASK_CODE + ":"))
async def ask_code(cb: CallbackQuery, state: FSMContext):
    _, file_id = cb.data.split(":")
    await state.set_state(UserStates.entering_code)
    await state.update_data(file_db_id=int(file_id))
    await cb.message.reply("🔑 کد ویژه رو بفرست (همین‌جا تو این چت):")
    await cb.answer()


@router.message(UserStates.entering_code)
async def receive_code(
    msg: Message, state: FSMContext, session: AsyncSession, db_user
):
    code = msg.text.strip()
    data = await state.get_data()
    file_db_id = data.get("file_db_id")
    await state.clear()
    f = await session.get(MediaFile, file_db_id) if file_db_id else None
    if f is None:
        await msg.answer("این مورد پیدا نشد؛ لینک رو از اول بزن")
        return
    drop = await session.scalar(select(Drop).where(Drop.file_id == f.id))
    if drop is None or not drop.is_active or drop.released:
        await deliver_file(msg, session, f.code, db_user.id, f=f)
        return
    passed, checklist = await check_conditions(
        session, msg.bot, drop, db_user.tg_id, db_user.id, code=code
    )
    if passed:
        await mark_unlocked(session, f.id, db_user.id)
        await msg.answer(
            "🎉 کد درست بود؛ قفل باز شد!\n⏳ تا پخش رسمی: " + countdown(drop.release_at)
        )
        return
    kb_rows = [[{"text": "🔄 بررسی دوباره", "callback_data": f"{RECHECK}:{f.id}"}]]
    if "🔑" in checklist:
        kb_rows.append([{"text": "🔑 کد اصلی", "callback_data": f"{ASK_CODE}:{f.id}"}])
    await msg.answer(
        locked_text(drop, f, checklist),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        disable_web_page_preview=True,
    )


async def _evaluate(cb: CallbackQuery, session: AsyncSession, db_user, code: str):
    _, file_id = cb.data.split(":")
    f = await session.get(MediaFile, int(file_id))
    if f is None:
        await cb.answer("این فایل پیدا نشد", show_alert=True)
        return
    drop = await session.scalar(select(Drop).where(Drop.file_id == f.id))
    if drop is None or not drop.is_active or drop.released:
        await cb.message.reply("این آهنگ الان منتشر شده! 🎉")
        await cb.answer()
        return
    passed, checklist = await check_conditions(
        session, cb.bot, drop, db_user.tg_id, db_user.id, code=code
    )
    if passed:
        if await mark_unlocked(session, f.id, db_user.id):
            await cb.message.reply(
                "🎉 قفل باز شد! وقت پخش دقیق خبرت می‌کنم؛ منتظر باش ⏳"
            )
        else:
            await cb.message.reply("قبلاً باز کردی 😉 تا پخش منتظر بمون.")
        await cb.answer()
        return
    invite_line = ""
    if "دعوت" in checklist:
        invite_line = (
            f"\n\n🔗 لینک دعوت: https://t.me/{settings.bot_username}?start=r_{db_user.tg_id}"
        )
    kb_rows = [[{"text": "🔄 بررسی دوباره", "callback_data": f"{RECHECK}:{f.id}"}]]
    if "🔑" in checklist:
        kb_rows.append([{"text": "🔑 وارد کردن کد", "callback_data": f"{ASK_CODE}:{f.id}"}])
    await cb.message.edit_text(
        locked_text(drop, f, checklist) + invite_line,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        disable_web_page_preview=True,
    )
    await cb.answer("شرط‌ها هنوز کامل نشده ❌")
