#!/bin/bash
# Скрипт для переключения обратно на SQLite

echo "🔄 Переключение на SQLite..."

# Проверяем наличие .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env файл не найден, создаю..."
    touch .env
fi

# Создаем бэкап текущего .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Обновляем DB_TYPE
if grep -q "DB_TYPE=" .env; then
    sed -i '' 's/^DB_TYPE=.*/DB_TYPE=sqlite/' .env
else
    echo "DB_TYPE=sqlite" >> .env
fi

# Обновляем DATABASE_URL
if grep -q "DATABASE_URL=" .env; then
    sed -i '' 's|^DATABASE_URL=.*|DATABASE_URL=sqlite:///src/reports.db|' .env
else
    echo "DATABASE_URL=sqlite:///src/reports.db" >> .env
fi

echo "✅ Переключено на SQLite"
echo ""
echo "Текущие настройки:"
grep -E "DB_TYPE|DATABASE_URL" .env
echo ""
echo "⚠️  Перезапустите Flask для применения изменений"
