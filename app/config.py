import os
import sys
from dataclasses import dataclass

import dotenv

dotenv.load_dotenv()


def _admins(raw: str) -> list[int]:
    out = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            print(f"[config] admin id {part!r} عدد نیست، رد شد")
    return out


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_username: str
    admin_ids: list[int]
    database_url: str
    caption_template: str
    link_btn_text: str
    webapp_url: str
    web_port: int
    stream_ttl: int


ADMIN_IDS = _admins(os.getenv("ADMIN_IDS", ""))
TOKEN = os.getenv("BOT_TOKEN", "").strip()

settings = Settings(
    bot_token=TOKEN,
    bot_username=os.getenv("BOT_USERNAME", "").split("@")[-1].strip(),
    admin_ids=ADMIN_IDS,
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data.db"),
    caption_template=os.getenv("DEFAULT_CAPTION", "🎧 {title}"),
    link_btn_text=os.getenv("LINK_BTN_TEXT", "📥 دانلود"),
    webapp_url=os.getenv("WEBAPP_URL", "").strip(),
    web_port=int(os.getenv("WEB_PORT", "8000")),
    stream_ttl=int(os.getenv("STREAM_TTL", "600")),
)

if not settings.bot_token:
    print("توکن بات تو فایل .env خالیه؛ اول ستش کن بعد اجرا کن")
    sys.exit(1)
