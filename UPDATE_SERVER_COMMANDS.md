# Команды для обновления проекта на сервере

## Полное обновление (Backend + Frontend)

```bash
# 1. Перейти в директорию проекта
cd /root/mapsparser-Replit-front

# 2. Остановить старый процесс Flask (несколько попыток)
echo "⏹️  Останавливаю Flask..."
pkill -9 -f "python.*main.py"
sleep 2

# 3. Проверить и убить процесс на порту 8000 явно
if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "⚠️  Порт 8000 занят, убиваю процесс..."
    PID=$(lsof -tiTCP:8000 -sTCP:LISTEN)
    kill -9 $PID 2>/dev/null
    sleep 2
    # Проверяем еще раз
    if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
        echo "❌ Не удалось освободить порт 8000!"
        lsof -iTCP:8000 -sTCP:LISTEN
        exit 1
    fi
fi

# 4. Удалить dist перед git pull (чтобы избежать конфликтов)
rm -rf frontend/dist

# 5. Обновить код из GitHub
git pull origin main

# 6. Активировать виртуальное окружение
source venv/bin/activate

# 7. Пересобрать frontend
cd frontend
rm -rf dist
npm install
npm run build
cd ..

# 8. Скопировать собранный frontend в Nginx директорию
sudo cp -r frontend/dist/* /var/www/html/

# 9. Запустить Flask API
echo "🚀 Запускаю Flask API..."
python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3

# 10. Проверить, что Flask запустился
if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "✅ Flask запущен на порту 8000"
    lsof -iTCP:8000 -sTCP:LISTEN
else
    echo "❌ Flask не запустился! Проверьте логи:"
    tail -30 /tmp/seo_main.out
    exit 1
fi

# 11. Проверить логи Flask
echo "📋 Последние логи Flask:"
tail -20 /tmp/seo_main.out

# 12. Перезагрузить Nginx (если нужно)
sudo systemctl reload nginx

# 13. Проверить статус Nginx
sudo systemctl status nginx --no-pager

echo "✅ Обновление завершено!"
```

## Быстрое обновление (только Backend)

```bash
cd /root/mapsparser-Replit-front

# Остановить Flask
pkill -9 -f "python.*main.py"
sleep 2

# Убедиться, что порт свободен
if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    PID=$(lsof -tiTCP:8000 -sTCP:LISTEN)
    kill -9 $PID 2>/dev/null
    sleep 2
fi

# Обновить код
git pull origin main
source venv/bin/activate

# Запустить Flask
python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3

# Проверить
if lsof -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "✅ Flask запущен"
    lsof -iTCP:8000 -sTCP:LISTEN
else
    echo "❌ Flask не запустился!"
    tail -30 /tmp/seo_main.out
fi
```

## Быстрое обновление (только Frontend)

```bash
cd /root/mapsparser-Replit-front/frontend
rm -rf dist
npm install
npm run build
sudo cp -r dist/* /var/www/html/
sudo systemctl reload nginx
```

## Проверка после обновления

```bash
# Проверить Flask процесс
lsof -iTCP:8000 -sTCP:LISTEN

# Проверить логи Flask
tail -30 /tmp/seo_main.out

# Проверить Nginx
sudo systemctl status nginx --no-pager

# Проверить API (должен вернуть JSON)
curl -s http://localhost:8000/api/health | head -c 100
```

## Если что-то пошло не так

```bash
# Остановить все процессы Flask
pkill -9 -f "python.*main.py"

# Проверить, что порт свободен
lsof -iTCP:8000 -sTCP:LISTEN

# Запустить заново
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3

# Проверить логи
tail -50 /tmp/seo_main.out
```

