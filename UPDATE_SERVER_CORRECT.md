# Команды для обновления на сервере (согласно ALGORITHM_UPDATE.md)

## 📍 Путь к проекту
`/root/mapsparser-Replit-front`

## 🔄 Полное обновление (Frontend + Backend)

### Шаг 1: Обновить код из GitHub
```bash
cd /root/mapsparser-Replit-front
git checkout -- frontend/dist/index.html 2>/dev/null || true
git pull origin main
```

### Шаг 2: Пересобрать фронтенд (ОБЯЗАТЕЛЬНО при изменениях в frontend/src/)
```bash
cd frontend
rm -rf dist  # ОБЯЗАТЕЛЬНО удалить старую сборку!
npm run build
```

### Шаг 3: Проверить сборку
```bash
ls -lh dist/assets/index-*.js
# Должен быть свежий файл с текущей датой и временем
```

### Шаг 4: Перезапустить Flask сервер

**Вариант А: Через systemd (РЕКОМЕНДУЕТСЯ)**
```bash
cd /root/mapsparser-Replit-front
systemctl restart seo-worker
```

**Вариант Б: Вручную (если systemd не используется)**
```bash
cd /root/mapsparser-Replit-front

# Остановить старый процесс Flask
pkill -9 -f "python.*main.py" || true
pkill -9 -f "python.*worker.py" || true
sleep 2

# Проверить, что порт свободен
lsof -iTCP:8000 -sTCP:LISTEN
# Не должно быть вывода

# Запустить новый процесс Flask
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
sleep 3
```

### Шаг 5: Проверить запуск
```bash
# Проверка порта
lsof -iTCP:8000 -sTCP:LISTEN
# Должен показать процесс на порту 8000

# Проверка логов на ошибки
tail -20 /tmp/seo_main.out | grep -E "ERROR|Traceback|AssertionError" || tail -10 /tmp/seo_main.out
# Должно быть "SEO анализатор запущен на порту 8000" без ошибок

# Проверка статуса worker (если используется systemd)
systemctl status seo-worker --no-pager | head -10
```

### Шаг 6: Очистить кеш браузера
- **Жесткая перезагрузка:** **Cmd+Shift+R** (Mac) или **Ctrl+Shift+R** (Windows/Linux)
- **Или режим инкогнито:** **Cmd+Shift+N**

## 🚀 Одной строкой (через systemd)

```bash
cd /root/mapsparser-Replit-front && git checkout -- frontend/dist/index.html 2>/dev/null || true && git pull origin main && cd frontend && rm -rf dist && npm run build && cd .. && systemctl restart seo-worker && sleep 3 && lsof -iTCP:8000 -sTCP:LISTEN && tail -10 /tmp/seo_main.out
```

## 🚀 Одной строкой (вручную)

```bash
cd /root/mapsparser-Replit-front && git checkout -- frontend/dist/index.html 2>/dev/null || true && git pull origin main && cd frontend && rm -rf dist && npm run build && cd .. && pkill -9 -f "python.*main.py" || true && pkill -9 -f "python.*worker.py" || true && sleep 2 && source venv/bin/activate && python src/main.py >/tmp/seo_main.out 2>&1 & sleep 3 && lsof -iTCP:8000 -sTCP:LISTEN && tail -10 /tmp/seo_main.out
```

## ⚠️ Важные моменты

1. **ОБЯЗАТЕЛЬНО удалить `dist`** перед сборкой фронтенда
2. **Проверить дату JS файла** после сборки
3. **Использовать `systemctl restart seo-worker`** если доступен
4. **Очистить кеш браузера** после обновления


