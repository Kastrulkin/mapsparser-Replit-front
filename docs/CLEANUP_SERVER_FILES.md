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
- `/opt/seo-app/debug_data/media_uploads`
- `/opt/seo-app/debug_data/sales_room_uploads`

## Текущая политика хранения

- PostgreSQL: 7 ежедневных, 4 еженедельных и 6 ежемесячных стандартных backup-файлов.
- Именованные backup-файлы перед миграциями и ручными изменениями сохраняются вне автоматической ротации.
- Несжатые SQL-бэкапы переводятся в gzip только после проверки gzip и SHA-256 распакованного содержимого.
- `latest.sql.gz` является hardlink на последний стандартный бэкап, а не второй полной копией.
- Debug bundles старше 30 дней удаляются; пользовательские медиа и файлы цифровых комнат исключены.
- Journald ограничен 300 МБ и 14 днями, rsyslog ротируется ежедневно или при достижении 100 МБ.

Ручная проверка без изменений:

```bash
cd /opt/seo-app
python3 scripts/prune_postgres_backups.py
bash scripts/prune_debug_data.sh
bash scripts/compress_sql_backups.sh
```

Ежедневная автоматизация выполняется через `localos-storage-maintenance.timer`.
Заполнение корневого диска проверяет `localos-disk-monitor.timer` каждые пять минут с порогами 70/80/90%.

## S3 для пользовательских файлов

S3 используется только после настройки `MEDIA_STORAGE_BACKEND=s3` и/или
`SALES_ROOM_STORAGE_BACKEND=s3` вместе с bucket, endpoint и credentials.
Покупка S3 сама по себе не расширяет корневой диск и не переключает LocalOS автоматически.
Рабочую базу PostgreSQL, Docker data и runtime-логи в S3 не перемещать.

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
