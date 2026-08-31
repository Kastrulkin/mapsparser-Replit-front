# Этап 1: сборка фронтенда (Vite/React)
FROM node:20-slim AS frontend-builder
ARG VITE_PROMOTION_HUB_ENABLED=false
ARG VITE_CONTENT_JOURNEY_ENABLED=false
ARG VITE_JOURNEY_ADMIN_BUILDER_ENABLED=false
ARG VITE_JOURNEY_POST_AUTH_REDIRECT_ENABLED=false
ARG VITE_GROWTH_PATHS_NAVIGATION_ENABLED=true
ARG VITE_BLOCK_ACCESS_V2_ENABLED=false
ARG VITE_BROWSER_COOKIE_AUTH_ENABLED=false
ENV VITE_PROMOTION_HUB_ENABLED=${VITE_PROMOTION_HUB_ENABLED}
ENV VITE_CONTENT_JOURNEY_ENABLED=${VITE_CONTENT_JOURNEY_ENABLED}
ENV VITE_JOURNEY_ADMIN_BUILDER_ENABLED=${VITE_JOURNEY_ADMIN_BUILDER_ENABLED}
ENV VITE_JOURNEY_POST_AUTH_REDIRECT_ENABLED=${VITE_JOURNEY_POST_AUTH_REDIRECT_ENABLED}
ENV VITE_GROWTH_PATHS_NAVIGATION_ENABLED=${VITE_GROWTH_PATHS_NAVIGATION_ENABLED}
ENV VITE_BLOCK_ACCESS_V2_ENABLED=${VITE_BLOCK_ACCESS_V2_ENABLED}
ENV VITE_BROWSER_COOKIE_AUTH_ENABLED=${VITE_BROWSER_COOKIE_AUTH_ENABLED}
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /app/frontend
RUN npm ci --legacy-peer-deps
COPY frontend/ .
RUN npm run build

# Этап 2: backend + worker
# Базовый образ Python 3.11 на Debian bookworm (стабильный apt-канал).
FROM python:3.11-bookworm

ARG INSTALL_PLAYWRIGHT_BROWSER=true

# Keep the runtime identity stable across app, worker and Telegram images. The
# host-side writable directories must use the same UID/GID when bind-mounted.
ARG LOCALOS_UID=10001
ARG LOCALOS_GID=10001

# Системные зависимости: psycopg2 + postgresql-client для pg_isready в entrypoint
RUN set -eux; \
    apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true update \
    && apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true install -y --no-install-recommends \
    libpq-dev \
    gcc \
    postgresql-client \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libegl1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
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

# Keep packaging tooling out of known-vulnerable ranges reported by the image
# scanner. These packages are not runtime application dependencies, but remain
# present in the final Python image and therefore must be patched as well.
RUN set -eux; \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=30 \
    pip install --no-cache-dir --retries 3 \
    --index-url https://mirrors.aliyun.com/pypi/simple \
    --extra-index-url https://pypi.org/simple \
    "setuptools==84.0.0" \
    "wheel==0.48.0"

# Production workers may need the bundled browser; host-driven staging E2E does not.
# A shared path keeps Chromium readable after the process drops root privileges.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN if [ "$INSTALL_PLAYWRIGHT_BROWSER" = "true" ]; then python -m playwright install chromium; fi

RUN set -eux; \
    groupadd --gid "${LOCALOS_GID}" localos \
    && useradd --uid "${LOCALOS_UID}" --gid "${LOCALOS_GID}" \
      --create-home --home-dir /home/localos --shell /usr/sbin/nologin localos

# Код проекта (src, scripts, tests и т.д.). Папка scripts/ не должна быть в .dockerignore (migrate_sqlite_to_postgres.py, smoke).
COPY . .
# Подставляем собранный фронтенд из первого этапа (поле «Город» и прочие правки всегда актуальны)
COPY --chown=localos:localos --from=frontend-builder /app/frontend/dist ./frontend/dist

# Entrypoint: ждёт Postgres, выполняет flask db upgrade, затем exec CMD
COPY entrypoint.sh /app/entrypoint.sh
RUN set -eux; \
    chmod +x /app/entrypoint.sh \
    && mkdir -p /app/debug_data /app/uploads /home/localos/.cache /ms-playwright \
    && chown -R localos:localos /app/debug_data /app/uploads /home/localos /ms-playwright

# Flask CLI (flask db upgrade) нужен PYTHONPATH с /app для FLASK_APP=src.main:app; приложение — /app/src
ENV PYTHONPATH=/app:/app/src
ENV HOME=/home/localos
ENV XDG_CACHE_HOME=/home/localos/.cache

USER localos:localos

# По умолчанию — backend; в compose переопределяем command для worker
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "src/main.py"]
