# Руководство по тестированию ChatGPT API

## Быстрый старт

### 1. Запуск тестов

```bash
# Убедитесь, что сервер запущен
python src/main.py

# В другом терминале запустите тесты
python tests/test_chatgpt_api.py
```

### 2. Ручное тестирование через curl

#### Поиск салонов
```bash
# Базовый поиск
curl "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка"

# Поиск с геолокацией
curl "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка&latitude=55.7558&longitude=37.6173"

# Поиск с фильтрами
curl "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка&min_rating=4.0&budget=2000"
```

#### Информация о салоне
```bash
# Замените {salon_id} на реальный ID салона
curl "http://localhost:8000/api/chatgpt/salon/{salon_id}"
```

#### Доступные слоты
```bash
curl "http://localhost:8000/api/chatgpt/salon/{salon_id}/available-slots?days=7"
```

#### Создание бронирования
```bash
curl -X POST "http://localhost:8000/api/chatgpt/book" \
  -H "Content-Type: application/json" \
  -H "X-ChatGPT-User-ID: test_user_123" \
  -d '{
    "salonId": "{salon_id}",
    "clientName": "Иван Петров",
    "clientPhone": "+7-900-123-45-67",
    "bookingTime": "2025-12-27T15:00:00Z"
  }'
```

#### Предпочтения пользователя
```bash
curl -H "X-ChatGPT-User-ID: test_user_123" \
  "http://localhost:8000/api/chatgpt/user/preferences"
```

#### Статистика (требуется авторизация администратора)
```bash
curl -H "Authorization: Bearer {admin_token}" \
  "http://localhost:8000/api/chatgpt/stats?days=30"
```

## Сценарии тестирования

### Сценарий 1: Полный цикл поиска и бронирования

1. **Поиск салона**
   ```bash
   curl "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка&latitude=55.7558&longitude=37.6173"
   ```

2. **Получение информации о салоне**
   ```bash
   curl "http://localhost:8000/api/chatgpt/salon/{salon_id}"
   ```

3. **Проверка доступных слотов**
   ```bash
   curl "http://localhost:8000/api/chatgpt/salon/{salon_id}/available-slots?days=7"
   ```

4. **Создание бронирования**
   ```bash
   curl -X POST "http://localhost:8000/api/chatgpt/book" \
     -H "Content-Type: application/json" \
     -H "X-ChatGPT-User-ID: test_user_123" \
     -d '{
       "salonId": "{salon_id}",
       "clientName": "Иван Петров",
       "clientPhone": "+7-900-123-45-67",
       "serviceId": "{service_id}",
       "bookingTime": "2025-12-27T15:00:00Z"
     }'
   ```

### Сценарий 2: Персонализация

1. **Создание истории поисков**
   ```bash
   for i in {1..5}; do
     curl -H "X-ChatGPT-User-ID: test_user_123" \
       "http://localhost:8000/api/chatgpt/search?city=Москва&service=услуга$i"
     sleep 1
   done
   ```

2. **Получение предпочтений**
   ```bash
   curl -H "X-ChatGPT-User-ID: test_user_123" \
     "http://localhost:8000/api/chatgpt/user/preferences"
   ```

### Сценарий 3: Обработка ошибок

1. **Отсутствующие обязательные параметры**
   ```bash
   curl "http://localhost:8000/api/chatgpt/search?city=Москва"
   # Ожидается: 400 Bad Request
   ```

2. **Несуществующий салон**
   ```bash
   curl "http://localhost:8000/api/chatgpt/salon/00000000-0000-0000-0000-000000000000"
   # Ожидается: 404 Not Found
   ```

3. **Неверный формат данных**
   ```bash
   curl -X POST "http://localhost:8000/api/chatgpt/book" \
     -H "Content-Type: application/json" \
     -d '{"salonId": "invalid"}'
   # Ожидается: 400 Bad Request
   ```

## Проверка производительности

### Тест нагрузки (требуется Apache Bench или аналогичный инструмент)

```bash
# 100 запросов, 10 параллельных
ab -n 100 -c 10 "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка"
```

### Проверка времени ответа

```bash
time curl "http://localhost:8000/api/chatgpt/search?city=Москва&service=стрижка"
```

## Проверка логирования

### Просмотр логов запросов

```sql
-- Подключитесь к базе данных
sqlite3 src/reports.db

-- Последние 10 запросов
SELECT endpoint, method, response_status, response_time_ms, created_at 
FROM ChatGPTRequests 
ORDER BY created_at DESC 
LIMIT 10;

-- Статистика по endpoint
SELECT endpoint, 
       COUNT(*) as total,
       AVG(response_time_ms) as avg_time,
       SUM(CASE WHEN response_status >= 200 AND response_status < 300 THEN 1 ELSE 0 END) as success_count
FROM ChatGPTRequests
GROUP BY endpoint;
```

## Проверка персонализации

### Просмотр сессий пользователей

```sql
SELECT chatgpt_user_id, 
       total_interactions,
       preferred_city,
       preferred_service_types,
       last_interaction_at
FROM ChatGPTUserSessions
ORDER BY last_interaction_at DESC
LIMIT 10;
```

## Чеклист тестирования

### Функциональное тестирование
- [ ] Поиск салонов работает корректно
- [ ] Фильтры применяются правильно
- [ ] Геолокация и расчет расстояния работают
- [ ] Группировка по сетям работает
- [ ] Информация о салоне полная
- [ ] Доступные слоты рассчитываются правильно
- [ ] Бронирование создается корректно
- [ ] Предпочтения пользователя сохраняются
- [ ] Статистика доступна администраторам

### Тестирование ошибок
- [ ] Обработка отсутствующих параметров
- [ ] Обработка неверных данных
- [ ] Обработка несуществующих ресурсов
- [ ] Обработка сетевых ошибок
- [ ] Обработка ошибок БД

### Производительность
- [ ] Время ответа < 1 секунды для поиска
- [ ] Время ответа < 2 секунд для бронирования
- [ ] Система выдерживает 10+ параллельных запросов
- [ ] Нет утечек памяти

### Безопасность
- [ ] API ключи проверяются (когда реализовано)
- [ ] Доступ к статистике только для администраторов
- [ ] Данные пользователей защищены
- [ ] SQL-инъекции невозможны (параметризованные запросы)

## Автоматизированное тестирование

Используйте `tests/test_chatgpt_api.py` для автоматического тестирования:

```bash
# Запуск всех тестов
python tests/test_chatgpt_api.py

# Запуск с выводом в файл
python tests/test_chatgpt_api.py > test_results.txt 2>&1
```

## Интеграционное тестирование с ChatGPT

1. Импортируйте OpenAPI схему в ChatGPT
2. Протестируйте все функции через ChatGPT интерфейс
3. Проверьте, что ChatGPT правильно интерпретирует ответы
4. Убедитесь, что ошибки обрабатываются корректно

---

**Версия**: 1.0.0  
**Дата**: 26 декабря 2025


