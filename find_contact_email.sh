#!/bin/bash
# Скрипт для поиска, где установлен CONTACT_EMAIL на сервере

echo "🔍 Поиск переменной CONTACT_EMAIL на сервере..."
echo ""

# 1. Проверяем .env файлы
echo "1️⃣ Проверяем .env файлы:"
find /root /opt -name ".env" -type f 2>/dev/null | while read file; do
    echo "   📄 $file"
    grep -i "CONTACT_EMAIL" "$file" 2>/dev/null || echo "      (не найден)"
done
echo ""

# 2. Проверяем systemd service файлы
echo "2️⃣ Проверяем systemd service файлы:"
systemctl cat seo-worker.service 2>/dev/null | grep -i "CONTACT_EMAIL" || echo "   (не найден в seo-worker.service)"
systemctl cat seo-api.service 2>/dev/null | grep -i "CONTACT_EMAIL" || echo "   (не найден в seo-api.service)"
echo ""

# 3. Проверяем override файлы
echo "3️⃣ Проверяем systemd override файлы:"
find /etc/systemd/system -name "*seo*.service.d" -type d 2>/dev/null | while read dir; do
    echo "   📁 $dir"
    find "$dir" -name "*.conf" -type f 2>/dev/null | while read file; do
        echo "      📄 $file"
        grep -i "CONTACT_EMAIL" "$file" 2>/dev/null || echo "         (не найден)"
    done
done
echo ""

# 4. Проверяем переменные окружения запущенных процессов
echo "4️⃣ Проверяем переменные окружения запущенных процессов:"
ps aux | grep -E "python.*main\.py|python.*worker\.py" | grep -v grep | while read line; do
    pid=$(echo "$line" | awk '{print $2}')
    echo "   PID: $pid"
    cat /proc/$pid/environ 2>/dev/null | tr '\0' '\n' | grep -i "CONTACT_EMAIL" || echo "      (не найден)"
done
echo ""

echo "✅ Поиск завершен"

