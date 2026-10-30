import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Drop, MediaFile
from app.keyboards.reply import ADMIN_MENU, CANCEL_KB
from app.middlewares.access import AdminOnly
from app.services.channels import all_channels, default_channel
from app.services.drop_check import load_conditions
from app.utils.persian_time import fmt_time, parse_time

logger = logging.getLogger(__name__)

router = Router(name="drops")
router.message.middleware(AdminOnly())
router.callback_query.middleware(AdminOnly())

DROP_BTN = "dpx"  # callback: dpx:<drop_id>:<go|cancel>
CH_PICK = "dpc"


class DropStates(StatesGroup):
    pick_file = State()
    waiting_date = State()
    waiting_teaser = State()
    waiting_channels = State()
    waiting_referrals = State()
    waiting_code = State()


async def _select_file(session: AsyncSession, code: str) -> tuple | None:
    f = await session.scalar(select(MediaFile).where(MediaFile.code == code))
    if f is None:
        return None
    taken = await session.scalar(select(Drop.id).where(Drop.file_id == f.id))
    return f, taken


@router.message(F.text == "🎯 دراپ‌ها")
async def list_drops(msg: Message, session: AsyncSession):
    rows = list(
        await session.scalars(
            select(Drop).order_by(Drop.release_at).where(Drop.released.is_(False))
        )
    )
    if not rows:
        await msg.answer(
            "دراپ فعالی نداری ⏳\n"
            "برنامه این شکلیه: /newdrop <کد فایل>"
        )
        return
    lines = ["🔒 دراپ‌های آینده:"]
    kb_rows = []
    for d in rows:
        f = await session.get(MediaFile, d.file_id)
        title = f.title or f.code if f else f"?{d.file_id}"
        cond = load_conditions(d)
        marks = []
        if cond["channels"]:
            marks.append(f"ch×{len(cond['channels'])}")
        if cond["referrals"]:
            marks.append(f"ref×{cond['referrals']}")
        if cond["code"]:
            marks.append("code")
        lines.append(f"• «{title}» تا {fmt_time(d.release_at)}  [{' '.join(marks) or 'بدون شرط'}]")
        kb_rows.append([
            {"text": f"🚀 {title}", "callback_data": f"{DROP_BTN}:{d.id}:go"},
            {"text": "❌ لغو", "callback_data": f"{DROP_BTN}:{d.id}:cancel"},
        ])
    await msg.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith(DROP_BTN + ":"))
async def drop_action(cb: CallbackQuery, session: AsyncSession, bot):
    _, drop_id, act = cb.data.split(":")
    d = await session.get(Drop, int(drop_id))
    if d is None:
        await cb.answer("این دراپ دیگه وجود نداره", show_alert=True)
        return
    f = await session.get(MediaFile, d.file_id)
    if act == "cancel":
        d.is_active = False
        await session.commit()
        if d.teaser_channel_id:
            try:
                await bot.delete_message(d.teaser_channel_id, d.teaser_msg_id or 0)
            except Exception:
                pass

        # تیزر پست تو چنل اونجا حذفش می‌کنیم اگه بود
        await cb.answer("دراپ لغو شد ✅")
        await cb.message.edit_text("این دراپ لغو شد.")
        return
    if act == "go":
        from app.services.scheduler import release_drop
        await release_drop(session, bot, d)
        await cb.answer("منتشر شد 🔥")


@router.message(F.text == "⏱ دراپ جدید")
async def newdrop_start(msg: Message, state: FSMContext, session: AsyncSession):
    await state.set_state(DropStates.pick_file)
    await msg.answer(
        "کد فایل رو بفرست (یکی از <code>xxx</code> کدایی که تو «فایل‌های من» دیدی):",
        reply_markup=CANCEL_KB,
    )


@router.message(DropStates.pick_file, F.text != "❌ لغو")
async def pick_file(msg: Message, state: FSMContext, session: AsyncSession):
    code = msg.text.strip()
    result = await _select_file(session, code.lstrip("f_"))
    if result is None:
        await msg.answer("این کد رو ندارم یا دراپش ساخته شده؛ دوباره بفرست 🙃")
        return
    f, taken = result
    if taken is not None:
        await state.clear()
        await msg.answer("برای این فایل از قبل دراپ ساختی!", reply_markup=ADMIN_MENU)
        return
    await state.update_data(file_id=f.id, title=f.title or f.code)
    await state.set_state(DropStates.waiting_date)
    await msg.answer(
        f"⏰ کی پخش بشه؟ مثل <code>1404/08/09 20:20</code> یا <code>2026-11-28 20:20</code>\n"
        "(اگه ساعت نگی ۲۰:۲۰ می‌ذارم)",
        reply_markup=CANCEL_KB,
    )


@router.message(DropStates.waiting_date, F.text != "❌ لغو")
async def pick_date(msg: Message, state: FSMContext):
    res = parse_time(msg.text)
    if res is None:
        await msg.answer("تاریخ رو نتونستم بخونم 🙃 مثل 1404/08/09 20:20 بفرست")
        return
    dt, jal = res
    await state.update_data(release_at=dt)
    await state.set_state(DropStates.waiting_teaser)
    await msg.answer(
        f"اوکی؛ پخش: {fmt_time(dt)}\n\n"
        "📝 متن تیزر رو بفرست (Enter یعنی متن پیش‌فرض بذار):\n"
        "مثل: «🔥 ریمیکس جدید شنبه‌شب از اینجا زودتر بشنو!»",
        reply_markup=CANCEL_KB,
    )


@router.message(DropStates.waiting_teaser, F.text != "❌ لغو")
async def pick_teaser(msg: Message, state: FSMContext, session: AsyncSession):
    teaser = "" if msg.text.strip() in ("", "-", "Enter") else msg.text.strip()
    channels = await all_channels(session)
    if not channels:
        await state.clear()
        await msg.answer("هیچ چنلی نداری که بشه تیزر گذاشت! اول /addch بزن", reply_markup=ADMIN_MENU)
        return
    listing = "\n".join(f"{i+1}) {c.title}" for i, c in enumerate(channels))
    await state.update_data(teaser=teaser)
    await state.set_state(DropStates.waiting_channels)
    await msg.answer(
        f"حالا چنلی که تیزر بره اونجا؟\n{listing}\nشماره چنل رو بفرست (Enter = پیش‌فرض ⭐)"
    )


@router.message(DropStates.waiting_channels, F.text != "❌ لغو")
async def pick_channel(msg: Message, state: FSMContext, session: AsyncSession):
    channels = await all_channels(session)
    ch = None
    if msg.text.strip().lstrip("#").isdigit():
        idx = int(msg.text.strip().lstrip("#")) - 1
        if 0 <= idx < len(channels):
            ch = channels[idx]
    elif not msg.text.strip():
        ch = await default_channel(session)
    if ch is None:
        await msg.answer("شماره درست بده یا خالی Enter (پیش‌فرض ⭐)")
        return
    await state.update_data(teaser_channel=ch.chat_id)
    await state.set_state(DropStates.waiting_referrals)
    await msg.answer("👥 چند دوست باید با لینک تو دعوت بشن؟ (عدد؛ Enter = ۰)")


@router.message(DropStates.waiting_referrals, F.text != "❌ لغو")
async def pick_referrals(msg: Message, state: FSMContext):
    t = msg.text.strip()
    if t and not t.isdigit():
        await msg.answer("عدد بگو؛ مثل 3. یا Enter = ۰")
        return
    await state.update_data(referrals=int(t or 0))
    await state.set_state(DropStates.waiting_code)
    await msg.answer("🔑 کد خاصی لازم باشه؟ بفرست (Enter = بدون کد)\nمثل: REMIX1404")


@router.message(DropStates.waiting_code, F.text != "❌ لغو")
async def pick_code(msg: Message, state: FSMContext, session: AsyncSession, bot):
    code = "" if msg.text.strip() in ("", "-") else msg.text.strip()
    data = await state.get_data()
    conds = {"channels": [], "referrals": data["referrals"], "code": code}
    tc_id = data["teaser_channel"]
    channels = await all_channels(session)
    for c in channels:
        if c.chat_id == tc_id:
            f = await session.get(MediaFile, data["file_id"])
            d = Drop(
                file_id=f.id,
                release_at=data["release_at"],
                teaser_text=data["teaser"],
                conditions=json.dumps(conds, ensure_ascii=False),
                teaser_channel_id=tc_id,
            )
            session.add(d)
            await session.flush()

            teaser_msg = await bot.send_message(
                tc_id,
                _teaser_text(d, f),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    {"text": "⏰ پخش زودتر", "url": f"https://t.me/{settings.bot_username}?start=f_{f.code}"},
                ]]),
            )
            d.teaser_msg_id = teaser_msg.message_id
            await session.commit()

            await state.clear()
            await msg.answer(
                f"دراپ ساخته شد ✅\n{fmt_time(data['release_at'])}\n"
                f"شرط‌ها: {'×'.join([]) } اعمال شد\n"
                f"تیزر تو چنل رفت 📢",
                reply_markup=ADMIN_MENU,
            )
            return
    await msg.answer("چنل رو پیدا نکردم، دوباره شماره بده")


def _teaser_text(d: Drop, f: MediaFile) -> str:
    c = load_conditions(d)
    bits = [d.teaser_text or f"🔥 «{f.title or f.code}» به زودی!"]
    bits.append("")
    bits.append(fmt_time(d.release_at))
    early = []
    if c["channels"]:
        early.append(f"عضویت تو {'و'.join(str(x) for x in c['channels'])}")
    if c["referrals"]:
        early.append(f"دعوت {c['referrals']} نفر")
    if c["code"]:
        early.append("کد ویژه")
    if early:
        bits.append("⏰ برای زودتر شنیدن: " + " + ".join(early))
        bits.append("روی دکمه بزن 👇")
    return "\n".join(bits)
