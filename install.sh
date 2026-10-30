#!/usr/bin/env bash
# نصب تک‌خطی روی هر سرور تازه:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/hhhgfdxxxccfgff/bot_downloder/main/install.sh)"
set -e

REPO_DIR="bot_downloder"

cd "$HOME"

# اگه پروژه تو مسیر فعلی نیست، از گیت‌هاب دانلودش کن
if [ ! -f "$REPO_DIR/setup.sh" ]; then
    echo "⬇️  دانلود پروژه از گیت‌هاب..."
    git clone --depth 1 "https://github.com/hhhgfdxxxccfgff/$REPO_DIR.git"
fi

cd "$REPO_DIR"

chmod +x setup.sh
exec ./setup.sh
