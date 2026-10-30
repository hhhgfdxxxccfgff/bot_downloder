#!/bin/bash
# اسکریپت راه‌اندازی tunnel خودکار + تنظیم منوی وب‌اپ
# اجرا: ./run_with_tunnel.sh

PORT="${WEB_PORT:-8000}"
TUNNEL_LOG="/tmp/cloudflared.log"

echo "⬇️  دانلود cloudflared..."
if [ ! -f /tmp/cloudflared ]; then
    curl -sSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x /tmp/cloudflared
fi

echo "🚀 راه‌اندازی tunnel..."
rm -f "$TUNNEL_LOG"
nohup /tmp/cloudflared tunnel --url "http://localhost:$PORT" --logfile "$TUNNEL_LOG" >/dev/null 2>&1 &
TUNNEL_PID=$!

# صبر کردن تا لینک بیاد
echo "⏳ منتظر لینک..."
sleep 5
URL=""
for i in {1..30}; do
    URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
    [ -n "$URL" ] && break
    sleep 2
done

if [ -z "$URL" ]; then
    echo "❌ نتونستم tunnel رو بسازم؛ دستی ادامه بده"
    exit 1
fi

echo "✅ لینک گرفته شد: $URL"

# ذخیره تو .env
cd "$(dirname "$0")"
if ! grep -q "^WEBAPP_URL=" .env 2>/dev/null; then
    echo "WEBAPP_URL=$URL" >> .env
else
    sed -i "s|^WEBAPP_URL=.*|WEBAPP_URL=$URL|" .env
fi

echo "📝 WEBAPP_URL تو .env ذخیره شد"

# ران کردن بات
echo "🎯 ران بات..."
exec python3 -m app.main