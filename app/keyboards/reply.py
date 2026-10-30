from aiogram.types import ReplyKeyboardMarkup

ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [{"text": "⬆️ آپلود آهنگ"}, {"text": "📄 فایل‌های من"}],
        [{"text": "🎯 دراپ‌ها"}, {"text": "⏱ دراپ جدید"}],
        [{"text": "📢 چنل‌ها"}, {"text": "📊 آمار"}],
    ],
    resize_keyboard=True,
)

CANCEL_KB = ReplyKeyboardMarkup(
    keyboard=[[{"text": "❌ لغو"}]],
    resize_keyboard=True,
)