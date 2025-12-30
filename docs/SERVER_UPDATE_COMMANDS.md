# Команды для обновления проекта на сервере

## 📍 Путь к проекту на сервере

**Директория проекта:** `/root/mapsparser-Replit-front`

## Обновление через SSH

### Шаг 1: Подключиться к серверу
```bash
ssh root@80.78.242.105
```

### Шаг 2: Перейти в директорию проекта
```bash
cd /root/mapsparser-Replit-front
```

### Шаг 3: Обновить проект
```bash
# Если есть локальные изменения в dist файлах - отменить их
git checkout -- frontend/dist/index.html 2>/dev/null || true

# Обновить из GitHub
git pull origin main
```

### Шаг 4: Перезапустить сервер

**Вариант А: Через systemd (рекомендуется)**
```bash
systemctl restart seo-worker
```

**Вариант Б: Вручную (если systemd не используется)**
```bash
# Найти процесс Flask
ps aux | grep "python.*main.py"

# Остановить старый процесс
pkill -f "python.*main.py"

# Запустить новый
source venv/bin/activate
nohup python src/main.py > /tmp/seo_main.out 2>&1 &
```

### Шаг 5: Проверить запуск
```bash
# Проверить статус воркера (если используется systemd)
systemctl status seo-worker

# Проверить порт Flask
lsof -iTCP:8000 -sTCP:LISTEN

# Проверить логи
tail -20 /tmp/seo_main.out
# или
journalctl -u seo-worker -f
```

## Быстрая команда (одной строкой)

### Через systemd:
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && git checkout -- frontend/dist/index.html 2>/dev/null || true && git pull origin main && systemctl restart seo-worker"
```

### Вручную (Flask сервер):
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && git pull origin main && pkill -f 'python.*main.py' && source venv/bin/activate && nohup python src/main.py > /tmp/seo_main.out 2>&1 &"
```

## Обновление через веб-консоль хостинга

Если SSH не работает, используйте веб-консоль в панели управления хостингом:

1. Зайдите в панель управления
2. Откройте веб-консоль/терминал
3. Выполните команды:
```bash
cd /root/mapsparser-Replit-front
git pull origin main
systemctl restart seo-worker
```

## Если проект не найден - клонировать заново

```bash
cd /root
git clone https://github.com/Kastrulkin/mapsparser-Replit-front.git
cd mapsparser-Replit-front

# Установить зависимости
source venv/bin/activate
pip install -r requirements.txt

# Установить Playwright браузеры (если нужно)
python -m playwright install chromium

# Запустить
nohup python src/main.py > /tmp/seo_main.out 2>&1 &
```

## Что обновлено в последнем коммите

- ✅ Network Interception парсер (`src/parser_interception.py`)
- ✅ Конфигурация парсера (`src/parser_config.py`)
- ✅ Интеграция в worker.py
- ✅ Документация по парсеру

## Проверка после обновления

```bash
# Проверить, что новый парсер доступен
cd /root/mapsparser-Replit-front
source venv/bin/activate
python -c "from parser_interception import parse_yandex_card; print('✅ Парсер работает')"

# Проверить логи на ошибки
tail -50 /tmp/seo_main.out | grep -i error
```
