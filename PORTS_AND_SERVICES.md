# Порты и сервисы LocalOS

Канонический production runtime — Docker Compose в `/opt/seo-app`. Источники истины: [README.md](./README.md), [AGENTS.md](./AGENTS.md) и текущий `docker compose config`.

## Runtime-схема

| Сервис | Доступ | Назначение |
|---|---|---|
| Nginx | `80/443` | HTTPS, статический frontend и reverse proxy |
| `app` | host `8000` | Flask/Gunicorn API |
| `worker` | без внешнего порта | Очереди, фоновые проверки и supervised automation |
| `telegram-bot` | без внешнего порта | Telegram polling внутри Compose |
| `postgres` | только Docker-сеть `5432` | Каноническая PostgreSQL-БД |
| `redis` | только Docker-сеть `6379` | Очереди и runtime-состояние |
| Vite dev server | local `3000` | Локальная frontend-разработка |

SQLite и host-level systemd-боты не являются production runtime. Не запускайте второй Telegram polling-процесс с тем же токеном.

## Обязательная production-проверка

Все серверные команды выполняются из `/opt/seo-app`:

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app
docker compose logs --since 10m worker
docker compose logs --since 10m telegram-bot
curl -I http://localhost:8000
curl -I https://localos.pro
```

Ожидаемый результат:

- `app`, `worker`, `telegram-bot`, `postgres` и `redis` запущены;
- PostgreSQL и Redis healthy;
- локальный API и `https://localos.pro` отвечают;
- в свежих логах нет новых traceback и повторяющихся критических ошибок.

## Управление сервисами

```bash
cd /opt/seo-app
docker compose restart app worker
docker compose restart telegram-bot
docker compose logs -f app worker telegram-bot
```

Полный rebuild применяется только при изменении образа, системных пакетов или зависимостей. Backend-код и миграции обновляются частично; frontend публикуется из проверенных `frontend/dist` и `frontend/public-dist` по правилам [AGENTS.md](./AGENTS.md).

## Локальная разработка

```bash
cd frontend
npm ci
npm run dev
```

Frontend dev server по умолчанию доступен на `http://localhost:3000`. Backend запускается через Docker Compose и публикуется на `http://localhost:8000`.

## Сетевая граница

```text
Интернет
  └─ Nginx :80/:443
       ├─ frontend
       └─ /api → app :8000
                    ├─ postgres :5432
                    ├─ redis :6379
                    └─ внешние провайдеры

telegram-bot ─ Telegram polling
worker       ─ очереди и фоновые задачи
```

PostgreSQL и Redis не должны публиковаться наружу. Telegram polling не требует входящего порта.
