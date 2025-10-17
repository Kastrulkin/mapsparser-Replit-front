# 🔍 Настройка API Яндекс.Вордстат для BeautyBot

## 📋 Обзор

API Яндекс.Вордстат позволяет автоматически получать актуальные данные о популярных запросах в бьюти-индустрии, что значительно улучшает качество SEO-оптимизации услуг.

## 🚀 Быстрый старт

### 1. Получение OAuth токена

```bash
# Запустите скрипт для получения токена
cd src
python3 get_wordstat_token.py
```

Скрипт автоматически:
- Откроет браузер для авторизации
- Поможет получить код авторизации
- Обменяет код на OAuth токен
- Протестирует токен

### 2. Установка переменных окружения

```bash
# Установите токен в переменную окружения
export YANDEX_WORDSTAT_OAUTH_TOKEN=your_token_here

# Или добавьте в .env файл
echo "YANDEX_WORDSTAT_OAUTH_TOKEN=your_token_here" >> .env
```

### 3. Тестирование API

```bash
# Обновите данные вручную
python3 update_wordstat_data.py

# Или через API
curl -X POST http://localhost:8000/api/wordstat/update \
  -H "Authorization: Bearer your_session_token"
```

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `YANDEX_WORDSTAT_CLIENT_ID` | ID приложения | `623b9605a95c4a57965cc4ccff1a7130` |
| `YANDEX_WORDSTAT_CLIENT_SECRET` | Секрет приложения | `8ec666a7306b49e78c895bfbbba63ad4` |
| `YANDEX_WORDSTAT_OAUTH_TOKEN` | OAuth токен | - |
| `WORDSTAT_UPDATE_INTERVAL` | Интервал обновления (сек) | `604800` (7 дней) |
| `WORDSTAT_DEFAULT_REGION` | ID региона | `225` (Россия) |

### Регионы

| ID | Регион |
|----|--------|
| 225 | Россия |
| 213 | Москва |
| 2 | Санкт-Петербург |
| 54 | Новосибирск |
| 66 | Екатеринбург |
| 16 | Казань |
| 1 | Московская область |

## 📊 API Endpoints

### Обновление данных
```http
POST /api/wordstat/update
Authorization: Bearer <session_token>
```

**Ответ:**
```json
{
  "success": true,
  "message": "Данные успешно обновлены",
  "queries_count": 150,
  "region": "Россия"
}
```

### Статус API
```http
GET /api/wordstat/status
```

**Ответ:**
```json
{
  "configured": true,
  "auth_url": null,
  "region": "Россия",
  "update_interval": 604800
}
```

## 🔄 Автоматическое обновление

### Через cron (Linux/macOS)

```bash
# Добавьте в crontab для еженедельного обновления
0 2 * * 1 cd /path/to/beautybot && python3 src/update_wordstat_data.py
```

### Через systemd (Linux)

Создайте файл `/etc/systemd/system/beautybot-wordstat.service`:

```ini
[Unit]
Description=BeautyBot Wordstat Data Updater
After=network.target

[Service]
Type=oneshot
User=beautybot
WorkingDirectory=/path/to/beautybot
ExecStart=/usr/bin/python3 src/update_wordstat_data.py
Environment=YANDEX_WORDSTAT_OAUTH_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

И таймер `/etc/systemd/system/beautybot-wordstat.timer`:

```ini
[Unit]
Description=BeautyBot Wordstat Data Updater Timer
Requires=beautybot-wordstat.service

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
```

Активация:
```bash
sudo systemctl enable beautybot-wordstat.timer
sudo systemctl start beautybot-wordstat.timer
```

## 📈 Ограничения API

- **10 запросов в секунду** (по умолчанию)
- **1,000 запросов в сутки** (по умолчанию)
- При превышении квоты: HTTP 429/503

## 🛠️ Структура файлов

```
src/
├── wordstat_client.py          # Клиент API
├── wordstat_config.py          # Конфигурация
├── update_wordstat_data.py     # Скрипт обновления
├── get_wordstat_token.py       # Получение токена
└── wordstat_token.json         # Сохраненный токен

prompts/
├── popular_queries_with_clicks.txt  # Обновляемые данные
└── wordstat_metadata.json          # Метаданные обновления
```

## 🔍 Мониторинг

### Проверка статуса
```bash
# Статус API
curl http://localhost:8000/api/wordstat/status

# Последнее обновление
cat prompts/wordstat_metadata.json
```

### Логи
```bash
# Логи обновления
tail -f server.out | grep wordstat
```

## 🚨 Устранение неполадок

### Ошибка 401 (Unauthorized)
- Проверьте OAuth токен
- Токен мог истечь (срок действия: 1 час)
- Получите новый токен: `python3 get_wordstat_token.py`

### Ошибка 429 (Quota exceeded)
- Превышена квота запросов
- Подождите указанное время в заголовке `Retry-After`
- Увеличьте интервал обновления

### Ошибка 503 (Service unavailable)
- Сервис временно недоступен
- Повторите запрос позже

### Токен не работает
```bash
# Проверьте токен
python3 -c "
from src.wordstat_client import WordstatClient
from src.wordstat_config import config
client = WordstatClient(config.client_id, config.client_secret)
client.set_access_token('your_token')
print('Тест:', client.get_popular_queries(['стрижка'], 225))
"
```

## 📞 Поддержка

При проблемах с API обращайтесь в [поддержку Яндекс Директа](https://yandex.ru/support/direct/).

## 🎯 Преимущества интеграции

- ✅ **Актуальные данные** вместо статических
- ✅ **Региональная аналитика** по городам
- ✅ **Автоматическое обновление** без ручного вмешательства
- ✅ **Улучшенное SEO** для услуг салонов красоты
- ✅ **Мониторинг трендов** в бьюти-индустрии
