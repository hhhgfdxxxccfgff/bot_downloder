import json

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Drop, DropUnlock, MediaFile, Referral, User
from app.utils.persian_time import countdown, fmt_time

MEMBEROK = ("member", "administrator", "creator")


def load_conditions(drop: Drop) -> dict:
    try:
        c = json.loads(drop.conditions or "{}")
    except json.JSONDecodeError:
        c = {}
    return {
        "channels": list(c.get("channels") or []),
        "referrals": int(c.get("referrals") or 0),
        "code": c.get("code") or "",
    }


def describe_conditions(c: dict) -> str:
    """چک‌لیست شرایط به زبون آدمیزادی"""
    lines = []
    for chat_id in c["channels"]:
        lines.append(f"عضویت تو چنل <code>{chat_id}</code>")
    if c["referrals"]:
        lines.append(f"دعوت {c['referrals']} نفر با لینک دعوت خودت")
    if c["code"]:
        lines.append(f"وارد کردن کد ویژه: «{c['code']}»")
    return "\n".join(lines) if lines else "(شرطی برای ورود زودتر گذاشته نشده)"


async def referrals_seen(session: AsyncSession, user_id: int) -> int:
    n = await session.scalar(
        select(func.count(Referral.referred_id)).where(Referral.inviter_id == user_id)
    )
    return int(n or 0)


async def memberships(bot: Bot, chat_ids: list[int], user_tg: int) -> list[int]:
    """لیست چنل‌هایی که کاربر توشون عضوه از بین شناسه‌های ورودی"""
    ok = []
    for chat_id in chat_ids:
        try:
            m = await bot.get_chat_member(chat_id, user_tg)
            if m.status in MEMBEROK:
                ok.append(chat_id)
        except Exception:
            continue
    return ok


async def check(
    session: AsyncSession, bot: Bot, drop: Drop, user_tg: int, user_id: int, code: str = ""
) -> tuple[bool, str]:
    """بررسی کامل شرایط؛ خروجی: (میتونه بازش کنه، پیام وضعیت)"""
    c = load_conditions(drop)

    ok_ch, todo_ch = [], []
    if c["channels"]:
        ok_ch = await memberships(bot, c["channels"], user_tg)
        todo_ch = [ch for ch in c["channels"] if ch not in ok_ch]

    ref_n = await referrals_seen(session, user_id)
    ref_ok = ref_n >= c["referrals"]

    code_ok = (not c["code"]) or (code.strip().lower() == c["code"].strip().lower())

    lines = ["🔓 شرایط ورود زودتر:"]
    for ch in c["channels"]:
        mark = "✅" if ch in ok_ch else "❌"
        lines.append(f"{mark} عضویت تو چنل <code>{ch}</code>")
    if c["referrals"]:
        mark = "✅" if ref_ok else "❌"
        lines.append(f"{mark} دعوت دوستان: {ref_n}/{c['referrals']}")
    if c["code"]:
        mark = "✅" if code_ok else "❌"
        lines.append(f"{mark} کد ویژه")
    if not (c["channels"] or c["referrals"] or c["code"]):
        lines.append("— شرطی نگذاشته شده")

    passed = not todo_ch and ref_ok and code_ok
    return passed, "\n".join(lines)


async def unlocked(session: AsyncSession, file_id: int, user_id: int) -> bool:
    hit = await session.scalar(
        select(DropUnlock.file_id).where(
            DropUnlock.file_id == file_id, DropUnlock.user_id == user_id
        )
    )
    return hit is not None


async def mark_unlocked(session: AsyncSession, file_id: int, user_id: int) -> bool:
    """True یعنی همین الان برای اولین بار باز شد"""
    if await unlocked(session, file_id, user_id):
        return False
    session.add(DropUnlock(file_id=file_id, user_id=user_id))
    await session.commit()
    return True


async def unlocked_users_tg(session: AsyncSession, file_id: int) -> list[int]:
    return list(
        await session.scalars(
            select(User.tg_id).join(DropUnlock, DropUnlock.user_id == User.id)
            .where(DropUnlock.file_id == file_id)
        )
    )


def locked_text(drop: Drop, f: MediaFile, checklist: str) -> str:
    c = load_conditions(drop)
    head = f"🔒 «{f.title or f.code}» هنوز رسماً منتشر نشده!"
    when = fmt_time(drop.release_at)
    remaining = countdown(drop.release_at)
    body = drop.teaser_text or ""
    rules = f"\n\n{checklist}" if checklist else ""
    extra = f"\n{body}" if body else ""
    tail = "" if c["channels"] or c["referrals"] or c["code"] else "\n\nشما شرطی نداری، تا پخش منتظر بمون 🎬"
    return f"{head}\n⏰ زمان انتشار: {when}\n⏳ باقی‌مونده: {remaining}{extra}{rules}{tail}"
