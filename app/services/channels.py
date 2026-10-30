from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, MediaFile, new_code


def make_file_code(session: AsyncSession, retries: int = 6) -> str:
    """تولید کد یکتا برای فایل؛ اگه تکراری دراومد دوباره می‌سازیم"""
    code = new_code()
    for _ in range(retries):
        exists = session.scalar(select(MediaFile.id).where(MediaFile.code == code))
        if exists is None:
            return code
        code = new_code()
    return code + "1"  # عملاً نمی‌رسه به اینجا ولی حتماً یه جواب لازمه


async def add_channel(
    session: AsyncSession, chat_id: int, title: str, make_default: bool = True
) -> Channel:
    if make_default:
        for ch in await session.scalars(select(Channel)):
            ch.is_default = False
    ch = await session.scalar(select(Channel).where(Channel.chat_id == chat_id))
    if ch is None:
        if not await session.scalar(select(Channel).limit(1)):
            make_default = True  # اولین چنل همیشه پیش‌فرضه
        ch = Channel(chat_id=chat_id, title=title, is_default=make_default)
        session.add(ch)
        await session.commit()
    elif make_default:
        ch.is_default = True
        await session.commit()
    return ch


async def all_channels(session: AsyncSession) -> list[Channel]:
    return list(await session.scalars(select(Channel).order_by(Channel.id)))


async def default_channel(session: AsyncSession) -> Channel | None:
    ch = await session.scalar(select(Channel).where(Channel.is_default.is_(True)))
    return ch or await session.scalar(select(Channel).order_by(Channel.id).limit(1))


async def remove_channel(session: AsyncSession, chat_id: int) -> bool:
    ch = await session.scalar(select(Channel).where(Channel.chat_id == chat_id))
    if ch is None:
        return False
    await session.delete(ch)
    await session.commit()
    return True
