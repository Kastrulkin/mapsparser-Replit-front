#!/bin/bash
# Скрипт для замены demyanovp@yandex.ru на demyanovap@yandex.ru на сервере

echo "🔧 Замена demyanovp@yandex.ru на demyanovap@yandex.ru..."
echo ""

# 1. Ищем и заменяем в .env файлах
echo "1️⃣ Проверяем и обновляем .env файлы..."
find /root /opt -name ".env" -type f 2>/dev/null | while read file; do
    if grep -q "demyanovp@yandex.ru" "$file" 2>/dev/null; then
        echo "   📄 Найден в: $file"
        sed -i 's/demyanovp@yandex\.ru/demyanovap@yandex.ru/g' "$file"
        echo "   ✅ Заменено в: $file"
    fi
done
echo ""

# 2. Проверяем и обновляем systemd service файлы
echo "2️⃣ Проверяем systemd service файлы..."
for service in seo-worker seo-api; do
    if systemctl cat "$service.service" 2>/dev/null | grep -q "demyanovp@yandex.ru"; then
        echo "   ⚠️  Найден в $service.service"
        echo "   📝 Нужно вручную отредактировать:"
        echo "      systemctl edit $service.service"
        echo "      Добавить: Environment=CONTACT_EMAIL=demyanovap@yandex.ru"
    fi
done
echo ""

# 3. Проверяем override файлы
echo "3️⃣ Проверяем override файлы..."
find /etc/systemd/system -name "*seo*.service.d" -type d 2>/dev/null | while read dir; do
    find "$dir" -name "*.conf" -type f 2>/dev/null | while read file; do
        if grep -q "demyanovp@yandex.ru" "$file" 2>/dev/null; then
            echo "   📄 Найден в: $file"
            sed -i 's/demyanovp@yandex\.ru/demyanovap@yandex.ru/g' "$file"
            echo "   ✅ Заменено в: $file"
        fi
    done
done
echo ""

# 3.5. Проверяем собранные файлы фронтенда (если нужно пересобрать)
echo "3.5️⃣ Проверяем собранные файлы фронтенда..."
if [ -d "/var/www/html" ]; then
    if grep -r "demyanovp@yandex.ru" /var/www/html 2>/dev/null | head -1; then
        echo "   ⚠️  Найден в собранных файлах фронтенда"
        echo "   📝 Нужно пересобрать фронтенд после замены в исходниках"
    fi
fi
if [ -d "/root/mapsparser-Replit-front/frontend/dist" ]; then
    if grep -r "demyanovp@yandex.ru" /root/mapsparser-Replit-front/frontend/dist 2>/dev/null | head -1; then
        echo "   ⚠️  Найден в локальных собранных файлах"
        echo "   📝 Нужно пересобрать фронтенд: cd frontend && npm run build"
    fi
fi
echo ""

# 4. Перезагружаем systemd и перезапускаем сервисы
echo "4️⃣ Перезагружаем systemd и перезапускаем сервисы..."
systemctl daemon-reload
systemctl restart seo-worker 2>/dev/null || echo "   ⚠️  seo-worker не найден"
systemctl restart seo-api 2>/dev/null || echo "   ⚠️  seo-api не найден"
echo ""

echo "✅ Замена завершена!"
echo ""
echo "📋 Проверка результата:"
echo "   Проверьте переменные окружения:"
echo "   systemctl show seo-worker.service | grep CONTACT_EMAIL"
echo "   systemctl show seo-api.service | grep CONTACT_EMAIL"

