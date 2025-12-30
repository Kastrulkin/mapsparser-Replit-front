# Проверка статуса сборки фронтенда

## Если сборка "подвисла"

### Проверить процессы сборки
```bash
# Проверить, есть ли активные процессы npm/node
ps aux | grep -E 'npm|node|vite' | grep -v grep

# Проверить использование CPU/памяти
top -bn1 | head -20
```

### Проверить использование диска
```bash
# Проверить свободное место
df -h

# Проверить размер директории frontend/dist
du -sh frontend/dist 2>/dev/null
```

### Если сборка действительно зависла

**Вариант 1: Прервать и запустить заново**
```bash
# Прервать все процессы npm/node
pkill -f 'npm|node|vite'

# Подождать
sleep 3

# Запустить сборку заново
cd /root/mapsparser-Replit-front/frontend
npm run build
```

**Вариант 2: Собрать с подробным выводом**
```bash
cd /root/mapsparser-Replit-front/frontend
npm run build -- --debug
```

**Вариант 3: Очистить кеш и собрать заново**
```bash
cd /root/mapsparser-Replit-front/frontend
rm -rf node_modules/.vite
rm -rf dist
npm run build
```

## Нормальное время сборки

- Маленький проект: 10-30 секунд
- Средний проект: 30-60 секунд
- Большой проект: 1-3 минуты

Если сборка идет больше 5 минут - вероятно, проблема.

## Проверка после сборки

```bash
# Проверить, что dist создан
ls -lh frontend/dist/assets/

# Проверить размер файлов
du -sh frontend/dist
```

