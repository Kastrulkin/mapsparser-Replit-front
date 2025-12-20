# 🚀 Быстрый запуск Telegram-бота на сервере

## Что нужно сделать:

### 1. Установить зависимость (если не установлена)

```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
pip install python-telegram-bot>=20.0
```

### 2. Добавить токен в .env

```bash
# Откройте .env файл
nano /root/mapsparser-Replit-front/.env

# Добавьте строку (замените на ваш токен от @BotFather):
TELEGRAM_BOT_TOKEN=ваш_токен_здесь
```

### 3. Установить systemd сервис

```bash
# Скопируйте файл сервиса
cp /root/mapsparser-Replit-front/telegram-bot.service /etc/systemd/system/

# Перезагрузите systemd
systemctl daemon-reload

# Включите автозапуск
systemctl enable telegram-bot

# Запустите бота
systemctl start telegram-bot
```

### 4. Проверить работу

```bash
# Проверьте статус
systemctl status telegram-bot

# Должно быть: "active (running)"

# Проверьте логи
journalctl -u telegram-bot -n 20

# Должно быть:
# 🤖 Telegram-бот запущен...
# ✅ Бот готов к работе. Ожидаю сообщения...
```

## 🔍 Если что-то не работает:

Используйте скрипт проверки:
```bash
bash /root/mapsparser-Replit-front/check_telegram_bot.sh
```

Или смотрите подробную инструкцию:
```bash
cat /root/mapsparser-Replit-front/TELEGRAM_BOT_TROUBLESHOOTING.md
```

## 📋 Полезные команды:

```bash
# Перезапустить бота
systemctl restart telegram-bot

# Остановить бота
systemctl stop telegram-bot

# Просмотр логов в реальном времени
journalctl -u telegram-bot -f

# Последние 50 строк логов
journalctl -u telegram-bot -n 50
```

## ⚠️ Важно:

1. **Токен** должен быть получен от [@BotFather](https://t.me/BotFather)
2. **API сервер** (`main.py`) должен быть запущен
3. **База данных** должна быть доступна
4. Для работы с фото нужен **GigaChat API** (опционально)

