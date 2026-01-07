# Команды для обновления проекта на сервере

## Полное обновление (Backend + Frontend)

```bash
# 1. Перейти в директорию проекта
cd /root/mapsparser-Replit-front

# 2. Остановить старый процесс Flask
pkill -9 -f "python.*main.py"
sleep 2

# 3. Проверить, что порт 8000 свободен
lsof -iTCP:8000 -sTCP:LISTEN
# Если есть процесс - убить его:
# kill -9 <PID>

# 4. Обновить код из GitHub
git pull origin main

# 5. Активировать виртуальное окружение
source venv/bin/activate

# 6. Пересобрать frontend
cd frontend
rm -rf dist
npm install
npm run build
cd ..

# 7. Скопировать собранный frontend в Nginx директорию
sudo cp -r frontend/dist/* /var/www/html/

# 8. Запустить Flask API
python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3

# 9. Проверить, что Flask запустился
lsof -iTCP:8000 -sTCP:LISTEN

# 10. Проверить логи Flask
tail -20 /tmp/seo_main.out

# 11. Перезагрузить Nginx (если нужно)
sudo systemctl reload nginx

# 12. Проверить статус Nginx
sudo systemctl status nginx --no-pager
```

## Быстрое обновление (только Backend)

```bash
cd /root/mapsparser-Replit-front
pkill -9 -f "python.*main.py"
sleep 2
git pull origin main
source venv/bin/activate
python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3
lsof -iTCP:8000 -sTCP:LISTEN
tail -20 /tmp/seo_main.out
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

