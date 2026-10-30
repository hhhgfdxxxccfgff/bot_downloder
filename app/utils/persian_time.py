from datetime import datetime

import jdatetime


def parse_time(raw: str) -> tuple | None:
    """تاریخ ورودی (شمسی یا میلادی) رو با ساعت می‌گیره؛ خروجی: (datetime, شمسی بودن) یا None

    چبناً ساعت اگه نگی، 20:20 می‌گیریم
    """
    raw = raw.strip().replace("،", " ").replace(".", "/").replace("-", "/")
    while "  " in raw:
        raw = raw.replace("  ", " ")
    parts = [p for p in raw.split() if p]
    if not parts:
        return None

    date_s = parts[0]
    time_s = parts[1] if len(parts) > 1 else "20:20"

    hh, mm = _parse_clock(time_s)
    if hh is None:
        return None
    date = _parse_date(date_s)
    if date is None:
        return None
    base = date + [hh, mm]

    if _is_jalali(date_s):
        try:
            jdt = jdatetime.datetime(*base)
        except (ValueError, TypeError):
            return None
        return jdt.togregorian(), True
    try:
        dt = datetime(*base)
    except (ValueError, TypeError):
        return None
    return dt, False


def _parse_clock(s: str) -> tuple:
    s = s.strip()
    if ":" not in s:
        return None, None
    a, _, b = s.partition(":")
    if a.isdigit() and b.isdigit():
        hh, mm = int(a), int(b)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
    return None, None


def _parse_date(s: str) -> list | None:
    p = [x for x in s.split("/") if x]
    if len(p) != 3:
        return None
    try:
        y, m, d = int(p[0]), int(p[1]), int(p[2])
    except ValueError:
        return None
    if m < 1 or m > 12 or d < 1 or d > 31:
        return None
    return [y, m, d]


def _is_jalali(s: str) -> bool:
    return s[:3].isdigit() and 1300 <= int(s[:4]) <= 1500


def fmt_time(dt: datetime) -> str:
    j = jdatetime.datetime.fromgregorian(datetime=dt)
    return (
        f"🗓 {j.year}/{j.month:02d}/{j.day:02d} ساعت {j.hour:02d}:{j.minute:02d}"
        f"  (میلادی {dt:%Y-%m-%d %H:%M})"
    )


def countdown(dt: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    secs = (dt - now).total_seconds()
    if secs <= 0:
        return "همین الان!"
    d, rest = divmod(int(secs), 86400)
    h, rest = divmod(rest, 3600)
    m, s = divmod(rest, 60)
    bits = []
    if d:
        bits.append(f"{d} روز")
    if h:
        bits.append(f"{h} ساعت")
    if m and not d:
        bits.append(f"{m} دقیقه")
    if s and not d and not h:
        bits.append(f"{s} ثانیه")
    return " و ".join(bits)
