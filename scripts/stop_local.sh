#!/bin/zsh
echo "🛑 Остановка локальных сервисов..."

kill $(lsof -tiTCP:8000) 2>/dev/null || echo "Порт 8000 свободен"
kill $(lsof -tiTCP:3000) 2>/dev/null || echo "Порт 3000 свободен"

if [ -f .pids/worker.pid ]; then
  kill $(cat .pids/worker.pid) 2>/dev/null || true
  rm .pids/worker.pid
  echo "⚙️  Worker остановлен"
fi

echo "✅ Остановка завершена"
