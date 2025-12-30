# Очистка ненужных файлов на сервере

## Проблема
Проект занимает 5.8GB, что слишком много. Нужно почистить временные файлы.

## Что можно безопасно удалить

### 1. Python кеши (__pycache__, *.pyc)
```bash
find /root/mapsparser-Replit-front -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /root/mapsparser-Replit-front -type f -name "*.pyc" -delete 2>/dev/null
```

### 2. Старые бэкапы БД (оставить только последние 5)
```bash
cd /root/mapsparser-Replit-front/db_backups
ls -t *.backup 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
```

### 3. Логи
```bash
> /tmp/seo_main.out
> /tmp/seo_worker.out
find /root/mapsparser-Replit-front -name "*.log" -delete 2>/dev/null
```

### 4. Кеши npm
```bash
cd /root/mapsparser-Replit-front/frontend
rm -rf node_modules/.cache
rm -rf .vite
npm cache clean --force
```

### 5. Временные файлы
```bash
cd /root/mapsparser-Replit-front
rm -f test_*.json
rm -f tmp
```

## Автоматическая очистка

Используйте готовый скрипт:

```bash
cd /root/mapsparser-Replit-front
bash scripts/cleanup_server_files.sh
```

Или если скрипта нет на сервере, выполните команды вручную:

```bash
cd /root/mapsparser-Replit-front && \
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null && \
find . -type f -name "*.pyc" -delete 2>/dev/null && \
cd db_backups && ls -t *.backup 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null && \
cd .. && > /tmp/seo_main.out && > /tmp/seo_worker.out && \
cd frontend && rm -rf node_modules/.cache .vite && \
cd .. && echo "✅ Очистка завершена" && du -sh .
```

## Проверка размера после очистки

```bash
du -sh /root/mapsparser-Replit-front
du -sh /root/mapsparser-Replit-front/* | sort -h
```

## Что НЕ удалять

- ❌ `src/reports.db` - база данных
- ❌ `.env` - переменные окружения
- ❌ `frontend/dist/` - собранный фронтенд
- ❌ `venv/` - виртуальное окружение Python
- ❌ `node_modules/` - зависимости фронтенда (можно переустановить, но не удалять без необходимости)

## Если node_modules очень большой

Если `node_modules` занимает > 500MB, можно переустановить:

```bash
cd /root/mapsparser-Replit-front/frontend
rm -rf node_modules
npm install --production
```

## Оптимизация базы данных

Если БД большая, можно оптимизировать:

```bash
cd /root/mapsparser-Replit-front
sqlite3 src/reports.db "VACUUM;"
```

## Ожидаемый результат

После очистки проект должен занимать:
- **Локально**: ~300-500MB (без node_modules и venv)
- **На сервере**: ~1-2GB (с node_modules и venv)

Если больше - проверьте, что именно занимает место.

