# 🔌 Порты и сервисы проекта BeautyBot

> 📖 **Связанная документация:**
> - [README.md](./README.md) — основное описание проекта
> - [ALGORITHM_UPDATE.md](./ALGORITHM_UPDATE.md) — алгоритм обновления проекта

## 📋 Схема портов

| Сервис | Порт | Протокол | Описание | Проверка |
|--------|------|----------|----------|----------|
| **Фронтенд (Dev)** | `3000` | HTTP | Vite dev server (разработка) | `http://localhost:3000` |
| **Фронтенд (Prod)** | `80/443` | HTTP/HTTPS | Nginx (статический фронтенд) | `https://localhost` |
| **Бэкенд API** | `8000` | HTTP | Flask API сервер | `http://localhost:8000` |
| **Бот управления** | - | - | Systemd сервис (polling) | `systemctl status telegram-bot` |
| **Бот обмена отзывами** | - | - | Systemd сервис (polling) | `systemctl status telegram-reviews-bot` |

## 🔍 Проверка портов и процессов

### 1. Проверить, какие порты заняты

```bash
# Проверить все занятые порты
netstat -tulpn | grep -E ":(80|443|3000|8000)"

# Или через ss
ss -tulpn | grep -E ":(80|443|3000|8000)"

# Проверить конкретный порт
lsof -i :8000  # Бэкенд API
lsof -i :3000  # Фронтенд (dev)
lsof -i :80    # Nginx HTTP
lsof -i :443   # Nginx HTTPS
```

### 2. Проверить процессы сервисов

```bash
# Бэкенд API (Flask)
ps aux | grep "main.py\|flask\|gunicorn" | grep -v grep

# Фронтенд (Nginx для продакшена)
ps aux | grep nginx | grep -v grep

# Фронтенд (Vite для разработки)
ps aux | grep "vite\|npm.*dev" | grep -v grep

# Бот для управления аккаунтом
ps aux | grep "telegram_bot.py" | grep -v grep

# Бот для обмена отзывами
ps aux | grep "telegram_reviews_bot.py" | grep -v grep
```

### 3. Проверить systemd сервисы

```bash
# Статус всех сервисов
systemctl status telegram-bot
systemctl status telegram-reviews-bot
systemctl status nginx
systemctl status gunicorn  # если используется

# Список всех сервисов проекта
systemctl list-units | grep -E "telegram|nginx|gunicorn|flask"
```

## 🚀 Запуск сервисов

### Фронтенд (разработка)

```bash
cd /root/mapsparser-Replit-front/frontend
npm run dev
# Запускается на порту 3000
```

### Фронтенд (продакшен)

```bash
# Сборка
cd /root/mapsparser-Replit-front/frontend
npm run build

# Копирование в nginx
cp -r dist/* /var/www/html/

# Nginx уже должен быть запущен на портах 80/443
systemctl status nginx
```

### Бэкенд API

```bash
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/main.py
# Запускается на порту 8000
```

Или через systemd (если настроен):
```bash
systemctl start flask-api  # если есть такой сервис
```

### Бот для управления аккаунтом

```bash
# Через systemd (рекомендуется)
systemctl start telegram-bot
systemctl status telegram-bot

# Или вручную
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/telegram_bot.py
```

**Порт:** Не используется (работает через Telegram polling API)

### Бот для обмена отзывами

```bash
# Через systemd (рекомендуется)
systemctl start telegram-reviews-bot
systemctl status telegram-reviews-bot

# Или вручную
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/telegram_reviews_bot.py
```

**Порт:** Не используется (работает через Telegram polling API)

## 🔧 Настройка портов

### Изменить порт бэкенда API

В файле `src/main.py` (строка ~5764):
```python
app.run(host='0.0.0.0', port=8000, debug=False)
```

Изменить на нужный порт, например:
```python
app.run(host='0.0.0.0', port=8080, debug=False)
```

Также обновить:
- `.env`: `API_BASE_URL=http://localhost:8080`
- `nginx-config.conf`: `proxy_pass http://localhost:8080/api/;`
- `frontend/vite.config.ts`: `target: 'http://localhost:8080'`

### Изменить порт фронтенда (dev)

В файле `frontend/vite.config.ts`:
```typescript
server: {
  port: 3000,  // Изменить на нужный порт
}
```

## 📊 Мониторинг портов

### Проверить, что все сервисы работают

```bash
#!/bin/bash
echo "=== Проверка портов и сервисов ==="
echo ""

echo "🔌 Порты:"
echo "  Порт 80 (HTTP):"
lsof -i :80 2>/dev/null || echo "    ❌ Не занят"
echo "  Порт 443 (HTTPS):"
lsof -i :443 2>/dev/null || echo "    ❌ Не занят"
echo "  Порт 3000 (Frontend Dev):"
lsof -i :3000 2>/dev/null || echo "    ❌ Не занят"
echo "  Порт 8000 (Backend API):"
lsof -i :8000 2>/dev/null || echo "    ❌ Не занят"

echo ""
echo "🤖 Telegram боты:"
echo "  Бот управления:"
systemctl is-active telegram-bot >/dev/null && echo "    ✅ Активен" || echo "    ❌ Не активен"
echo "  Бот обмена отзывами:"
systemctl is-active telegram-reviews-bot >/dev/null && echo "    ✅ Активен" || echo "    ❌ Не активен"

echo ""
echo "🌐 Nginx:"
systemctl is-active nginx >/dev/null && echo "  ✅ Активен" || echo "  ❌ Не активен"
```

Сохранить как `check_ports.sh` и запустить:
```bash
chmod +x check_ports.sh
./check_ports.sh
```

## ⚠️ Важные замечания

1. **Telegram боты не используют порты** - они работают через polling (запросы к Telegram API), поэтому им не нужны открытые порты.

2. **Фронтенд в продакшене** - статические файлы отдаются через Nginx на портах 80/443, API проксируется на порт 8000.

3. **Бэкенд API** - должен быть доступен на `localhost:8000` для Nginx и фронтенда.

4. **Firewall** - убедитесь, что порты 80 и 443 открыты для внешнего доступа:
```bash
# Проверить firewall
ufw status
# Открыть порты если нужно
ufw allow 80/tcp
ufw allow 443/tcp
```

## 🔗 Связи между сервисами

```
Интернет
    ↓
Nginx (80/443)
    ├─→ Статические файлы фронтенда (/var/www/html)
    └─→ API запросы → Flask API (localhost:8000)
                        ├─→ База данных (SQLite)
                        ├─→ GigaChat API
                        └─→ Telegram API (через ботов)

Telegram API
    ├─→ Бот управления (telegram_bot.py) → Systemd сервис
    └─→ Бот обмена отзывами (telegram_reviews_bot.py) → Systemd сервис
```

## 📝 Быстрая проверка всех сервисов

```bash
# Одной командой проверить всё
echo "=== Статус всех сервисов ===" && \
echo "Backend API (8000):" && (curl -s http://localhost:8000 > /dev/null && echo "✅ Работает" || echo "❌ Не работает") && \
echo "Nginx (80/443):" && (systemctl is-active nginx > /dev/null && echo "✅ Работает" || echo "❌ Не работает") && \
echo "Бот управления:" && (systemctl is-active telegram-bot > /dev/null && echo "✅ Работает" || echo "❌ Не работает") && \
echo "Бот обмена отзывами:" && (systemctl is-active telegram-reviews-bot > /dev/null && echo "✅ Работает" || echo "❌ Не работает")
```

