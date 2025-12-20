#!/bin/bash
# ============================================
# Скрипт проверки и запуска Telegram-бота
# ============================================

echo "🔍 Проверяю Telegram-бот..."

# Переходим в директорию проекта
cd /root/mapsparser-Replit-front || { echo "❌ Директория не найдена!"; exit 1; }

# 1. Проверяем наличие зависимости
echo "📦 Проверяю зависимость python-telegram-bot..."
source venv/bin/activate
if ! python -c "import telegram" 2>/dev/null; then
    echo "⚠️  Зависимость не установлена. Устанавливаю..."
    pip install python-telegram-bot>=20.0
    echo "✅ Зависимость установлена"
else
    echo "✅ Зависимость установлена"
fi

# 2. Проверяем наличие токена
echo "🔑 Проверяю токен TELEGRAM_BOT_TOKEN..."
if [ -f .env ]; then
    if grep -q "TELEGRAM_BOT_TOKEN=" .env; then
        TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        if [ -z "$TOKEN" ] || [ "$TOKEN" == "" ]; then
            echo "❌ Токен не установлен в .env файле!"
            echo "💡 Добавьте строку: TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather"
            exit 1
        else
            echo "✅ Токен найден в .env"
        fi
    else
        echo "❌ TELEGRAM_BOT_TOKEN не найден в .env файле!"
        echo "💡 Добавьте строку: TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather"
        exit 1
    fi
else
    echo "❌ Файл .env не найден!"
    echo "💡 Создайте файл .env с токеном: TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather"
    exit 1
fi

# 3. Проверяем, запущен ли бот
echo "🤖 Проверяю, запущен ли бот..."
if pgrep -f "telegram_bot.py" > /dev/null; then
    echo "✅ Бот уже запущен (PID: $(pgrep -f 'telegram_bot.py'))"
    echo "💡 Для перезапуска выполните: systemctl restart telegram-bot"
else
    echo "⚠️  Бот не запущен"
    
    # 4. Проверяем наличие systemd сервиса
    if [ -f /etc/systemd/system/telegram-bot.service ]; then
        echo "✅ Systemd сервис найден"
        echo "💡 Запустите бота: systemctl start telegram-bot"
        echo "💡 Или включите автозапуск: systemctl enable telegram-bot && systemctl start telegram-bot"
    else
        echo "⚠️  Systemd сервис не найден"
        echo "💡 Создайте сервис:"
        echo "   1. Скопируйте telegram-bot.service в /etc/systemd/system/"
        echo "   2. Выполните: systemctl daemon-reload"
        echo "   3. Выполните: systemctl enable telegram-bot"
        echo "   4. Выполните: systemctl start telegram-bot"
    fi
fi

# 5. Проверяем логи (если запущен как сервис)
if systemctl is-active --quiet telegram-bot 2>/dev/null; then
    echo ""
    echo "📋 Последние логи бота:"
    journalctl -u telegram-bot -n 10 --no-pager
fi

echo ""
echo "✅ Проверка завершена"

