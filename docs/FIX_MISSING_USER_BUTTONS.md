# Исправление: не появились кнопки на сервере

## Типовая причина

Если изменения есть локально, но не видны на `localos.pro`, сначала проверяйте не `venv` и не `nohup`, а текущий Docker runtime и live frontend bundle.

## Быстрый сценарий проверки

### 1. Убедиться, что код обновлён на сервере

```bash
cd /opt/seo-app
git log --oneline -5
```

### 2. Пересобрать и выкатить фронтенд каноническим способом

```bash
cd /opt/seo-app
bash scripts/deploy_frontend_dist.sh --build
```

### 3. Проверить, что live bundle действительно обновился

```bash
cd /opt/seo-app
docker compose exec -T app sh -lc 'grep -n "/assets/index-" /app/frontend/dist/index.html'
```

### 4. Проверить app runtime

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m app | tail -n 120
curl -I http://localhost:8000
```

### 5. Проверить браузер

- сделать hard refresh: `Cmd + Shift + R` или `Ctrl + Shift + R`
- открыть страницу в режиме инкогнито
- в DevTools -> `Network` убедиться, что загружается новый `index-*.js`

## Что больше не делать

Для текущего production не использовать:

- старый путь проекта вне `/opt/seo-app`
- ручной kill/restart python-процесса
- ручную активацию `venv`
- прямой запуск Flask через `nohup`
