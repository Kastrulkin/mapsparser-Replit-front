# Диагностика белого экрана на beautybot.pro

## Возможные причины

1. **Фронтенд не собран** - отсутствует `frontend/dist/index.html`
2. **Ошибка в JavaScript** - консоль браузера покажет ошибки
3. **Проблема с путями к assets** - JS/CSS файлы не загружаются
4. **Ошибка Flask сервера** - сервер не запущен или падает с ошибкой
5. **Проблема с nginx** - неправильная конфигурация прокси

## Команды для диагностики на сервере

### 1. Проверить наличие фронтенда
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && ls -la frontend/dist/"
```

### 2. Проверить index.html
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && cat frontend/dist/index.html | head -20"
```

### 3. Проверить логи Flask
```bash
ssh root@80.78.242.105 "tail -50 /tmp/seo_main.out"
```

### 4. Проверить, запущен ли Flask
```bash
ssh root@80.78.242.105 "ps aux | grep 'python.*main.py'"
```

### 5. Проверить порт 8000
```bash
ssh root@80.78.242.105 "lsof -iTCP:8000 -sTCP:LISTEN"
```

### 6. Пересобрать фронтенд (если нужно)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front/frontend && npm run build"
```

## Быстрое решение

### Вариант 1: Пересобрать фронтенд
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front/frontend && rm -rf dist && npm run build && cd .. && systemctl restart seo-worker"
```

### Вариант 2: Проверить и перезапустить Flask
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && pkill -f 'python.*main.py' && source venv/bin/activate && nohup python src/main.py > /tmp/seo_main.out 2>&1 &"
```

## Проверка в браузере

1. Откройте консоль разработчика (F12)
2. Перейдите на вкладку Console
3. Проверьте ошибки JavaScript
4. Перейдите на вкладку Network
5. Проверьте, загружаются ли файлы (index.html, JS, CSS)

## Типичные ошибки

### "Failed to load resource: the server responded with a status of 404"
- Файлы не найдены - нужно пересобрать фронтенд

### "Uncaught SyntaxError"
- Ошибка в JavaScript - проверьте сборку

### "Connection refused"
- Flask сервер не запущен

### Пустая страница без ошибок
- Проблема с React роутингом или базовым URL

