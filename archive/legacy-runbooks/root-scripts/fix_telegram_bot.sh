#!/bin/bash
# ============================================
# Скрипт быстрого исправления Telegram-бота
# ============================================

set -e

echo "🔧 Исправляю Telegram-бот..."

cd /root/mapsparser-Replit-front || { echo "❌ Директория не найдена!"; exit 1; }

# 1. Проверяем процесс
echo "1️⃣ Проверяю, запущен ли бот..."
if pgrep -f "telegram_bot.py" > /dev/null; then
    echo "   ✅ Бот уже запущен (PID: $(pgrep -f 'telegram_bot.py'))"
    echo "   💡 Если бот не отвечает, перезапустите: systemctl restart telegram-bot"
else
    echo "   ⚠️  Бот не запущен"
    
    # 2. Проверяем systemd сервис
    echo "2️⃣ Проверяю systemd сервис..."
    if [ ! -f /etc/systemd/system/telegram-bot.service ]; then
        echo "   ⚠️  Сервис не найден. Создаю..."
        cp telegram-bot.service /etc/systemd/system/
        systemctl daemon-reload
        echo "   ✅ Сервис создан"
    else
        echo "   ✅ Сервис найден"
    fi
    
    # 3. Проверяем токен
    echo "3️⃣ Проверяю токен..."
    if [ -f .env ] && grep -q "TELEGRAM_BOT_TOKEN=" .env; then
        TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs)
        if [ -z "$TOKEN" ] || [ "$TOKEN" == "" ]; then
            echo "   ❌ Токен пустой в .env!"
            echo "   💡 Добавьте токен в .env: TELEGRAM_BOT_TOKEN=ваш_токен"
            exit 1
        else
            echo "   ✅ Токен найден"
        fi
    else
        echo "   ❌ Токен не найден в .env!"
        echo "   💡 Добавьте токен в .env: TELEGRAM_BOT_TOKEN=ваш_токен"
        exit 1
    fi
    
    # 4. Проверяем зависимость
    echo "4️⃣ Проверяю зависимость..."
    source venv/bin/activate
    if ! python -c "import telegram" 2>/dev/null; then
        echo "   ⚠️  Зависимость не установлена. Устанавливаю..."
        pip install -q python-telegram-bot>=20.0
        echo "   ✅ Зависимость установлена"
    else
        echo "   ✅ Зависимость установлена"
    fi
    
    # 5. Запускаем бота
    echo "5️⃣ Запускаю бота..."
    systemctl enable telegram-bot 2>/dev/null || true
    systemctl start telegram-bot
    sleep 2
    
    # 6. Проверяем статус
    echo "6️⃣ Проверяю статус..."
    if systemctl is-active --quiet telegram-bot; then
        echo "   ✅ Бот запущен успешно!"
    else
        echo "   ❌ Бот не запустился. Проверьте логи:"
        echo "   journalctl -u telegram-bot -n 20"
        exit 1
    fi
fi

# 7. Показываем логи
echo ""
echo "📋 Последние логи бота:"
journalctl -u telegram-bot -n 15 --no-pager 2>/dev/null || echo "   (логи недоступны, возможно бот запущен не через systemd)"

echo ""
echo "✅ Готово! Бот должен работать."
echo ""
echo "💡 Полезные команды:"
echo "   - Статус: systemctl status telegram-bot"
echo "   - Логи: journalctl -u telegram-bot -f"
echo "   - Перезапуск: systemctl restart telegram-bot"

