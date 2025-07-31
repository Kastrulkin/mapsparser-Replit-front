#!/bin/bash

# Скрипт для обновления конфигурации Nginx на сервере
# Добавляет поддержку отчётов по адресу /reports/

echo "🔄 Обновление конфигурации Nginx..."

# Создаём резервную копию
echo "📦 Создание резервной копии..."
cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup.$(date +%Y%m%d_%H%M%S)

# Копируем новую конфигурацию
echo "📝 Копирование новой конфигурации..."
cp nginx-config.conf /etc/nginx/sites-available/default

# Проверяем конфигурацию
echo "🔍 Проверка конфигурации..."
if nginx -t; then
    echo "✅ Конфигурация корректна!"
    
    # Перезагружаем Nginx
    echo "🔄 Перезагрузка Nginx..."
    systemctl reload nginx
    
    if [ $? -eq 0 ]; then
        echo "✅ Nginx успешно перезагружен!"
        echo "🎉 Отчёты теперь доступны по адресу:"
        echo "   https://beautybot.pro/reports/view-report/{id}"
    else
        echo "❌ Ошибка при перезагрузке Nginx!"
        exit 1
    fi
else
    echo "❌ Ошибка в конфигурации Nginx!"
    echo "🔄 Восстановление резервной копии..."
    cp /etc/nginx/sites-available/default.backup.* /etc/nginx/sites-available/default
    exit 1
fi

echo "✨ Готово!" 