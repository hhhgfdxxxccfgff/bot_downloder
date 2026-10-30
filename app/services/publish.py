from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions

from app.config import settings
from app.db.models import MediaFile
from app.services.caption import rendered_caption


def deep_link(code: str) -> str:
    return f"https://t.me/{settings.bot_username}?start=f_{code}"


def file_btn(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        {"text": settings.link_btn_text, "url": deep_link(code)},
    ]])


async def publish_to_channel(bot: Bot, chat_id: int, f: MediaFile) -> int:
    """پست لینک‌محور برمی‌گردونه message id چنل"""
    caption = rendered_caption(f)
    keyboard = file_btn(f.code)

    if f.kind is f.kind.AUDIO and f.cover_file_id:
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=f.cover_file_id,
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    return msg.message_id
