# 🚨 СРОЧНО: Применить миграцию вручную на сервере

## Проблема
Скрипт не смог применить миграцию из-за `python: command not found`. Нужно применить миграцию вручную.

## Решение (выполнить на сервере)

```bash
# 1. Подключиться к серверу
ssh root@80.78.242.105

# 2. Перейти в директорию проекта
cd /root/mapsparser-Replit-front

# 3. Активировать виртуальное окружение
source venv/bin/activate

# 4. Создать бэкап БД
python src/safe_db_utils.py
# Или вручную:
cp src/reports.db db_backups/reports_$(date +%Y%m%d_%H%M%S).db.backup

# 5. Применить миграцию
python src/migrate_clientinfo_add_business_id.py

# 6. Проверить структуру таблицы
python -c "
import sqlite3
conn = sqlite3.connect('src/reports.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(ClientInfo)')
columns = [col[1] for col in cursor.fetchall()]
print('Колонки в ClientInfo:', columns)
if 'business_id' in columns:
    print('✅ Колонка business_id существует!')
else:
    print('❌ Колонка business_id НЕ найдена!')
conn.close()
"

# 7. Перезапустить Flask API (если нужно)
systemctl restart seo-worker

# 8. Проверить логи
journalctl -u seo-worker -n 20 --no-pager

# 9. Проверить API
curl -s http://localhost:8000/ | head -c 100
```

## Проверка после применения

1. Откройте браузер: http://beautybot.pro
2. Войдите в систему
3. Откройте консоль браузера (F12)
4. Проверьте, что ошибка `no such column: business_id` исчезла

