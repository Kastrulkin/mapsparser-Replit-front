# Проверка нагрузки сервера

## Команды для проверки

### 1. Проверка использования CPU и памяти
```bash
ssh root@80.78.242.105 "top -bn1 | head -20"
```

Или через веб-консоль:
```bash
top -bn1 | head -20
```

### 2. Проверка использования памяти
```bash
free -h
```

### 3. Проверка использования диска
```bash
df -h
```

### 4. Проверка процессов Python (сколько ресурсов используют)
```bash
ps aux | grep python | grep -v grep | awk '{print $2, $3"%", $4"%", $11}' | sort -k2 -rn
```

### 5. Полная диагностика одной командой
```bash
echo "=== CPU и память ===" && top -bn1 | head -5 && echo "" && echo "=== Память ===" && free -h && echo "" && echo "=== Диск ===" && df -h / && echo "" && echo "=== Python процессы ===" && ps aux | grep python | grep -v grep | awk '{print $2, $3"% CPU", $4"% MEM", $11}' | sort -k2 -rn | head -10
```

### 6. Проверка нагрузки за последние 1, 5, 15 минут
```bash
uptime
```

### 7. Проверка использования памяти процессами
```bash
ps aux --sort=-%mem | head -10
```

### 8. Проверка использования CPU процессами
```bash
ps aux --sort=-%cpu | head -10
```

### 9. Проверка размера проекта
```bash
du -sh /root/mapsparser-Replit-front
du -sh /root/mapsparser-Replit-front/* | sort -h
```

### 10. Проверка размера базы данных
```bash
ls -lh /root/mapsparser-Replit-front/src/reports.db
du -sh /root/mapsparser-Replit-front/db_backups/
```

## Интерпретация результатов

### CPU
- **0-50%** - нормально
- **50-80%** - повышенная нагрузка
- **80-100%** - критическая нагрузка

### Память (RAM)
- **< 50%** - нормально
- **50-80%** - повышенное использование
- **> 80%** - критично, возможен swap

### Диск
- **< 80%** - нормально
- **80-90%** - нужно очистить место
- **> 90%** - критично

### Load Average (uptime)
- **< количество CPU ядер** - нормально
- **= количество CPU ядер** - полная загрузка
- **> количество CPU ядер** - перегрузка

## Оптимизация при перегрузке

### 1. Остановить неиспользуемые процессы
```bash
# Найти процессы Python
ps aux | grep python | grep -v grep

# Остановить ненужные (замените PID)
kill <PID>
```

### 2. Очистить старые логи
```bash
# Проверить размер логов
du -sh /tmp/seo_*.out
du -sh /var/log/*.log

# Очистить старые логи
> /tmp/seo_main.out
> /tmp/seo_worker.out
```

### 3. Очистить старые бэкапы БД
```bash
# Проверить размер бэкапов
du -sh /root/mapsparser-Replit-front/db_backups/

# Удалить старые бэкапы (старше 30 дней)
find /root/mapsparser-Replit-front/db_backups/ -name "*.backup" -mtime +30 -delete
```

### 4. Оптимизировать базу данных
```bash
cd /root/mapsparser-Replit-front
sqlite3 src/reports.db "VACUUM;"
```

### 5. Проверить размер node_modules (если большой)
```bash
du -sh /root/mapsparser-Replit-front/frontend/node_modules
# Если очень большой (> 500MB), можно переустановить:
# cd frontend && rm -rf node_modules && npm install
```

## Мониторинг в реальном времени

### htop (если установлен)
```bash
htop
```

### watch для постоянного мониторинга
```bash
watch -n 2 'free -h && echo "" && uptime && echo "" && ps aux | grep python | grep -v grep | wc -l'
```

## Рекомендации по ресурсам

### Минимальные требования для проекта:
- **CPU**: 1-2 ядра
- **RAM**: 2-4 GB
- **Диск**: 10-20 GB

### Рекомендуемые требования:
- **CPU**: 2-4 ядра
- **RAM**: 4-8 GB
- **Диск**: 20-50 GB

### Если проект слишком большой:
1. Оптимизировать базу данных (VACUUM)
2. Удалить старые бэкапы
3. Очистить логи
4. Использовать более легкий веб-сервер (gunicorn вместо Flask dev server)
5. Рассмотреть миграцию на более мощный сервер

