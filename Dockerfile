# Этап 1: сборка фронтенда (Vite/React)
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /app/frontend
RUN npm ci --legacy-peer-deps
COPY frontend/ .
RUN npm run build

# Этап 2: backend + worker
# Базовый образ Python 3.11 на Debian bookworm (стабильный apt-канал).
FROM python:3.11-bookworm

# Системные зависимости: psycopg2 + postgresql-client для pg_isready в entrypoint
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://deb.debian.org/debian|http://mirror.yandex.ru/debian|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|http://deb.debian.org/debian|http://mirror.yandex.ru/debian|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true update \
    && apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true install -y --no-install-recommends \
    libpq-dev \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-зависимости (слой кешируется отдельно)
COPY requirements.txt .
RUN set -eux; \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=30 \
    pip install --no-cache-dir --retries 3 \
    --index-url https://mirrors.aliyun.com/pypi/simple \
    --extra-index-url https://pypi.org/simple \
    -r requirements.txt

# Playwright: браузер Chromium + системные зависимости (worker/парсинг)
# apt-get update нужен заново — выше списки пакетов удалены; после install чистим кеш
RUN apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true update \
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
