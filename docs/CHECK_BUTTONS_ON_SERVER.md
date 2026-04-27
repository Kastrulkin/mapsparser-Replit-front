# Проверка UI-правок на сервере

## Цель

Подтвердить, что фронтенд-изменение реально доехало до production bundle и раздаётся из канонического runtime path.

## Проверка на сервере

### 1. Проверить свежий bundle в контейнере

```bash
cd /opt/seo-app
docker compose exec -T app sh -lc 'grep -n "/assets/index-" /app/frontend/dist/index.html'
```

### 2. Проверить, что сервис жив

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```

### 3. Проверить live HTML

```bash
curl -s https://localos.pro | rg '/assets/index-|/assets/index-.*\\.css'
```

### 4. Если bundle старый

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

## Проверка в браузере

1. Открыть `DevTools -> Network`
2. Найти `index-*.js`
3. Убедиться, что имя совпадает с тем, что лежит в `/app/frontend/dist/index.html`
4. Сделать hard refresh

## Чего больше не делать

Не использовать старую схему:

- старый путь проекта вне `/opt/seo-app`
- restart старого systemd worker как способ применить frontend
- ручную пересборку с копированием в legacy web-root
