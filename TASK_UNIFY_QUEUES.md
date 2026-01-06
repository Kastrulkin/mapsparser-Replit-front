# Задача: Объединение SyncQueue и ParseQueue в единую очередь

**Дата:** 2025-01-03  
**Приоритет:** Высокий  
**Исполнитель:** Кодер

---

## Текущее состояние

**Уже реализовано (см. IMPLEMENTATION.md - "2025-01-03 - Асинхронная синхронизация Яндекс.Бизнес через очередь"):**
- ✅ Создана таблица `SyncQueue` и она работает
- ✅ Добавлена асинхронность: эндпоинт `/api/admin/yandex/sync/business/<business_id>` добавляет задачи в SyncQueue
- ✅ Реализована функция `process_sync_queue()` в `worker.py` (строки 319-646)
- ✅ Добавлен эндпоинт `/api/admin/yandex/sync/status/<sync_id>` для проверки статуса (строки 5905-5945)
- ✅ Синхронизация работает в фоне через worker
- ✅ Функция `_sync_yandex_business_sync_task()` реализована в `main.py` (строки 5591-5945)

**Проблема:**
Сейчас есть две отдельные очереди:
- **ParseQueue** - для парсинга публичных карт (обрабатывается `process_queue()`)
- **SyncQueue** - для синхронизации внешних источников (обрабатывается `process_sync_queue()`)

Это создает путаницу и дублирование логики. Нужна единая очередь для всех задач.

**Цель:**
Объединить SyncQueue в ParseQueue, чтобы была единая логика обработки всех задач через одну очередь.

---

## Решение

Объединить SyncQueue в ParseQueue, добавив поле `task_type` для различения типов задач.

---

## План изменений

### Этап 1: Расширение ParseQueue

**Файл:** `src/init_database_schema.py`

**Добавить поля в ParseQueue (миграция для существующих таблиц):**
```sql
-- Проверяем и добавляем поля только если их нет
ALTER TABLE ParseQueue ADD COLUMN task_type TEXT DEFAULT 'parse_card';
ALTER TABLE ParseQueue ADD COLUMN account_id TEXT;
ALTER TABLE ParseQueue ADD COLUMN source TEXT;
ALTER TABLE ParseQueue ADD COLUMN error_message TEXT;
ALTER TABLE ParseQueue ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

**Примечание:** SQLite не поддерживает `IF NOT EXISTS` для `ALTER TABLE ADD COLUMN`, поэтому нужно проверять наличие колонок через `PRAGMA table_info()` перед добавлением.

**Типы задач:**
- `parse_card` - парсинг публичных карт (текущий, по умолчанию)
- `sync_yandex_business` - синхронизация Яндекс.Бизнес
- `sync_google_business` - синхронизация Google Business
- `sync_2gis` - синхронизация 2ГИС

**Структура ParseQueue после изменений:**
```sql
CREATE TABLE ParseQueue (
    id TEXT PRIMARY KEY,
    url TEXT,                    -- для parse_card
    user_id TEXT NOT NULL,
    business_id TEXT,
    task_type TEXT DEFAULT 'parse_card',  -- НОВОЕ: тип задачи
    account_id TEXT,             -- НОВОЕ: для sync задач
    source TEXT,                 -- НОВОЕ: 'yandex_business', 'google_business', '2gis'
    status TEXT NOT NULL DEFAULT 'pending',
    retry_after TEXT,
    error_message TEXT,          -- НОВОЕ: сообщение об ошибке
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- НОВОЕ
    FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
    FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
)
```

---

### Этап 2: Миграция данных из SyncQueue в ParseQueue

**Файл:** `src/migrate_syncqueue_to_parsequeue.py` (создать)

**Логика миграции:**
1. Проверить наличие SyncQueue
2. Проверить наличие полей в ParseQueue (добавить если нет)
3. Для каждой записи в SyncQueue:
   - Создать запись в ParseQueue с `task_type = 'sync_yandex_business'` (или другой source)
   - Скопировать `business_id`, `account_id`, `source`, `status`, `error_message`
   - Сохранить `created_at`, `updated_at`
   - Получить `user_id` из Businesses (owner_id)
4. Проверить, что все данные перенесены
5. Удалить SyncQueue после миграции (только если миграция успешна)

**SQL миграции:**
```sql
-- Копируем данные из SyncQueue в ParseQueue
-- Важно: проверяем, что запись еще не существует в ParseQueue
INSERT INTO ParseQueue (
    id, business_id, account_id, task_type, source, 
    status, error_message, created_at, updated_at, user_id, url
)
SELECT 
    SyncQueue.id,
    SyncQueue.business_id,
    SyncQueue.account_id,
    CASE 
        WHEN SyncQueue.source = 'yandex_business' THEN 'sync_yandex_business'
        WHEN SyncQueue.source = 'google_business' THEN 'sync_google_business'
        WHEN SyncQueue.source = '2gis' THEN 'sync_2gis'
        ELSE 'sync_unknown'
    END as task_type,
    SyncQueue.source,
    SyncQueue.status,
    SyncQueue.error_message,
    SyncQueue.created_at,
    SyncQueue.updated_at,
    COALESCE(
        (SELECT owner_id FROM Businesses WHERE Businesses.id = SyncQueue.business_id LIMIT 1),
        ''  -- fallback, если бизнес не найден
    ) as user_id,
    '' as url  -- для sync задач url не нужен
FROM SyncQueue
WHERE NOT EXISTS (
    SELECT 1 FROM ParseQueue WHERE ParseQueue.id = SyncQueue.id
);
```

**Проверка перед миграцией:**
```sql
-- Проверить количество записей в SyncQueue
SELECT COUNT(*) FROM SyncQueue;

-- Проверить количество записей в ParseQueue до миграции
SELECT COUNT(*) FROM ParseQueue;

-- Проверить количество записей в ParseQueue после миграции
SELECT COUNT(*) FROM ParseQueue WHERE task_type LIKE 'sync_%';
```

---

### Этап 3: Изменение worker.py

**Файл:** `src/worker.py`

**Текущее состояние:**
- ✅ `process_queue()` - обрабатывает ParseQueue (парсинг карт)
- ✅ `process_sync_queue()` - обрабатывает SyncQueue (синхронизация)
- ✅ В main loop вызываются обе функции: `process_queue()` и `process_sync_queue()`

**Изменения:**
1. Объединить `process_queue()` и `process_sync_queue()` в одну функцию `process_queue()`
2. Добавить обработку разных типов задач в `process_queue()`:
   - `task_type = 'parse_card'` или `NULL` → использовать `parse_yandex_card()` (существующая логика)
   - `task_type = 'sync_yandex_business'` → использовать логику из `process_sync_queue()` (YandexBusinessParser)
   - `task_type = 'sync_google_business'` → использовать `GoogleBusinessParser` (будущее)
   - `task_type = 'sync_2gis'` → использовать `TwoGisBusinessParser` (будущее)
3. Удалить функцию `process_sync_queue()` после объединения
4. Убрать вызов `process_sync_queue()` из main loop

**Пример изменения:**
```python
def process_queue():
    """Обрабатывает очередь парсинга и синхронизации"""
    queue_dict = None
    
    # Получаем задачу из очереди
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем задачу (parse_card или sync)
        # Важно: обрабатываем и старые задачи без task_type (parse_card по умолчанию)
        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT * FROM ParseQueue 
            WHERE status = 'pending' 
               OR (status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?))
            ORDER BY 
                CASE WHEN status = 'pending' THEN 1 ELSE 2 END,
                created_at ASC 
            LIMIT 1
        """, (now,))
        
        queue_item = cursor.fetchone()
        if not queue_item:
            return
        
        queue_dict = dict(queue_item)
        cursor.execute("UPDATE ParseQueue SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                      ("processing", queue_dict["id"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    
    if not queue_dict:
        return
    
    # Определяем тип задачи (по умолчанию parse_card для обратной совместимости)
    task_type = queue_dict.get("task_type") or "parse_card"
    
    # Обрабатываем в зависимости от типа задачи
    if task_type == "parse_card" or task_type is None:
        # Обычный парсинг карт (существующая логика из process_queue)
        # ... весь существующий код парсинга карт ...
        card_data = parse_yandex_card(queue_dict["url"])
        # ... сохраняем результаты ...
        
    elif task_type == "sync_yandex_business":
        # Синхронизация Яндекс.Бизнес (логика из process_sync_queue)
        account_id = queue_dict.get("account_id")
        business_id = queue_dict.get("business_id")
        
        if not account_id or not business_id:
            # Обновляем статус на error
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ParseQueue 
                SET status = 'error', 
                    error_message = 'Отсутствует account_id или business_id',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (queue_dict["id"],))
            conn.commit()
            conn.close()
            return
        
        # Используем существующую функцию из main.py
        from main import _sync_yandex_business_sync_task
        success = _sync_yandex_business_sync_task(
            queue_dict["id"],
            business_id,
            account_id
        )
        
        # Статус обновляется внутри _sync_yandex_business_sync_task
        
    elif task_type in ["sync_google_business", "sync_2gis"]:
        # Аналогично для других источников (будущее)
        # ...
        pass
```

**Важно:** 
- Сохранить всю существующую логику из `process_sync_queue()` для `sync_yandex_business`
- Использовать существующую функцию `_sync_yandex_business_sync_task()` из `main.py`
- Обратная совместимость: старые задачи без `task_type` должны работать как `parse_card`

**Примечание:** 
- Функция `_sync_yandex_business_sync_task()` уже существует в `main.py` (строки 5591-5945)
- Нужно использовать её, а не создавать новую
- Логика синхронизации уже реализована в `process_sync_queue()` (строки 319-646)
- Нужно перенести эту логику в `process_queue()` для обработки задач с `task_type = 'sync_yandex_business'`

---

### Этап 4: Изменение эндпоинта синхронизации

**Файл:** `src/main.py` (строки 5552-5579)

**Текущее состояние:**
- ✅ Эндпоинт уже добавляет задачи в SyncQueue (асинхронно)
- ✅ Возвращает ответ "синхронизация запущена"

**Изменения:**
- Изменить INSERT: использовать ParseQueue вместо SyncQueue
- Добавить `task_type = 'sync_yandex_business'`
- Добавить `user_id` из авторизованного пользователя
- Поле `url` можно оставить пустым или NULL (для sync задач не нужно)

**Пример изменения:**
```python
# Было (строки 5559-5562):
cursor.execute("""
    INSERT INTO SyncQueue (id, business_id, account_id, source, status, created_at, updated_at)
    VALUES (?, ?, ?, 'yandex_business', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""", (sync_id, business_id, account_id))

# Стало:
cursor.execute("""
    INSERT INTO ParseQueue (
        id, business_id, account_id, task_type, source, 
        status, user_id, url, created_at, updated_at
    )
    VALUES (?, ?, ?, 'sync_yandex_business', 'yandex_business', 
            'pending', ?, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""", (sync_id, business_id, account_id, user_data["user_id"]))
```

**Также изменить:**
- Переименовать `sync_id` → `task_id` для единообразия (опционально)
- Обновить ответ: `"sync_id"` → `"task_id"` (опционально)

---

### Этап 5: Удаление SyncQueue и обновление кода

**Файл:** `src/migrate_syncqueue_to_parsequeue.py`

**После успешной миграции данных:**
```sql
-- Удалить индексы
DROP INDEX IF EXISTS idx_syncqueue_status;
DROP INDEX IF EXISTS idx_syncqueue_business_id;
DROP INDEX IF EXISTS idx_syncqueue_created_at;

-- Удалить таблицу
DROP TABLE IF EXISTS SyncQueue;
```

**Файл:** `src/init_database_schema.py`

**Изменения:**
- Убрать создание SyncQueue (строки 117-131)
- Убрать создание индексов SyncQueue (строки 363-366)

**Файл:** `src/worker.py`

**Изменения:**
- Удалить функцию `process_sync_queue()` (строки 319-646)
- Убрать вызов `process_sync_queue()` из main loop (строка 641)

**Файл:** `src/main.py`

**Изменения:**
- Убрать эндпоинт `/api/admin/yandex/sync/status/<sync_id>` (если есть) или изменить на ParseQueue
- Обновить логику проверки статуса для использования ParseQueue

---

### Этап 6: Обновление эндпоинта статуса синхронизации

**Файл:** `src/main.py` (строки 5905-5945)

**Текущее состояние:**
- ✅ Эндпоинт `/api/admin/yandex/sync/status/<sync_id>` проверяет статус в SyncQueue

**Изменения:**
- Изменить запрос: использовать ParseQueue вместо SyncQueue
- Фильтровать по `task_type = 'sync_yandex_business'`

**Пример:**
```python
# Было:
cursor.execute("SELECT status, error_message, created_at, updated_at FROM SyncQueue WHERE id = ?", (sync_id,))

# Стало:
cursor.execute("""
    SELECT status, error_message, created_at, updated_at 
    FROM ParseQueue 
    WHERE id = ? AND task_type = 'sync_yandex_business'
""", (sync_id,))
```

### Этап 7: Обновление init_database_schema.py

**Файл:** `src/init_database_schema.py`

**Изменения:**
1. Убрать создание SyncQueue (строки 117-131)
2. Убрать индексы SyncQueue (строки 363-366)
3. Добавить проверку и добавление полей в ParseQueue при инициализации:
   - Проверять наличие полей через `PRAGMA table_info(ParseQueue)`
   - Добавлять только отсутствующие поля

---

## Порядок выполнения

### Важно: Сначала расширить ParseQueue, потом мигрировать данные

1. **Создать миграцию** `src/migrate_syncqueue_to_parsequeue.py`:
   - Проверить наличие полей в ParseQueue через `PRAGMA table_info(ParseQueue)`
   - Добавить отсутствующие поля: `task_type`, `account_id`, `source`, `error_message`, `updated_at`
   - Перенести данные из SyncQueue в ParseQueue
   - Проверить количество перенесенных записей (ДО и ПОСЛЕ)
   - **НЕ удалять SyncQueue** на этом этапе (только после тестирования)

2. **Изменить `init_database_schema.py`**:
   - Добавить проверку и добавление полей в ParseQueue при инициализации (для новых БД)
   - Пока оставить создание SyncQueue (удалить после успешного тестирования)

3. **Изменить `worker.py`**:
   - Изучить логику из `process_sync_queue()` (строки 319-646)
   - Добавить обработку `task_type = 'sync_yandex_business'` в `process_queue()`
   - Использовать существующую функцию `_sync_yandex_business_sync_task()` из `main.py`
   - Сохранить всю логику обработки ошибок
   - Убедиться, что старые задачи без `task_type` обрабатываются как `parse_card`
   - Пока оставить `process_sync_queue()` (удалить после тестирования)

4. **Изменить `main.py`**:
   - Изменить эндпоинт синхронизации (строки 5552-5579): использовать ParseQueue вместо SyncQueue
   - Изменить эндпоинт статуса (строки 5905-5945): использовать ParseQueue вместо SyncQueue

5. **Применить миграцию** - перенести данные из SyncQueue в ParseQueue

6. **Протестировать** - проверить работу парсинга и синхронизации:
   - Парсинг карт должен работать как раньше
   - Синхронизация должна работать через ParseQueue
   - Проверить логи worker.py

7. **Удалить SyncQueue** - только после успешного тестирования:
   - Удалить функцию `process_sync_queue()` из `worker.py`
   - Убрать вызов `process_sync_queue()` из main loop
   - Убрать создание SyncQueue из `init_database_schema.py`
   - Удалить таблицу SyncQueue через миграцию

---

## Чеклист для кодера

### Подготовка
- [ ] Изучить структуру ParseQueue и SyncQueue
- [ ] Понять логику обработки в worker.py
- [ ] Создать бэкап БД

### Этап 1: Расширение ParseQueue
- [ ] Создать миграцию `src/migrate_syncqueue_to_parsequeue.py`
- [ ] В миграции добавить проверку и добавление полей в ParseQueue:
  - `task_type TEXT DEFAULT 'parse_card'`
  - `account_id TEXT`
  - `source TEXT`
  - `error_message TEXT`
  - `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- [ ] Использовать `PRAGMA table_info(ParseQueue)` для проверки наличия полей
- [ ] Добавлять только отсутствующие поля (SQLite не поддерживает IF NOT EXISTS для ALTER TABLE)

### Этап 2: Миграция данных
- [ ] Создать `src/migrate_syncqueue_to_parsequeue.py`
- [ ] Скопировать данные из SyncQueue в ParseQueue
- [ ] Проверить количество перенесенных записей
- [ ] Убедиться, что все данные перенесены

### Этап 3: Изменение worker.py
- [ ] Изучить логику из `process_sync_queue()` (строки 319-646)
- [ ] Добавить обработку `task_type = 'sync_yandex_business'` в `process_queue()`
- [ ] Использовать существующую функцию `_sync_yandex_business_sync_task()` из `main.py`
- [ ] Сохранить всю логику обработки ошибок из `process_sync_queue()`
- [ ] Убедиться, что старые задачи без `task_type` обрабатываются как `parse_card`
- [ ] Удалить функцию `process_sync_queue()` после объединения
- [ ] Убрать вызов `process_sync_queue()` из main loop (строка 641)

### Этап 4: Изменение main.py
- [ ] Изменить эндпоинт `/api/admin/yandex/sync/business/<business_id>` (строки 5552-5579):
  - Заменить INSERT в SyncQueue на INSERT в ParseQueue
  - Добавить `task_type = 'sync_yandex_business'`
  - Добавить `user_id` из авторизованного пользователя
  - Поле `url` оставить пустым или NULL
- [ ] Изменить эндпоинт `/api/admin/yandex/sync/status/<sync_id>` (строки 5905-5945):
  - Заменить запрос к SyncQueue на ParseQueue
  - Добавить фильтр `task_type = 'sync_yandex_business'`
- [ ] Функцию `_sync_yandex_business_sync_task()` оставить (используется в worker.py)

### Этап 5: Удаление SyncQueue
- [ ] Удалить индексы SyncQueue (после миграции данных)
- [ ] Удалить таблицу SyncQueue (только после успешного тестирования)
- [ ] Убрать создание SyncQueue из `init_database_schema.py` (строки 117-131)
- [ ] Убрать индексы SyncQueue из `init_database_schema.py` (строки 363-366)

### Тестирование
- [ ] Протестировать парсинг карт (должно работать как раньше)
  - Добавить задачу парсинга в ParseQueue
  - Проверить, что worker обрабатывает задачу
  - Проверить, что результаты сохраняются
- [ ] Протестировать синхронизацию Яндекс.Бизнес:
  - Запустить синхронизацию через эндпоинт
  - Проверить, что задача добавлена в ParseQueue с `task_type = 'sync_yandex_business'`
  - Проверить, что worker обрабатывает задачу
  - Проверить, что данные синхронизированы (ExternalBusinessReviews, ExternalBusinessStats)
  - Проверить статус через эндпоинт `/api/admin/yandex/sync/status/<task_id>`
- [ ] Проверить логи worker.py:
  - Должны быть сообщения об обработке задач обоих типов
  - Не должно быть ошибок
- [ ] Проверить статусы задач в ParseQueue:
  - Задачи парсинга: `task_type = 'parse_card'` или `NULL`
  - Задачи синхронизации: `task_type = 'sync_yandex_business'`

---

## Проверка после изменений

### Проверить структуру ParseQueue
```sql
PRAGMA table_info(ParseQueue);
-- Должны быть поля: task_type, account_id, source, error_message, updated_at
```

### Проверить данные
```sql
-- Проверить задачи синхронизации
SELECT * FROM ParseQueue WHERE task_type = 'sync_yandex_business';

-- Проверить задачи парсинга
SELECT * FROM ParseQueue WHERE task_type = 'parse_card' OR task_type IS NULL;
```

### Проверить работу worker
```bash
# Проверить логи worker
tail -f /tmp/seo_worker.out

# Должны быть сообщения:
# "Обрабатываю заявку: {'task_type': 'sync_yandex_business', ...}"
# "✅ Синхронизация Яндекс.Бизнес завершена"
```

---

## Ожидаемый результат

**После объединения:**
- Одна очередь ParseQueue для всех задач
- Единая логика обработки в worker.py
- Нет дублирования кода
- Упрощение поддержки

**Преимущества:**
- Единая точка обработки задач
- Легче добавлять новые типы задач
- Упрощение мониторинга (одна таблица)
- Меньше кода для поддержки

---

## Важные замечания

1. **Обратная совместимость:**
   - Старые задачи парсинга (без `task_type`) должны работать
   - Использовать `task_type = 'parse_card'` по умолчанию

2. **Миграция данных:**
   - Обязательно создать бэкап перед миграцией
   - Проверить количество записей до и после миграции
   - Убедиться, что все данные перенесены

3. **Тестирование:**
   - Сначала протестировать на локальной БД
   - Проверить работу парсинга (не должно сломаться)
   - Проверить работу синхронизации (должно работать как раньше)

---

## Дополнительная информация

**Файлы для изучения:**
- `src/worker.py` - текущая логика обработки очередей
- `src/main.py` - эндпоинт синхронизации (строки 5484-5590)
- `src/init_database_schema.py` - структура таблиц
- `src/yandex_business_parser.py` - парсер Яндекс.Бизнес

**Связанные задачи:**
- TASK_NGINX_TIMEOUTS_FIX.md - исправление таймаутов (можно отложить после объединения очередей)

