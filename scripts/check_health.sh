#!/bin/zsh
echo "🔍 Проверка состояния..."

sleep 2
if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null; then
  echo "✅ API (8000): OK"
else
  echo "❌ API (8000): не запущен"
fi

if lsof -iTCP:3000 -sTCP:LISTEN > /dev/null; then
  echo "✅ Frontend (3000): OK"
else
  echo "ℹ️ Frontend (3000): не запущен"
fi
