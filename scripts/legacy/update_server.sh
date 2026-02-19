#!/bin/bash
# Команды для обновления проекта на сервере local

echo "🚀 Обновление проекта на сервере..."
echo ""

# 1. Перейти в директорию проекта
cd /root/mapsparser-Replit-front

# 2. Получить изменения из GitHub
echo "📥 Получаем изменения из GitHub..."
git pull origin main

# 3. Обновить зависимости frontend (если нужно)
echo "📦 Обновляем зависимости frontend..."
cd frontend
npm install --legacy-peer-deps

# 4. Пересобрать frontend
echo "🔨 Собираем frontend..."
rm -rf dist
npm run build

# 5. Скопировать файлы в /var/www/html
echo "📋 Копируем файлы..."
cd ..
rm -rf /var/www/html/*
cp -r frontend/dist/* /var/www/html/
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

# 6. Перезапустить сервисы
echo "🔄 Перезапускаем сервисы..."
systemctl restart nginx
systemctl restart seo-worker 2>/dev/null || true
systemctl restart seo-api 2>/dev/null || true

echo ""
echo "✅ Обновление завершено!"
echo "💡 Очистите кеш браузера (Cmd+Shift+R или Ctrl+Shift+R)"
