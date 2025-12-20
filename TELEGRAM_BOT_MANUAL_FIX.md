# 🔧 Ручное исправление Telegram-бота (пока файлы не на сервере)

## Быстрая проверка и запуск

Выполните на сервере по порядку:

### 1. Проверить, запущен ли бот

```bash
ps aux | grep telegram_bot
```

Если процесс не найден, продолжайте.

### 2. Проверить systemd сервис

```bash
systemctl status telegram-bot
```

Если сервис не существует, создайте его:

```bash
# Создать файл сервиса
cat > /etc/systemd/system/telegram-bot.service << 'EOF'
[Unit]
Description=BeautyBot Telegram Bot
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/mapsparser-Replit-front
Environment=PYTHONPATH=/root/mapsparser-Replit-front/src
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/root/mapsparser-Replit-front/.env
ExecStart=/root/mapsparser-Replit-front/venv/bin/python /root/mapsparser-Replit-front/src/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузить systemd
systemctl daemon-reload
```

### 3. Проверить токен

```bash
grep TELEGRAM_BOT_TOKEN /root/mapsparser-Replit-front/.env
```

Должна быть строка вида: `TELEGRAM_BOT_TOKEN=1234567890:ABC...`

### 4. Проверить зависимость

```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
python -c "import telegram; print('OK')"
```

Если ошибка, установите:
```bash
pip install python-telegram-bot>=20.0
```

### 5. Запустить бота

```bash
# Включить автозапуск
systemctl enable telegram-bot

# Запустить
systemctl start telegram-bot

# Проверить статус
systemctl status telegram-bot
```

### 6. Проверить логи

```bash
journalctl -u telegram-bot -n 30
```

Должно быть:
```
🤖 Telegram-бот запущен...
✅ Бот готов к работе. Ожидаю сообщения...
```

## Если есть ошибки в логах

Покажите вывод:
```bash
journalctl -u telegram-bot -n 50
```

## Альтернатива: запуск вручную (для теста)

Если systemd не работает, можно запустить вручную для проверки:

```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/telegram_bot.py
```

Если бот запустится, увидите:
```
🤖 Telegram-бот запущен...
✅ Бот готов к работе. Ожидаю сообщения...
```

Для постоянной работы лучше использовать systemd (см. выше).

