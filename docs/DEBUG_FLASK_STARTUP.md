# Диагностика проблем запуска Flask

## Проблема
Flask не запускается или падает сразу после запуска.

## Диагностика

### 1. Проверить логи на ошибки
```bash
ssh root@80.78.242.105 "tail -50 /tmp/seo_main.out"
```

### 2. Запустить Flask синхронно (увидеть ошибки)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && timeout 10 python src/main.py 2>&1"
```

### 3. Проверить зависимости
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && python -c 'import flask; import sqlite3; print(\"✅ Основные зависимости OK\")'"
```

### 4. Проверить импорты
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && python -c 'from src.main import app; print(\"✅ Импорт OK\")' 2>&1"
```

### 5. Проверить базу данных
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && ls -la src/reports.db 2>&1"
```

## Типичные ошибки

### ImportError
- Не установлены зависимости: `pip install -r requirements.txt`

### DatabaseError
- Проблема с базой данных: проверить права доступа

### Port already in use
- Порт 8000 занят: `lsof -iTCP:8000` и убить процесс

### ModuleNotFoundError
- Отсутствует модуль: проверить импорты в main.py

## Полная диагностика одной командой
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && echo '=== Логи ===' && tail -30 /tmp/seo_main.out 2>&1 && echo '' && echo '=== Зависимости ===' && source venv/bin/activate && python -c 'import flask, sqlite3; print(\"OK\")' 2>&1 && echo '' && echo '=== Импорт ===' && python -c 'import sys; sys.path.insert(0, \"src\"); from main import app; print(\"OK\")' 2>&1 | head -20"
```

