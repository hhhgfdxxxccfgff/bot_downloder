#!/usr/bin/env bash
# نصب کامل پروژه: ساخت venv، نصب پکیج‌ها، گرفتن متغیرها از کاربر و استارت بات
set -e

BASEDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASEDIR"

PY=python3

# --- محیط مجازی ---
if [ ! -d .venv ]; then
    echo "در حال ساخت محیط مجازی..."
    if $PY -m venv .venv 2>/dev/null; then
        PIP=.venv/bin/pip
    else
        echo "venv در دسترس نیست؛ مستقیم با pip جلو میریم"
        PIP="pip"
    fi
else
    PIP=.venv/bin/pip
fi

echo "در حال نصب پکیج‌ها..."
if [ "$PIP" = "pip" ]; then
    pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt --break-system-packages -q
else
    "$PIP" install -q -r requirements.txt
fi

# --- گرفتن متغیرها (فقط جای خالی‌ها پرسیده میشه) ---
$PY setup_env.py

# --- استارت ---
echo ""
echo "🚀 بالاخره میرسیم به استارت... (با Ctrl+C خاموش کن)"
if [ "$PIP" = "pip" ]; then
    exec python3 -m app.main
else
    exec .venv/bin/python -m app.main
fi
