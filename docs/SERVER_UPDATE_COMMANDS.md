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
- при ручном `rsync` для `frontend/dist/assets` не использовать `--delete`, иначе у пользователей со старым cached entry chunk будут 404 на lazy-loaded модулях вроде `About-*.js`;
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

Канонический способ backend-hotfix теперь такой:

```bash
cd /opt/seo-app
bash scripts/deploy_backend_src.sh
```

Что делает скрипт:

- синхронизирует весь `src/`, а не отдельные Python-файлы;
- синхронизирует `alembic_migrations/` и `entrypoint.sh`;
- пересоздаёт только `app` и `worker`, чтобы новые runtime mounts тоже применились;
- проверяет live runtime-файл внутри контейнера (`/app/src/...`).

Почему это важно:

- `app` и `worker` теперь bind-mount'ят `./src -> /app/src`;
- это убирает drift, когда контейнер жил на неполной внутренней копии backend-кода;
- backend deploy теперь обновляет source of truth целиком, а не кусками.

Перед backend-релизом полезно отдельно проверить, не участвуют ли в runtime untracked-файлы:

```bash
cd /opt/seo-app
bash scripts/check_backend_source_of_truth.sh
```

Если нужно быстро снять server-side drift со своей локальной машины:

```bash
bash scripts/check_server_backend_source_of_truth.sh
```

Скрипт:

- подключается к `root@80.78.242.105` с каноническим ключом `~/.ssh/localos_prod`;
- выставляет `safe.directory` для `/opt/seo-app`;
- показывает branch status, `HEAD` vs `origin/main`, backend source-of-truth check и счётчики runtime drift.

Если скрипт ругается, это означает:

- часть backend-кода уже влияет на runtime;
- но Git ещё не считает её каноническим source of truth.

`deploy_backend_src.sh` не блокирует релиз в этом случае, но явно печатает предупреждение.

Если перед cleanup нужен безопасный backup грязного server tree:

```bash
bash scripts/backup_server_dirty_tree.sh
```

Скрипт:

- подключается к `root@80.78.242.105` с ключом `~/.ssh/localos_prod`;
- всегда работает из `/opt/seo-app`;
- сохраняет в `/opt/seo-app/backups/git-drift-YYYYmmdd_HHMMSS/`:
  - `git-status.txt`
  - `head.txt`
  - `origin-main.txt`
  - `git-diff.patch`
  - `untracked.txt`
  - `runtime-dirty-tree.tgz`

Важно:

- при `behind` на сотни коммитов и большом количестве `UNTRACKED/MODIFIED` не делать `git clean/reset` по умолчанию;
- сначала снять backup и drift-audit, потом отдельно принять решение, допустим ли controlled reset.

Если нужен безопасный parallel checkout рядом с live-tree:

```bash
bash scripts/create_server_parallel_checkout.sh
```

Скрипт:

- создаёт чистый checkout `origin/main` в `/opt/seo-app-parallel/origin-main-YYYYmmdd_HHMMSS`;
- делает это в отдельной `tmux`-сессии `parallel_checkout`;
- не трогает live `/opt/seo-app`.

Чтобы снять controlled compare между live-tree и чистым checkout:

```bash
bash scripts/check_server_parallel_checkout_diff.sh
```

Он показывает:

- путь к последнему clean checkout;
- количество различий по:
  - `src/`
  - `alembic_migrations/`
  - `docker-compose.yml`
- примеры diff по backend и migrations.

Это канонический safe migration path для server git cleanup:

1. backup dirty tree;
2. parallel checkout;
3. controlled compare;
4. только после этого решать, допустим ли перенос live на чистый git state.

Если нужно сделать первый безопасный cleanup-pass без риска для live runtime:

```bash
bash scripts/quarantine_server_runtime_drift.sh
```

Скрипт:

- работает из `/opt/seo-app`;
- не делает `git clean/reset`;
- переносит в quarantine только:
  - `* (2).py`
  - `__pycache__`
- складывает всё в:
  - `/opt/seo-app/backups/runtime-quarantine-YYYYmmdd_HHMMSS`

Это допустимый первый cleanup-pass, потому что:

- убирает явный мусор из runtime-tree;
- не трогает живые backend-модули;
- сохраняет возможность отката через quarantine-каталог.

Если нужно сделать второй безопасный cleanup-pass уже по non-runtime хвостам:

```bash
bash scripts/quarantine_server_nonruntime_leftovers.sh
```

Скрипт:

- работает из `/opt/seo-app`;
- не делает `git clean/reset`;
- переносит в quarantine только безопасные non-runtime leftovers верхнего уровня:
  - `.codex_tmp`
  - `.env.bak*`
  - `docker-compose.yml.bak.*`
  - `*.tgz`
  - `tmp_*`
  - `tmp_*.log`
  - `tmp_sync/`
  - `tmp_app_versions/`
  - `tmp_cardauto_upload/`
  - stray-файл `name`
- складывает всё в:
  - `/opt/seo-app/backups/nonruntime-quarantine-YYYYmmdd_HHMMSS`

Это допустимый второй cleanup-pass, потому что:

- убирает архивы, временные прогоны и backup-хвосты, которые не участвуют в Docker runtime;
- не трогает `/opt/seo-app/src`, `alembic_migrations/`, `runtime_bot/` и `telegram-bot-venv/`;
- сохраняет возможность отката через quarantine-каталог.

Если нужно сделать третий cleanup-pass по safe second-order leftovers:

```bash
bash scripts/quarantine_server_second_order_leftovers.sh
```

Скрипт:

- работает из `/opt/seo-app`;
- не делает `git clean/reset`;
- переносит в quarantine только generated/non-runtime artifacts второго порядка верхнего уровня:
  - `build_app.log`
  - `frontend_build.log`
  - `oliver_result.json`
  - `test_parser_result*.json`
  - `waterland_*.sql`
  - `schema_local.sql`
  - каталоги `logs/`, `reports/`, `assets/`
- складывает всё в:
  - `/opt/seo-app/backups/second-order-quarantine-YYYYmmdd_HHMMSS`

Это допустимый cleanup-pass, потому что:

- убирает generated artifacts и разовые результатные файлы, которые не участвуют в Docker runtime;
- не трогает backend-код, migrations, host Telegram runtime и server backups;
- сохраняет возможность отката через quarantine-каталог.

Если нужно только перезапустить сервисы после уже выполненной синхронизации:

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
