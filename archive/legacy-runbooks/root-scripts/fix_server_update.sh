#!/bin/bash
# Скрипт для исправления обновления на сервере

echo "🔄 Исправление обновления на сервере..."

# 1. Остановить все процессы
echo "1. Останавливаем процессы..."
pkill -9 -f "python.*main.py" || true
pkill -9 -f "python.*worker.py" || true
sleep 3

# 2. Убить процесс на порту 8000
echo "2. Освобождаем порт 8000..."
PID=$(lsof -tiTCP:8000 -sTCP:LISTEN -P 2>/dev/null)
if [ ! -z "$PID" ]; then
    echo "   Найден процесс $PID на порту 8000, убиваем..."
    kill -9 $PID
    sleep 2
fi

# 3. Проверить, что порт свободен
lsof -iTCP:8000 -sTCP:LISTEN 2>/dev/null && echo "⚠️ Порт всё ещё занят!" || echo "✅ Порт свободен"

# 4. Решить конфликт с git pull
echo "3. Решаем конфликт git..."
cd /root/mapsparser-Replit-front
git stash || true
git reset --hard HEAD || true
rm -f frontend/dist/index.html

# 5. Получить последние изменения
echo "4. Получаем изменения с GitHub..."
git pull origin main

# 6. Пересобрать фронтенд
echo "5. Пересобираем фронтенд..."
cd frontend
rm -rf dist
npm run build
cd ..

# 7. Проверить сборку
echo "6. Проверяем сборку..."
ls -lh frontend/dist/assets/index-*.js

# 8. Запустить бэкенд
echo "7. Запускаем бэкенд..."
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
sleep 4

# 9. Запустить worker
echo "8. Запускаем worker..."
python src/worker.py >/tmp/seo_worker.out 2>&1 &
sleep 2

# 10. Проверить запуск
echo "9. Проверяем запуск..."
lsof -iTCP:8000 -sTCP:LISTEN

# 11. Проверить логи
echo "10. Проверяем логи..."
tail -20 /tmp/seo_main.out | grep -E "ERROR|Traceback|AssertionError" || tail -10 /tmp/seo_main.out

# 12. Скопировать фронтенд
echo "11. Копируем фронтенд в веб-директорию..."
cp -r frontend/dist/* /var/www/html/
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

# 13. Перезапустить nginx
echo "12. Перезапускаем nginx..."
systemctl restart nginx

echo "✅ Обновление завершено!"


