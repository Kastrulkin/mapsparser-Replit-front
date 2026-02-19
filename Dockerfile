# Этап 1: сборка фронтенда (Vite/React)
# --platform=linux/amd64: на Mac ARM @swc/core даёт Bus error; amd64 через QEMU стабильнее
FROM --platform=linux/amd64 node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /app/frontend
RUN npm ci
COPY frontend/ .
RUN npm run build

# Этап 2: backend + worker
# Базовый образ Python 3.11 (Debian); Playwright плохо дружит с Alpine.
FROM python:3.11-slim

# Системные зависимости: psycopg2 + postgresql-client для pg_isready в entrypoint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-зависимости (слой кешируется отдельно)
# --timeout 300: при нестабильной сети pip может обрываться по умолчанию (15 сек)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# Playwright: браузер Chromium + системные зависимости (worker/парсинг)
# apt-get update нужен заново — выше списки пакетов удалены; после install чистим кеш
RUN apt-get update \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Код проекта (src, scripts, tests и т.д.). Папка scripts/ не должна быть в .dockerignore (migrate_sqlite_to_postgres.py, smoke).
COPY . .
# Подставляем собранный фронтенд из первого этапа (поле «Город» и прочие правки всегда актуальны)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Entrypoint: ждёт Postgres, выполняет flask db upgrade, затем exec CMD
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Flask CLI (flask db upgrade) нужен PYTHONPATH с /app для FLASK_APP=src.main:app; приложение — /app/src
ENV PYTHONPATH=/app:/app/src

# По умолчанию — backend; в compose переопределяем command для worker
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "src/main.py"]
