import aiohttp
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import settings
from app.db import Session
from app.db.models import Drop, MediaFile, User
from app.services.drop_check import unlocked as check_unlocked
from app.web.auth import validate_init_data
from app.web.tokens import pack_stream_token, unpack_stream_token

_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

def get_bot():
    return _bot

app = FastAPI()
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/w/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/w/api/catalog")
async def catalog(x_telegram_init_data: str = Header(None)):
    if not x_telegram_init_data:
        raise HTTPException(401, "این صفحه فقط تو تلگرام باز میشه")
    user_data = validate_init_data(x_telegram_init_data, settings.bot_token)
    if not user_data:
        raise HTTPException(401, "ورود نامعتبر")
    tg_id = user_data.get("id")
    async with Session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        user_id = user.id if user else None

        files = await session.scalars(
            select(MediaFile).where(MediaFile.published == True).order_by(MediaFile.id.desc()).limit(50)
        )
        result = []
        for f in files:
            drop = await session.scalar(
                select(Drop).where(Drop.file_id == f.id, Drop.is_active == True)
            )
            locked = False
            countdown_sec = None
            can_stream = False
            stream_url = None
            conditions = None

            if drop:
                if not drop.released:
                    locked = True
                    delta = (drop.release_at - datetime.now()).total_seconds()
                    countdown_sec = max(0, int(delta))
                    if user_id:
                        is_unlocked = await check_unlocked(session, f.id, user_id)
                        if is_unlocked:
                            can_stream = True
                        else:
                            cond = json.loads(drop.conditions or "{}")
                            conditions = {"has_code": bool(cond.get("code")), "has_ref": bool(cond.get("referrals")), "has_ch": bool(cond.get("channels"))}
                else:
                    can_stream = True
            else:
                can_stream = True

            if can_stream and user_id:
                stream_url = f"/w/stream/{f.id}?st={pack_stream_token(settings.bot_token, user_id, f.id, settings.stream_ttl)}"

            entry = {
                "id": f.id,
                "code": f.code,
                "title": f.title or "بی‌نام",
                "artist": f.artist or "",
                "duration": f.duration,
                "cover_url": f"/w/cover/{f.id}?st={pack_stream_token(settings.bot_token, user_id, f.id, settings.stream_ttl)}" if f.cover_file_id else None,
                "locked": locked,
                "countdown": countdown_sec,
                "can_stream": can_stream,
                "stream_url": stream_url,
                "conditions": conditions,
                "release_at": drop.release_at.isoformat() if drop and drop.release_at else None,
            }
            result.append(entry)
        return result


async def _fetch_tg_file(file_id: str):
    bot = get_bot()
    if not bot:
        raise HTTPException(500, "بات آماده نیست")
    file = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}", file.file_size


@app.get("/w/stream/{file_id}")
async def stream(file_id: int, st: str):
    payload = unpack_stream_token(st, settings.bot_token)
    if not payload or payload.get("f") != file_id:
        raise HTTPException(403, "لینک نامعتبر")
    async with Session() as session:
        f = await session.get(MediaFile, file_id)
        if not f:
            raise HTTPException(404, "فایل پیدا نشد")
    url, size = await _fetch_tg_file(f.file_id)
    async with aiohttp.ClientSession() as cs:
        async with cs.get(url) as resp:
            if resp.status != 200:
                raise HTTPException(502, "خطا در دریافت فایل")
            async def gen():
                async for chunk, _ in resp.content.iter_chunks():
                    yield chunk
            headers = {"Accept-Ranges": "bytes"}
            if size:
                headers["Content-Length"] = str(size)
            return StreamingResponse(gen(), media_type=f.mime or "audio/mpeg", headers=headers)


@app.get("/w/cover/{file_id}")
async def cover(file_id: int, st: str):
    payload = unpack_stream_token(st, settings.bot_token)
    if not payload or payload.get("f") != file_id:
        raise HTTPException(403, "لینک نامعتبر")
    async with Session() as session:
        f = await session.get(MediaFile, file_id)
        if not f or not f.cover_file_id:
            raise HTTPException(404, "کاور نیست")
    url, _ = await _fetch_tg_file(f.cover_file_id)
    async with aiohttp.ClientSession() as cs:
        async with cs.get(url) as resp:
            if resp.status != 200:
                raise HTTPException(502, "خطا")
            async def gen():
                async for chunk, _ in resp.content.iter_chunks():
                    yield chunk
            return StreamingResponse(gen(), media_type="image/jpeg")