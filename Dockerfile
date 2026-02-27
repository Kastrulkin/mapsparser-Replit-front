# Этап 1: сборка фронтенда (Vite/React)
# --platform=linux/amd64: на Mac ARM @swc/core даёт Bus error; amd64 через QEMU стабильнее
FROM --platform=linux/amd64 node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /app/frontend
RUN npm ci --legacy-peer-deps
COPY frontend/ .
RUN npm run build

# Этап 2: backend + worker
# Базовый образ Python 3.11 (Debian); Playwright плохо дружит с Alpine.
FROM python:3.11-bookworm

# Системные зависимости: psycopg2 + postgresql-client для pg_isready в entrypoint
# Сеть на сервере может быть нестабильной, поэтому используем retry+backoff и fallback по зеркалам apt.
RUN set -eux; \
    printf 'Acquire::Retries "10";\nAcquire::ForceIPv4 "true";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' > /etc/apt/apt.conf.d/99network-retries; \
    if [ -f /etc/apt/sources.list ]; then cp /etc/apt/sources.list /etc/apt/sources.list.bak; fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.bak; fi; \
    mirrors='mirror.yandex.ru/debian ftp.debian.org deb.debian.org'; \
    updated=0; \
    for mirror in $mirrors; do \
      if [ -f /etc/apt/sources.list.bak ]; then cp /etc/apt/sources.list.bak /etc/apt/sources.list; fi; \
      if [ -f /etc/apt/sources.list.d/debian.sources.bak ]; then cp /etc/apt/sources.list.d/debian.sources.bak /etc/apt/sources.list.d/debian.sources; fi; \
      case "$mirror" in \
        mirror.yandex.ru/debian) \
          if [ -f /etc/apt/sources.list ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list; fi; \
          if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list.d/debian.sources; fi \
          ;; \
        *) \
          if [ -f /etc/apt/sources.list ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}/debian|g; s|http://deb.debian.org/debian-security|http://${mirror}/debian-security|g" /etc/apt/sources.list; fi; \
          if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}/debian|g; s|http://deb.debian.org/debian-security|http://${mirror}/debian-security|g" /etc/apt/sources.list.d/debian.sources; fi \
          ;; \
      esac; \
      for n in 1 2 3; do \
        if timeout 120 apt-get update; then updated=1; break; fi; \
        echo "apt-get update failed via ${mirror} (attempt ${n}), retrying..." >&2; \
        sleep "$((n*5))"; \
      done; \
      [ "$updated" -eq 1 ] && break; \
    done; \
    [ "$updated" -eq 1 ] || exit 1; \
    apt-get install -y --no-install-recommends \
      libpq-dev \
      gcc \
      postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-зависимости (слой кешируется отдельно)
# Добавлен fallback по PyPI-индексам и повторные попытки для нестабильной сети.
COPY requirements.txt .
RUN set -eux; \
    indexes='https://pypi.org/simple https://pypi.tuna.tsinghua.edu.cn/simple https://mirrors.aliyun.com/pypi/simple'; \
    installed=0; \
    for idx in $indexes; do \
      for n in 1 2 3; do \
        if PIP_DEFAULT_TIMEOUT=300 pip install --no-cache-dir --retries 10 --index-url "$idx" -r requirements.txt; then installed=1; break; fi; \
        echo "pip install failed via ${idx} (attempt ${n}), retrying..." >&2; \
        sleep "$((n*5))"; \
      done; \
      [ "$installed" -eq 1 ] && break; \
    done; \
    [ "$installed" -eq 1 ] || exit 1

# Playwright: браузер Chromium + системные зависимости (worker/парсинг)
# apt-get update нужен заново — выше списки пакетов удалены; после install чистим кеш.
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then cp /etc/apt/sources.list /etc/apt/sources.list.bak; fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.bak; fi; \
    mirrors='mirror.yandex.ru/debian ftp.debian.org deb.debian.org'; \
    updated=0; \
    for mirror in $mirrors; do \
      if [ -f /etc/apt/sources.list.bak ]; then cp /etc/apt/sources.list.bak /etc/apt/sources.list; fi; \
      if [ -f /etc/apt/sources.list.d/debian.sources.bak ]; then cp /etc/apt/sources.list.d/debian.sources.bak /etc/apt/sources.list.d/debian.sources; fi; \
      case "$mirror" in \
        mirror.yandex.ru/debian) \
          if [ -f /etc/apt/sources.list ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list; fi; \
          if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}|g; s|http://deb.debian.org/debian-security|http://mirror.yandex.ru/debian-security|g" /etc/apt/sources.list.d/debian.sources; fi \
          ;; \
        *) \
          if [ -f /etc/apt/sources.list ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}/debian|g; s|http://deb.debian.org/debian-security|http://${mirror}/debian-security|g" /etc/apt/sources.list; fi; \
          if [ -f /etc/apt/sources.list.d/debian.sources ]; then sed -i "s|http://deb.debian.org/debian|http://${mirror}/debian|g; s|http://deb.debian.org/debian-security|http://${mirror}/debian-security|g" /etc/apt/sources.list.d/debian.sources; fi \
          ;; \
      esac; \
      for n in 1 2 3; do \
        if timeout 120 apt-get update; then updated=1; break; fi; \
        echo "apt-get update failed via ${mirror} (attempt ${n}), retrying..." >&2; \
        sleep "$((n*5))"; \
      done; \
      [ "$updated" -eq 1 ] && break; \
    done; \
    [ "$updated" -eq 1 ] || exit 1; \
    python -m playwright install --with-deps chromium \
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
