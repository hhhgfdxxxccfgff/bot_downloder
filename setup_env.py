import re
import sys
from pathlib import Path

ENV_FILE = Path(".env")


def ask(label: str, default: str = "", validate=None) -> str:
    suffix = f" [Enter = {default}] " if default else ""
    while True:
        val = input(f"{label}{suffix}: ").strip() or default
        if validate is None:
            return val
        err = validate(val)
        if err is None:
            return val
        print(f"❗ {err}")


def valid_token(s: str) -> str | None:
    if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{20,}", s):
        return "شکل توکن باید مثل 123456789:AA... باشه؛ از @BotFather بگیر"
    return None


def valid_admins(s: str) -> str | None:
    parts = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return "حداقل یه ایدی لازمه؛ آیدیتو با @userinfobot بگیر"
    for p in parts:
        if not p.lstrip("-").isdigit():
            return f"«{p}» عدد نیست؛ ایدی‌ها فقط رقم باید باشن (با کاما جدا)"
    return None


def main() -> None:
    print("═" * 46)
    print(" نصب بات میریم! 🤖")
    print(" (هر سوال که جاش خالی بمونه از پیش‌فرض میره جلو)")
    print("═" * 46 + "\n")

    old = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                old[k.strip()] = v.strip()

    token = old.get("BOT_TOKEN", "")
    if token:
        masked = token.split(":")[0] + ":***" + token[-4:]
        new_one = input(f"1) توکن بات: {masked}  (Enter = همون قبلی): ").strip()
        if new_one:
            token = ask("   توکن جدید", validate=valid_token)
        print("   ✅ توکن ست شد\n")
    else:
        token = ask("1) توکن بات (از @BotFather)", validate=valid_token)
        print("   ✅ توکن ست شد\n")

    default_user = old.get("BOT_USERNAME", "")
    raw_user = input(f"2) یوزرنیم بات (بدون @){' [' + default_user + '] ' if default_user else ''}: ").strip()
    username = raw_user or default_user
    print("   ✅ ثبت شد\n")

    admins = ask("3) ایدی عددی ادمین‌ها (با کاما جدا)", old.get("ADMIN_IDS", ""), validate=valid_admins)
    print("   ✅ ادمین‌ها ثبت شدن\n")

    db = ask("4) آدرس دیتابیس", old.get("DATABASE_URL", "sqlite+aiosqlite:///data.db"))
    caption = ask(
        "5) قالب کپشن — متغیرها: {title} {artist} {size} {duration} {date}",
        old.get("DEFAULT_CAPTION", "🎧 {title}"),
    )
    btn = ask("6) متن دکمه دانلود تو چنل", old.get("LINK_BTN_TEXT", "📥 دانلود"))

    ENV_FILE.write_text(
        f"BOT_TOKEN={token}\n"
        f"BOT_USERNAME={username}\n"
        f"ADMIN_IDS={admins}\n\n"
        f"DATABASE_URL={db}\n\n"
        f"DEFAULT_CAPTION={caption}\n"
        f"LINK_BTN_TEXT={btn}\n"
    )
    print("\n✅ همه چی تو .env ذخیره شد؛ میریم برای استارت!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nلغو شد")
        sys.exit(1)
