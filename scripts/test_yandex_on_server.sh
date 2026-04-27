#!/bin/bash
set -euo pipefail

echo "🧪 Тестирование Яндекс-скрипта в текущем production runtime"
echo "==========================================================="
echo ""

if [ ! -f "/opt/seo-app/docker-compose.yml" ]; then
    echo "❌ Не найден /opt/seo-app/docker-compose.yml"
    echo "   Этот скрипт рассчитан на текущий Docker production runtime."
    exit 1
fi

cd /opt/seo-app

if [ ! -f "scripts/test_oliver_yandex.py" ]; then
    echo "❌ Не найден scripts/test_oliver_yandex.py"
    exit 1
fi

echo "✅ Проект найден: /opt/seo-app"
echo "✅ Запускаю тест внутри app container"
echo ""

docker compose exec -T app python3 scripts/test_oliver_yandex.py

echo ""
echo "==========================================================="
echo "✅ Тест завершён"
