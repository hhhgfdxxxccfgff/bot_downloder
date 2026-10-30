import base64
import hashlib
import hmac
import json
import time


def _key(token: str, kind: str) -> bytes:
    return hashlib.sha256(f"{kind}::{token}".encode()).digest()


def pack_stream_token(token: str, user_id: int, file_id: int, ttl: int) -> str:
    payload = {"u": user_id, "f": file_id, "e": int(time.time()) + ttl}
    data = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_key(token, "stream"), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(data).decode() + "." + base64.urlsafe_b64encode(sig).decode()


def unpack_stream_token(token: str, bot_token: str) -> dict | None:
    try:
        data_b64, sig_b64 = token.split(".")
    except ValueError:
        return None
    try:
        data = base64.urlsafe_b64decode(data_b64.encode())
        sig = base64.urlsafe_b64decode(sig_b64.encode())
    except Exception:
        return None
    expected_sig = hmac.new(_key(bot_token, "stream"), data, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = json.loads(data)
    except Exception:
        return None
    if payload.get("e", 0) < time.time():
        return None
    return payload