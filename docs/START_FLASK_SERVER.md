# Восстановление backend на production

## Актуальная схема

На текущем проде `localos.pro` backend не запускается вручную через прямой `nohup`-старт Python.

Канонический runtime:

- проект на сервере: `/opt/seo-app`
- backend: контейнер `app`
- reverse proxy: nginx -> `127.0.0.1:8000`

Если сайт отвечает `502`, сначала проверяйте контейнеры, а не `venv/systemd`.

## Базовая диагностика

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose ps"
```

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose logs --since 10m app | tail -n 120"
```

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && curl -I http://localhost:8000"
```

## Перезапустить backend

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose restart app && docker compose ps"
```

## Пересоздать app container

Если обычный restart не помог:

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose up -d --force-recreate app && docker compose ps"
```

## Проверить, что frontend и backend смотрят в правильные пути

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose exec -T app python3 - <<'PY'
from src.main import FRONTEND_DIST_DIR
print(FRONTEND_DIST_DIR)
PY"
```

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose exec -T app sh -lc 'grep -n \"/assets/index-\" /app/frontend/dist/index.html'"
```

## Если проблема во frontend bundle

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

Потом повторить:

```bash
ssh root@80.78.242.105 "cd /opt/seo-app && docker compose ps && docker compose logs --since 10m app | tail -n 120 && curl -I http://localhost:8000"
```

## Что больше не использовать

Не использовать для текущего production:

- старый путь проекта вне `/opt/seo-app`
- ручную активацию `venv`
- прямой `nohup`-старт Flask
- ручной kill python-процесса
- ручной systemd unit для `seo-main`
