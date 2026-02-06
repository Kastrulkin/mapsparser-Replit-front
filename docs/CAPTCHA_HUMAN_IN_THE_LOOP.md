# Human-in-the-Loop обработка капчи через noVNC

## Обзор

При обнаружении капчи "Вы не робот?" парсер сохраняет живую сессию браузера и переводит задачу в статус `WAIT_CAPTCHA`. Оператор в личном кабинете открывает noVNC сессию, решает капчу и нажимает "Продолжить". Воркер продолжает парсинг в той же сессии браузера.

## Flow для оператора

### 1. Обнаружение капчи

Когда парсер обнаруживает капчу:
- Задача переводится в статус `captcha` с `captcha_status='waiting'`
- В БД сохраняются:
  - `captcha_required = TRUE`
  - `captcha_url` (URL страницы с капчей)
  - `captcha_session_id` (UUID сессии)
  - `captcha_token` (одноразовый токен, TTL 15 минут)
  - `captcha_vnc_path` (путь для открытия в кабинете)
  - `captcha_started_at` (время начала ожидания)
  - `resume_requested = FALSE`

### 2. Решение капчи оператором

**Ссылка для оператора:**
```
/tasks/{task_id}/captcha?token={captcha_token}
```

**Шаги:**
1. Откройте ссылку в браузере
2. В открывшемся окне noVNC вы увидите страницу с капчей
3. Решите капчу в окне noVNC
4. Нажмите кнопку **"Продолжить"**

**Что происходит:**
- Backend устанавливает `resume_requested = TRUE` и `captcha_status = 'resume'`
- Воркер обнаруживает флаг и продолжает парсинг в той же сессии браузера
- Проверяется, что капча решена (URL больше не содержит `/showcaptcha`)
- Парсинг продолжается с того места, где остановился

### 3. Завершение парсинга

После успешного завершения:
- Браузер/контекст закрываются
- Поля `captcha_*` очищаются в БД
- Статус задачи меняется на `completed`

### 4. Таймаут (30 минут)

Если капча не решена в течение 30 минут:
- Сессия браузера закрывается
- `captcha_status = 'expired'`
- Статус задачи меняется на `error`
- Задача НЕ возвращается в автоматический retry

## API Endpoints

### GET /tasks/{id}/captcha?token=...

Отображает HTML страницу с iframe на noVNC сессию.

**Параметры:**
- `id`: ID задачи в очереди
- `token`: одноразовый токен из `captcha_token`

**Ответ:**
- HTML страница с noVNC iframe (200)
- `{"error": "Token required"}` (400)
- `{"error": "Invalid token or task not found"}` (404)
- `{"error": "Token expired"}` (403)

### POST /tasks/{id}/captcha/resume?token=...

Устанавливает флаг `resume_requested = TRUE` для продолжения парсинга.

**Параметры:**
- `id`: ID задачи в очереди
- `token`: одноразовый токен из `captcha_token`

**Ответ:**
- `{"success": true, "message": "Parsing will resume shortly"}` (200)
- `{"error": "Token required"}` (400)
- `{"error": "Invalid token or task not found"}` (404)

### GET /vnc/{session_id}?token=...

Проксирует noVNC соединение (TODO: интеграция с novnc-websockify).

**Параметры:**
- `session_id`: UUID сессии браузера
- `token`: одноразовый токен

**Ответ:**
- Пока что возвращает 501 (Not Implemented)
- TODO: Интеграция с novnc-websockify для проксирования WebSocket соединения

## Тестирование

### FORCE_CAPTCHA=1

Для тестирования пайплайна без реальной капчи Яндекса:

```bash
export FORCE_CAPTCHA=1
python3 src/worker.py
```

Парсер искусственно вернёт `captcha_detected` с сохранением сессии.

## Структура БД

### Поля в ParseQueue

```sql
captcha_required BOOLEAN DEFAULT FALSE
captcha_url TEXT
captcha_session_id TEXT
captcha_token TEXT
captcha_vnc_path TEXT
captcha_started_at TIMESTAMP
captcha_status TEXT  -- 'waiting' | 'resume' | 'expired'
resume_requested BOOLEAN DEFAULT FALSE
```

### Индекс

```sql
CREATE INDEX idx_parsequeue_captcha_status 
ON parsequeue(captcha_status) 
WHERE captcha_status IS NOT NULL;
```

## Миграция

Применить миграцию для добавления полей:

```bash
python3 src/migrations/add_captcha_fields.py
```

## Реестр сессий

Воркер хранит активные сессии в памяти:

```python
ACTIVE_CAPTCHA_SESSIONS: dict[str, dict] = {
    "session_id": {
        "task_id": str,
        "browser": Browser,
        "context": BrowserContext,
        "page": Page,
        "created_at": datetime,
    }
}
```

**Важно:** Сессии хранятся только в памяти воркера. При перезапуске воркера все активные сессии теряются.

## Ограничения

1. **Никаких новых антидетект/обходов** - текущий `parser_interception.py` оставлен как есть
2. **Браузер НЕ закрывается** при капче (только при завершении или таймауте)
3. **Таймаут 30 минут** - после этого сессия закрывается
4. **TTL токена 15 минут** - для безопасности доступа к noVNC

## TODO

- [ ] Интеграция с novnc-websockify для проксирования WebSocket соединения
- [ ] Сохранение сессий в БД/Redis для переживания перезапуска воркера
- [ ] Уведомления оператора о новых задачах с капчей
- [ ] Статистика решения капчи (время, успешность)
