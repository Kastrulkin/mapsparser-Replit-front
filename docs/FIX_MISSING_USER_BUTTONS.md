# Исправление: не появились кнопки удаления пользователей на сервере

## Проблема
На сервере не появились кнопки удаления и паузы пользователей в админ-панели.

## Причины

### 1. Фронтенд не пересобран на сервере
Фронтенд нужно пересобрать после обновления кода.

### 2. Кеш браузера
Браузер использует старую версию JS файлов.

### 3. Старый dist не обновлен
Файлы в `frontend/dist/` не обновлены.

## Решение

### Шаг 1: Проверить, что код обновлен на сервере
```bash
cd /root/mapsparser-Replit-front
git log --oneline -5
# Должен быть коммит "Исправления: subscription_tier, управление пользователями..."
```

### Шаг 2: Пересобрать фронтенд на сервере
```bash
cd /root/mapsparser-Replit-front/frontend
rm -rf dist
npm run build
```

### Шаг 3: Проверить, что новый JS файл создан
```bash
ls -lh dist/assets/index-*.js
# Должен быть файл с текущей датой/временем
```

### Шаг 4: Перезапустить Flask
```bash
cd /root/mapsparser-Replit-front
pkill -f 'python.*main.py' 2>/dev/null
sleep 2
source venv/bin/activate
nohup python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3
lsof -iTCP:8000 -sTCP:LISTEN
```

### Шаг 5: Очистить кеш браузера
В браузере:
- **Mac**: `Cmd + Shift + R` (жесткая перезагрузка)
- **Windows/Linux**: `Ctrl + Shift + R`
- Или откройте в режиме инкогнито: `Cmd + Shift + N` (Mac) / `Ctrl + Shift + N` (Windows)

### Шаг 6: Проверить в консоли браузера
Откройте DevTools (F12) → Console и проверьте:
- Нет ли ошибок загрузки JS файлов
- Загружается ли новый JS файл (Network → ищите `index-*.js`)

## Полная команда для обновления

```bash
cd /root/mapsparser-Replit-front && \
git pull origin main && \
cd frontend && \
rm -rf dist && \
npm run build && \
cd .. && \
pkill -f 'python.*main.py' 2>/dev/null && \
sleep 2 && \
source venv/bin/activate && \
nohup python src/main.py > /tmp/seo_main.out 2>&1 & \
sleep 3 && \
echo "=== Проверка ===" && \
lsof -iTCP:8000 -sTCP:LISTEN && \
ls -lh frontend/dist/assets/index-*.js | head -1
```

## Проверка после обновления

1. Откройте админ-панель
2. Наведите курсор на карточку пользователя
3. Должны появиться две кнопки справа:
   - Иконка Ban/User (пауза/возобновление)
   - Иконка Trash2 (удаление)

Если кнопки не появились:
- Проверьте консоль браузера на ошибки
- Убедитесь, что загружается новый JS файл
- Попробуйте жесткую перезагрузку страницы


