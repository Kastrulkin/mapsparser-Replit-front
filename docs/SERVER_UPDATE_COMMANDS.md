# Команды для обновления проекта на сервере

## Текущий production runbook

Для `localos.pro` канонический путь проекта на сервере:

```bash
/opt/seo-app
```

Текущий runtime:

- `docker compose`
- `postgres`, `app`, `worker`
- frontend раздаётся Flask из `/app/frontend/dist`

Старые non-Docker команды и внешний web-root больше не использовать.

## Базовое обновление кода на сервере

```bash
cd /opt/seo-app
git pull origin main
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```

## Frontend-only hotfix

Собирать фронтенд лучше локально, затем выкладывать канонический `frontend/dist`.

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

Подробный runbook:

- `docs/FRONTEND_DEPLOY_RUNBOOK.md`

Важно:

- не использовать временный `tar + docker cp` как основной путь;
- не удалять старые asset-файлы перед выкладкой;
- канонический скрипт сам синхронизирует оба runtime-пути:
  - `/app/frontend/dist`
  - `/app/dist`

Проверка:

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```

## Backend-only hotfix

После синхронизации `src/` на сервер:

```bash
cd /opt/seo-app
docker compose restart app worker
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```

Если изменение касается только API, достаточно:

```bash
cd /opt/seo-app
docker compose restart app
```

## Полезные one-liners

### Проверить прод

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose ps && docker compose logs --since 10m app | tail -n 80 && curl -I http://localhost:8000"
```

### Перезапустить только app

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose restart app && docker compose ps"
```

### Проверить, какой frontend реально раздаётся

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose exec -T app sh -lc 'grep -n \"/assets/index-\" /app/frontend/dist/index.html'"
```

## Если нужно восстановить frontend runtime

```bash
cd /opt/seo-app
bash scripts/verify_frontend_dist_integrity.sh frontend/dist
docker compose exec -T app sh -lc 'grep -n "/assets/index-" /app/frontend/dist/index.html'
```

## Стандарт проверки после любого hotfix

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```
