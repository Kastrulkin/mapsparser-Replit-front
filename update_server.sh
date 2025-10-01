#!/bin/bash

# Скрипт для обновления сервера
# Запустите этот скрипт на сервере 80.78.242.105

echo "🔄 Обновление проекта на сервере..."

# Переходим в директорию проекта
cd /root/mapsparser-Replit-front || {
    echo "❌ Директория проекта не найдена!"
    echo "Клонируем проект..."
    git clone https://github.com/Kastrulkin/mapsparser-Replit-front.git
    cd mapsparser-Replit-front
}

echo "📥 Получаем последние изменения из GitHub..."
git fetch origin

echo "🔄 Переключаемся на main ветку..."
git checkout main

echo "⬇️ Сливаем изменения..."
git pull origin main

echo "📦 Обновляем зависимости Python..."
pip install -r requirements.txt

echo "📦 Обновляем зависимости Node.js..."
cd frontend
npm install
npm run build
cd ..

echo "🔄 Перезапускаем сервисы..."
systemctl restart seo-worker
systemctl restart nginx

echo "✅ Обновление завершено!"
echo "🌐 Проверьте сайт: http://80.78.242.105"

# Показываем статус сервисов
echo "📊 Статус сервисов:"
systemctl status seo-worker --no-pager -l
systemctl status nginx --no-pager -l
