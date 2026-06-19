# 🔧 Исправление обоих Telegram-ботов на сервере

## Проблема 1: Бот для управления аккаунтом не запускается

**Ошибка:** `TELEGRAM_BOT_TOKEN не установлен`

### Решение:

```bash
cd /root/mapsparser-Replit-front

# 1. Проверить, есть ли токен в .env
grep TELEGRAM_BOT_TOKEN .env

# 2. Если токена нет, добавить его
nano .env
# Добавьте строку: TELEGRAM_BOT_TOKEN=ваш_токен_от_Local_bot

# 3. Перезапустить бота
systemctl restart telegram-bot

# 4. Проверить статус
systemctl status telegram-bot
```

## Проблема 2: Бот для обмена отзывами

### Шаг 1: Установить schedule в venv

```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
pip install schedule
deactivate
```

### Шаг 2: Создать файл сервиса для бота обмена отзывами

```bash
cd /root/mapsparser-Replit-front

# Создать файл сервиса
cat > telegram-reviews-bot.service << 'EOF'
[Unit]
Description=BeautyBot Telegram Reviews Exchange Bot
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/mapsparser-Replit-front
Environment=PYTHONPATH=/root/mapsparser-Replit-front/src
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/root/mapsparser-Replit-front/.env
ExecStart=/root/mapsparser-Replit-front/venv/bin/python /root/mapsparser-Replit-front/src/telegram_reviews_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### Шаг 3: Установить и запустить сервис

```bash
# Скопировать сервис в systemd
cp telegram-reviews-bot.service /etc/systemd/system/

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable telegram-reviews-bot

# Запустить бота
systemctl start telegram-reviews-bot

# Проверить статус
systemctl status telegram-reviews-bot
```

### Шаг 4: Добавить токен для бота обмена отзывами

```bash
cd /root/mapsparser-Replit-front

# Проверить, есть ли токен
grep TELEGRAM_REVIEWS_BOT_TOKEN .env

# Если токена нет, добавить
nano .env
# Добавьте строку: TELEGRAM_REVIEWS_BOT_TOKEN=ваш_токен_от_beautyreviewexchange_bot

# Перезапустить бота
systemctl restart telegram-reviews-bot
```

## Проверка работы обоих ботов

```bash
# Статус бота для управления аккаунтом
systemctl status telegram-bot
journalctl -u telegram-bot -n 20 --no-pager

# Статус бота для обмена отзывами
systemctl status telegram-reviews-bot
journalctl -u telegram-reviews-bot -n 20 --no-pager
```

## Ожидаемый результат

Оба бота должны показать в логах:
```
🤖 Telegram-бот запущен...
✅ Бот готов к работе. Ожидаю сообщения...
```

## Если что-то не работает

### Проверить токены в .env:
```bash
cd /root/mapsparser-Replit-front
grep -E "TELEGRAM_BOT_TOKEN|TELEGRAM_REVIEWS_BOT_TOKEN" .env
```

Должно быть:
```
TELEGRAM_BOT_TOKEN=токен_для_Local_bot
TELEGRAM_REVIEWS_BOT_TOKEN=токен_для_beautyreviewexchange_bot
```

### Проверить, что файлы ботов существуют:
```bash
ls -la /root/mapsparser-Replit-front/src/telegram_bot.py
ls -la /root/mapsparser-Replit-front/src/telegram_reviews_bot.py
```

### Проверить зависимости:
```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
python -c "import telegram; print('telegram OK')"
python -c "import schedule; print('schedule OK')"
deactivate
```

