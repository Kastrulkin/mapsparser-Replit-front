# Проверка нагрузки сервера

## Актуальный production-контекст

Текущий сервер работает из `/opt/seo-app` через Docker Compose. Для проверки нагрузки смотрите на:

- контейнеры `app`, `worker`, `postgres`
- диск хоста
- Docker images / build cache

## Базовые команды

### CPU, память, диск

```bash
top -bn1 | head -20
free -h
df -h
```

### Контейнеры и их статус

```bash
cd /opt/seo-app
docker compose ps
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
```

### Логи приложений

```bash
cd /opt/seo-app
docker compose logs --since 15m app | tail -n 120
docker compose logs --since 15m worker | tail -n 120
```

### Размеры Docker-артефактов

```bash
docker system df
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
docker buildx du
```

### Размер проекта и dist

```bash
du -sh /opt/seo-app
du -sh /opt/seo-app/* | sort -h
du -sh /opt/seo-app/frontend/dist
```

## Что смотреть в первую очередь

- диск `> 90%` заполнен: риск падения `postgres` и Docker
- слишком много неиспользуемых image/cache: чистить Docker
- `app` или `worker` перезапускаются: смотреть `docker compose logs`
- frontend hotfix не применяется: смотреть `/opt/seo-app/frontend/dist` и `/app/frontend/dist`

## Что больше не актуально

Для текущего production не использовать:

- старый project root вне `/opt/seo-app`
- `sqlite3 src/reports.db "VACUUM;"`
- cleanup старых `seo_*.out` как основной путь диагностики
