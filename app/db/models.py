import secrets
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FileKind(StrEnum):
    AUDIO = "audio"
    DOCUMENT = "document"
    VIDEO = "video"
    PHOTO = "photo"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    requests: Mapped[list["FileRequest"]] = relationship(back_populates="user")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    kind: Mapped[FileKind] = mapped_column(Enum(FileKind, native_enum=False))
    file_id: Mapped[str] = mapped_column(String(256))
    file_unique_id: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    artist: Mapped[str] = mapped_column(String(128), default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    mime: Mapped[str] = mapped_column(String(128), default="")
    cover_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileRequest(Base):
    """هر بار که یکی با لینک فایل رو گرفت، ثبت اینجا میشه (برای آمار)"""
    __tablename__ = "file_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="requests")


class Referral(Base):
    __tablename__ = "referrals"

    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Drop(Base):
    """انتشار زمان‌بندی‌شده (فاز‌های بعدی)"""
    __tablename__ = "drops"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), unique=True)
    release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    teaser_text: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


def new_code() -> str:
    """کد کوتاه برای لینک مثل t.me/bot?start=f_abc12xy"""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))
