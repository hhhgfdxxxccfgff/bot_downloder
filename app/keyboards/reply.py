from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.services.publish import file_btn

ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [{"text": "⬆️ آپلود آهنگ"}, {"text": "📄 فایل‌های من"}],
        [{"text": "📢 چنل‌ها"}, {"text": "📊 آمار"}],
    ],
    resize_keyboard=True,
)

CANCEL_KB = ReplyKeyboardMarkup(
    keyboard=[[{"text": "❌ لغو"}]],
    resize_keyboard=True,
)

BACK_HOME_KB = CANCEL_KB
