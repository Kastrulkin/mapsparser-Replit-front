#!/bin/bash
# Скрипт для запуска Flask и фронтенда

cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/mapsparser-Replit-front"

echo "🚀 Запуск серверов..."

# 1. Остановить старые процессы
echo "1️⃣ Останавливаем старые процессы..."
PID_FLASK=$(lsof -tiTCP:8000 -sTCP:LISTEN -P 2>/dev/null)
PID_FRONTEND=$(lsof -tiTCP:3000 -sTCP:LISTEN -P 2>/dev/null)

if [ -n "$PID_FLASK" ]; then
    kill -9 $PID_FLASK
    echo "   ✅ Остановлен Flask (PID: $PID_FLASK)"
fi

if [ -n "$PID_FRONTEND" ]; then
    kill -9 $PID_FRONTEND
    echo "   ✅ Остановлен фронтенд (PID: $PID_FRONTEND)"
fi

sleep 2

# 2. Запустить Flask
echo ""
echo "2️⃣ Запускаем Flask сервер на порту 8000..."
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
FLASK_PID=$!
sleep 3

if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "   ✅ Flask запущен (PID: $FLASK_PID)"
else
    echo "   ❌ Flask не запустился, проверьте логи: tail -50 /tmp/seo_main.out"
fi

# 3. Запустить фронтенд
echo ""
echo "3️⃣ Запускаем фронтенд на порту 3000..."
cd frontend
npm run dev >/tmp/seo_frontend.out 2>&1 &
FRONTEND_PID=$!
sleep 5

if lsof -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "   ✅ Фронтенд запущен (PID: $FRONTEND_PID)"
else
    echo "   ❌ Фронтенд не запустился, проверьте логи: tail -50 /tmp/seo_frontend.out"
fi

echo ""
echo "✅ Готово!"
echo ""
echo "📊 Проверка портов:"
lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 && echo "   ✅ Flask: http://localhost:8000" || echo "   ❌ Flask не запущен"
lsof -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1 && echo "   ✅ Фронтенд: http://localhost:3000" || echo "   ❌ Фронтенд не запущен"
echo ""
echo "📝 Логи:"
echo "   Flask: tail -f /tmp/seo_main.out"
echo "   Фронтенд: tail -f /tmp/seo_frontend.out"
echo ""
echo "🛑 Для остановки:"
echo "   kill $FLASK_PID $FRONTEND_PID"

