from datetime import datetime

from app.config import settings
from app.db.models import MediaFile



def human_size(n: int) -> str:
    size = float(n)
    for unit in ("بایت", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "بایت":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} GB"


def fmt_duration(sec: int) -> str:
    sec = int(sec or 0)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def rendered_caption(f: MediaFile) -> str:
    vals = {
        "title": f.title,
        "artist": f.artist,
        "size": human_size(f.size),
        "duration": fmt_duration(f.duration),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    text = settings.caption_template.format(**vals)

    info = []
    if f.artist:
        info.append(f"🎙 {f.artist}")
    if f.duration:
        info.append(f"⏱ {fmt_duration(f.duration)}")
    if f.size:
        info.append(f"💾 {human_size(f.size)}")
    if info:
        text += "\n" + "\n".join(info)
    return text
