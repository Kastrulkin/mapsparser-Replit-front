# Шлифовка Human-in-the-Loop CAPTCHA Flow

## Изменения

### A) Устойчивость к рестартам воркера

**Проблема:** При рестарте воркера `ACTIVE_CAPTCHA_SESSIONS` (in-memory) теряется, а задачи остаются в `captcha_status='waiting'`.

**Решение:**
- При старте воркера вызывается `_recover_lost_captcha_sessions()`
- Находятся задачи со `status='captcha' AND captcha_status='waiting'`
- Если сессии нет в реестре → `captcha_status='expired'`, `error_message='captcha session lost (worker restarted)'`

**Новый endpoint:** `POST /tasks/{id}/captcha/restart`
- Сбрасывает все `captcha_*` поля
- Возвращает задачу в `status='pending'` для нового парсинга

### B) Синхронизация TTL токена

**Изменение:** TTL токена увеличен до **30 минут** (совпадает с таймаутом ожидания воркера).

**Новое поле:** `captcha_token_expires_at TIMESTAMP`
- Явно хранит время истечения токена
- Используется в API для проверки валидности

### C) Усиление verify_captcha_solved

**Улучшения:**
1. Проверка отсутствия капчи:
   - URL не содержит `/showcaptcha`
   - Нет селекторов капчи (`.smart-captcha`, `input[name='smart-token']`)
   - Нет текста капчи ("Вы не робот?", "Подтвердите, что вы не робот")
   - Нет iframe капчи

2. **Критично:** Проверка наличия целевого селектора карточки организации:
   - `h1`, `div.business-card-title-view`, `div.card-title-view__title`, и т.д.
   - Таймаут ожидания: 10 секунд
   - Если селектор не появился → капча считается НЕ решённой

### D) Защита от утечки Playwright объектов

**Проблема:** `_browser`, `_context`, `_page` не должны попадать в JSON/логи.

**Решение:**
- Объекты извлекаются из `card_data` через `pop()` перед сохранением
- Сохраняются **только** в `ACTIVE_CAPTCHA_SESSIONS`
- Добавлены `assert` проверки, что в `card_data` нет Playwright объектов

### E) Улучшение индексов

**Добавлен составной индекс:**
```sql
CREATE INDEX idx_parsequeue_captcha_waiting 
ON parsequeue(status, captcha_status) 
WHERE captcha_required = TRUE AND captcha_status = 'waiting';
```

**Цель:** Быстрый поиск задач "ждут оператора" в кабинете.

### F) UX для оператора

**Улучшения HTML страницы:**
1. **Разные состояния:**
   - `captcha_status='waiting'` → iframe + кнопка "Продолжить"
   - `captcha_status='expired'` → сообщение + кнопка "Перезапустить сессию"
   - `token_expired` → сообщение + кнопка "Обновить ссылку"

2. **Авто-refresh статуса:**
   - Poll каждые 5 секунд через `GET /tasks/{id}/captcha/status?token=...`
   - Автоматическое обновление UI при изменении статуса

3. **Новые кнопки:**
   - "Перезапустить сессию" → `POST /tasks/{id}/captcha/restart`
   - "Обновить ссылку" → (TODO: refresh_token endpoint)

## Новые API Endpoints

### GET /tasks/{id}/captcha/status?token=...

Возвращает текущий статус капчи для авто-refresh.

**Ответ:**
```json
{
  "status": "waiting" | "expired" | "resume",
  "token_expired": false
}
```

### POST /tasks/{id}/captcha/restart?token=...

Перезапускает сессию капчи:
- Сбрасывает все `captcha_*` поля
- Возвращает задачу в `status='pending'`
- Задача будет обработана заново с `keep_open_on_captcha=True`

**Ответ:**
```json
{
  "success": true,
  "message": "Session restarted. Task returned to pending queue."
}
```

## Поведение при рестарте воркера

1. **При старте воркера:**
   - Вызывается `_recover_lost_captcha_sessions()`
   - Находятся задачи с `status='captcha' AND captcha_status='waiting'`
   - Для каждой проверяется наличие сессии в `ACTIVE_CAPTCHA_SESSIONS`
   - Если сессии нет → `captcha_status='expired'`

2. **В кабинете:**
   - Оператор видит сообщение "Сессия истекла"
   - Кнопка "Перезапустить сессию" запускает новый парсинг
   - Задача возвращается в очередь `pending`

3. **Гарантия:**
   - Ни одна задача не остаётся навечно в `waiting`
   - После рестарта все потерянные сессии помечаются как `expired`
   - Оператор может перезапустить сессию вручную

## Изменённые файлы

1. **src/worker.py**
   - Добавлена функция `_recover_lost_captcha_sessions()`
   - Улучшена `verify_captcha_solved()` с проверкой целевого селектора
   - Добавлена защита от утечки Playwright объектов
   - Обновлён `park_task_for_captcha()` для сохранения `captcha_token_expires_at`
   - Вызов восстановления при старте воркера

2. **src/api/captcha_api.py**
   - Обновлён HTML шаблон с разными состояниями
   - Добавлен `GET /tasks/{id}/captcha/status`
   - Добавлен `POST /tasks/{id}/captcha/restart`
   - Улучшена проверка TTL токена (30 минут)

3. **src/migrations/add_captcha_fields.py**
   - Добавлено поле `captcha_token_expires_at`
   - Добавлен составной индекс `idx_parsequeue_captcha_waiting`

## Проверки

- ✅ `python3 -m py_compile` — все файлы компилируются без ошибок
- ✅ Защита от утечки объектов — `assert` проверки добавлены
- ✅ Улучшенная проверка капчи — проверка целевого селектора
- ✅ Восстановление после рестарта — автоматическая пометка `expired`

## Следующие шаги

1. Применить миграцию: `python3 src/migrations/add_captcha_fields.py`
2. Протестировать восстановление после рестарта воркера
3. Протестировать перезапуск сессии через API
4. Интегрировать noVNC сервер для проксирования WebSocket соединения
