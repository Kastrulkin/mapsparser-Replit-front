# Frontend Deploy Runbook

Канонический способ выкладки production frontend для `localos.pro`:

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

## Что делает скрипт

1. Локально собирает `frontend/dist` и `frontend/public-dist`
2. Проверяет целостность обоих dist-каталогов
3. Копирует dist на сервер в `/opt/seo-app/frontend/dist` и `/opt/seo-app/frontend/public-dist`
4. Проверяет, что сервис `app` поднят в `docker compose`
5. Синхронизирует runtime-каталоги внутри контейнера `app`
6. Выполняет стандартную проверку:
   - `docker compose ps`
   - `docker compose logs --since 10m app`
   - `curl -I http://localhost:8000`
   - targeted frontend checks

## Почему больше не используем ручной tar + docker cp

- ручные шаги расходятся от одного запуска к другому;
- легко забыть обновить оба runtime-пути:
  - `/app/frontend/dist`
  - `/app/dist`
- легко удалить старые lazy-assets и сломать уже открытые вкладки.

Скрипт специально **не удаляет старые asset-файлы** перед копированием. Это уменьшает риск ошибок вида:

- `Failed to fetch dynamically imported module`
- падение старой вкладки после нового релиза

Дополнительно скрипт использует:

- SSH keepalive
- повторные попытки для `ssh` / `scp` / verification steps

Это не лечит полный outage сервера, но уменьшает вероятность ложного провала из-за короткого сетевого дрожания.

## Когда использовать

### Frontend-only hotfix

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

### Если dist уже собран локально

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh
```

## Локальная проверка без выкладки

```bash
bash scripts/deploy_frontend_dist.sh --build --skip-remote
```

## После выкладки

Если пользователь держал вкладку открытой давно, попросить сделать hard refresh. Скрипт сохраняет старые assets, но это снижает риск, а не отменяет кеш браузера полностью.
