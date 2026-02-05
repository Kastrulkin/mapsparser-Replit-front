# Локальная разработка

## Установка зависимостей

### Базовая установка (Web API)
```zsh
source venv/bin/activate
pip install -r requirements.web.txt
```

### Установка для Worker (включает Web + Playwright)
```zsh
source venv/bin/activate
pip install -r requirements.worker.txt
python3 -m playwright install chromium
```

### Дополнительные LLM зависимости (опционально)
```zsh
source venv/bin/activate
pip install -r requirements.extras-llm.txt
```

## Полный локальный перезапуск

### 1. Остановка всех сервисов
```zsh
./scripts/stop_local.sh
```

### 2. Проверка синтаксиса
```zsh
python3 -m py_compile src/main.py src/yandex_sync_service.py
```

### 3. Запуск сервисов (каждый в отдельном терминале)

**Терминал 1 — Web API (через venv):**
```zsh
cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре"
source venv/bin/activate
python3 src/main.py
```

**Терминал 2 — Worker (через venv):**
```zsh
cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре"
source venv/bin/activate
python3 src/worker.py
```

**Терминал 3 — Frontend:**
```zsh
cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/frontend"
npm run dev
```

## Быстрый рестарт

```zsh
./scripts/stop_local.sh && ./scripts/run_web.sh
```

## Проверка состояния

```zsh
./scripts/check_health.sh
```

## Устранение проблем

### ModuleNotFoundError

Если видите `ModuleNotFoundError` — проверьте, что используете правильный интерпретатор:

```zsh
which python3
# Должно быть: .../venv/bin/python3

# Если нет — активируйте venv:
source venv/bin/activate
which python3
```

### Порт занят

Если порт 8000 или 3000 занят:

```zsh
# Проверка
lsof -iTCP:8000
lsof -iTCP:3000

# Остановка
./scripts/stop_local.sh
```

### Worker не запускается

Проверьте:
1. Установлен ли Playwright: `pip list | grep playwright`
2. Установлен ли браузер: `python3 -m playwright install chromium`
3. Есть ли файл `.pids/worker.pid` (должен создаваться автоматически)

## Структура зависимостей

- **requirements.web.txt** — базовые зависимости для Web API
- **requirements.worker.txt** — включает web + playwright (для парсинга)
- **requirements.extras-llm.txt** — опциональные LLM зависимости
- **requirements.txt** — старый файл (сохранен для совместимости)

## Примечания

- Все скрипты используют `zsh` и учитывают пробелы в пути проекта
- Worker использует polling по БД (без Celery/Redis)
- Скрипты не убивают "чужие" python-процессы (только процессы на портах 8000/3000)
- PID worker'а сохраняется в `.pids/worker.pid` для безопасной остановки
