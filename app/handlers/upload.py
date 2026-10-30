import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, FileKind, MediaFile
from app.keyboards.reply import ADMIN_MENU, CANCEL_KB
from app.middlewares.access import AdminOnly
from app.services.caption import human_size
from app.services.channels import all_channels
from app.services.publish import deep_link, publish_to_channel

logger = logging.getLogger(__name__)

router = Router(name="upload")
router.message.middleware(AdminOnly())
router.callback_query.middleware(AdminOnly())

CHAT_BTN = "chs"  # callback: chs:<file_db_id>:<chat_id>
RETRY_BTN = "pbr"


class UpStates(StatesGroup):
    waiting_media = State()


async def _fresh_code(session: AsyncSession) -> str:
    import secrets

    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        taken = await session.scalar(
            select(MediaFile.id).where(MediaFile.code == code)
        )
        if taken is None:
            return code


@router.message(F.text == "⬆️ آپلود آهنگ")
async def open_upload(msg: Message, state: FSMContext):
    await state.set_state(UpStates.waiting_media)
    await msg.answer(
        "فایت رو بفرست 📩 (آهنگ، ویدیو، عکس یا هر فایل دیگه)",
        reply_markup=CANCEL_KB,
    )


@router.message(F.text == "❌ لغو")
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("برگشتم به منو", reply_markup=ADMIN_MENU)


def _channel_kb(file_db_id: int, channels: list[Channel]) -> InlineKeyboardMarkup:
    rows = [[
        {"text": f"📢 {c.title}", "callback_data": f"{CHAT_BTN}:{file_db_id}:{c.chat_id}"}
    ] for c in channels]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _extract(msg: Message) -> dict | None:
    """از پیام ورودی مشخصات فایل رو درمیارم"""
    if a := msg.audio:
        return dict(
            kind=FileKind.AUDIO,
            file_id=a.file_id,
            file_unique_id=a.file_unique_id,
            title=a.title or "",
            artist=a.performer or "",
            duration=int(a.duration or 0),
            size=int(a.file_size or 0),
            mime=a.mime_type or "audio/mpeg",
            cover_file_id=getattr(a.thumbnail, "file_id", None),
        )
    if v := msg.video:
        return dict(
            kind=FileKind.VIDEO,
            file_id=v.file_id,
            file_unique_id=v.file_unique_id,
            title=v.file_name or v.title or "",
            duration=int(v.duration or 0),
            size=int(v.file_size or 0),
            mime=v.mime_type or "video/mp4",
        )
    if d := msg.document:
        return dict(
            kind=FileKind.DOCUMENT,
            file_id=d.file_id,
            file_unique_id=d.file_unique_id,
            title=d.file_name or "",
            size=int(d.file_size or 0),
            mime=d.mime_type or "",
        )
    if p := msg.photo:
        photo = p[-1]
        return dict(
            kind=FileKind.PHOTO,
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            size=int(photo.file_size or 0),
            mime="image/jpeg",
        )
    return None


@router.message(UpStates.waiting_media, F.audio | F.video | F.document | F.photo)
async def receive_file(
    msg: Message, state: FSMContext, session: AsyncSession, db_user
):
    data = _extract(msg)
    if data is None:
        await msg.answer("این نوع فایلو نشناسمت، دوباره بفرست 🙃")
        return

    f = MediaFile(code="", uploaded_by=db_user.id, **data)
    session.add(f)
    await session.flush()
    f.code = await _fresh_code(session)
    await session.commit()

    channels = await all_channels(session)
    if not channels:
        await state.clear()
        await msg.answer(
            "فایل ذخیره شد ولی هنوز چنلی نداریم ❗\n"
            "اول با /addch چنل اضافه کن بعد دوباره آپلود کن"
        )
        return

    lines = [f"فایل ذخیره شد ✅ کد: <code>{f.code}</code>", ""]
    if f.title:
        lines.append(f"• عنوان: {f.title}")
    if f.artist:
        lines.append(f"• خواننده: {f.artist}")
    if f.duration:
        lines.append(f"• مدت: {f.duration} ثانیه")
    if f.size:
        lines.append(f"• حجم: {human_size(f.size)}")
    if f.cover_file_id:
        lines.append("• کاور: ✅")
    await msg.answer("\n".join(lines))
    await msg.answer("کدوم چنل منتشر بشه؟", reply_markup=_channel_kb(f.id, channels))
    await state.clear()


@router.callback_query(F.data.startswith(CHAT_BTN + ":"))
async def handle_publish(cb: CallbackQuery, session: AsyncSession, bot):
    _, file_db_id, chat_id = cb.data.split(":")
    f = await session.get(MediaFile, int(file_db_id))
    if f is None:
        await cb.answer("این فایل تو دیتابیس نیست", show_alert=True)
        return

    try:
        msg_id = await publish_to_channel(bot, int(chat_id), f)
    except Exception as e:
        logger.warning("انتشار در چنل %s خورد: %s", chat_id, e)
        await cb.answer(
            "انتشار شکست خورد؛ مطمئن شو بات تو چنل ادمینه ❗", show_alert=True
        )
        return

    f.published = True
    f.channel_msg_id = msg_id
    await session.commit()
    await cb.answer("منتشر شد ✅")
    await cb.message.edit_text(
        f"پست تو چنل رفت 🔥\n"
        f"• چنل: <code>{chat_id}</code>\n"
        f"• لینک فایل: {deep_link(f.code)}",
        reply_markup=None,
        link_preview_options=None,
    )
