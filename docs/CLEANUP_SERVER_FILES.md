# Очистка серверных файлов

Этот документ описывает безопасную очистку файлов на текущем runtime-стеке.

## Канонические пути

- Хостовый frontend dist: `/opt/seo-app/frontend/dist`
- Runtime path в `app` container: `/app/frontend/dist`
- Продовая раздача `localos.pro`: через Flask `127.0.0.1:8000`, который читает именно `/app/frontend/dist`

## Что считать legacy

Эти каталоги не должны быть источником правды для продового фронтенда:

- `/opt/seo-app/dist`
- `/opt/seo-app/tmp_frontend_dist`
- `/opt/seo-app/tmp_frontend_dist_fix`
- старый внешний web-root вне Docker runtime
- любые старые каталоги вида `mapsparser-Replit-front/...`

## Что можно безопасно удалять

```bash
cd /opt/seo-app
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null
find . -type f -name "*.log" -delete 2>/dev/null
rm -f /tmp/seo_main.out /tmp/seo_worker.out 2>/dev/null || true
```

## Что НЕ удалять

- `/opt/seo-app/frontend/dist`
- `/opt/seo-app/.env`
- `/opt/seo-app/debug_data`
- Docker volume Postgres

## Проверка дубликатов dist

```bash
cd /opt/seo-app
find /opt/seo-app -maxdepth 2 -type d \( -name dist -o -name 'tmp_frontend_dist*' \)
```

Ожидаемое состояние:

- есть только `/opt/seo-app/frontend/dist` как рабочий dist
- временные `tmp_frontend_dist*` отсутствуют

## Автоматическая очистка

```bash
cd /opt/seo-app
bash scripts/cleanup_server_files.sh
```
