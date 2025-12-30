# Решение конфликта при git pull на сервере

## Проблема
```
error: Your local changes to the following files would be overwritten by merge:
        frontend/dist/index.html
Please commit your changes or stash them before you merge.
```

## Решение

### Вариант 1: Отменить локальные изменения (рекомендуется для dist файлов)

```bash
cd /root/mapsparser-Replit-front

# Отменить изменения в dist файлах (они пересобираются автоматически)
git checkout -- frontend/dist/index.html

# Теперь можно обновить
git pull origin main

# Перезапустить воркер
systemctl restart seo-worker
```

### Вариант 2: Сохранить изменения в stash

```bash
cd /root/mapsparser-Replit-front

# Сохранить изменения во временное хранилище
git stash

# Обновить
git pull origin main

# Перезапустить воркер
systemctl restart seo-worker
```

### Вариант 3: Принудительно обновить (если dist файлы не важны)

```bash
cd /root/mapsparser-Replit-front

# Сбросить все локальные изменения
git reset --hard origin/main

# Перезапустить воркер
systemctl restart seo-worker
```

## Быстрая команда (одной строкой)

```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && git checkout -- frontend/dist/index.html && git pull origin main && systemctl restart seo-worker"
```

## После обновления

Если обновлялся фронтенд, может потребоваться пересобрать:

```bash
cd /root/mapsparser-Replit-front/frontend
npm run build
```

