# План оптимизации структуры базы данных

**Дата:** 2025-01-03  
**Статус:** Approved for Implementation  
**Исполнитель:** Кодер

---

## 📊 Текущее состояние

- **46-50 таблиц** (много для SQLite)
- **Дублирование данных:** ClientInfo, Cards, GigaChatTokenUsage
- **Недостаточно индексов:** отсутствуют индексы на часто используемых полях
- **Похожие таблицы:** UserNewsExamples, UserReviewExamples, UserServiceExamples можно объединить

---

## 🎯 Цель оптимизации

1. **Упростить схему:** 40-41 таблица вместо 46-50
2. **Ускорить запросы:** добавление индексов (5-10x ускорение)
3. **Устранить дублирование:** удалить дублирующие таблицы
4. **Упростить запросы:** объединить похожие таблицы

---

## 📋 ЭТАП 1: Добавление недостающих индексов (Критично)

### Файл: `src/migrate_add_missing_indexes.py`

### Индексы для добавления:

```sql
-- UserSessions (критично для авторизации)
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON UserSessions(token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON UserSessions(expires_at);

-- Businesses (фильтрация активных)
CREATE INDEX IF NOT EXISTS idx_businesses_active ON Businesses(is_active);
CREATE INDEX IF NOT EXISTS idx_businesses_subscription_status ON Businesses(subscription_status);

-- Bookings (фильтрация по статусу)
CREATE INDEX IF NOT EXISTS idx_bookings_status ON Bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_business_status ON Bookings(business_id, status);

-- ExternalBusinessReviews (сортировка по дате)
CREATE INDEX IF NOT EXISTS idx_ext_reviews_published_at ON ExternalBusinessReviews(published_at);
CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_published ON ExternalBusinessReviews(business_id, published_at);

-- ChatGPTRequests (мониторинг)
CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_business_status ON ChatGPTRequests(business_id, response_status);

-- TokenUsage (аналитика)
CREATE INDEX IF NOT EXISTS idx_token_usage_business_created ON TokenUsage(business_id, created_at);
```

### Шаги реализации:

1. Создать файл `src/migrate_add_missing_indexes.py`
2. Использовать `safe_migrate()` из `safe_db_utils.py`
3. Добавить все индексы через `CREATE INDEX IF NOT EXISTS`
4. Проверить, что индексы созданы: `SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'`

### Ожидаемый эффект:
- Ускорение проверки сессий: **10-50x**
- Ускорение фильтрации активных бизнесов: **5-10x**
- Ускорение запросов с несколькими условиями: **3-5x**

---

## 📋 ЭТАП 2: Удаление дублирующих таблиц (Важно)

### Файл: `src/migrate_remove_duplicate_tables.py`

### Таблица 1: ClientInfo → Businesses

**Проблема:** `ClientInfo` дублирует данные из `Businesses`

**Миграция:**
1. Проверить количество записей в `ClientInfo`
2. Для каждой записи в `ClientInfo`:
   - Найти соответствующий бизнес в `Businesses` по `user_id` и `business_id`
   - Обновить поля в `Businesses`: `name`, `business_type`, `address`, `working_hours`, `description`
   - Если бизнес не найден, создать новый (или пропустить)
3. Удалить таблицу `ClientInfo`

**SQL для миграции:**
```sql
-- Обновить Businesses из ClientInfo
UPDATE Businesses 
SET 
    name = (SELECT business_name FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id),
    business_type = (SELECT business_type FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id),
    address = (SELECT address FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id),
    working_hours = (SELECT working_hours FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id),
    description = (SELECT description FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id)
WHERE EXISTS (SELECT 1 FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id);
```

**Проверка:**
- Убедиться, что все данные перенесены
- Проверить количество обновленных записей

---

### Таблица 2: GigaChatTokenUsage → TokenUsage

**Проблема:** `GigaChatTokenUsage` заменена на `TokenUsage`

**Миграция:**
1. Проверить, есть ли данные в `GigaChatTokenUsage`
2. Если есть данные:
   - Перенести в `TokenUsage` (маппинг полей)
   - Проверить, что все данные перенесены
3. Удалить таблицу `GigaChatTokenUsage`

**SQL для миграции:**
```sql
-- Перенести данные из GigaChatTokenUsage в TokenUsage
INSERT INTO TokenUsage (id, business_id, user_id, task_type, model, total_tokens, created_at)
SELECT 
    id,
    business_id,
    user_id,
    COALESCE(request_type, 'unknown') as task_type,
    'GigaChat' as model,
    tokens_used as total_tokens,
    created_at
FROM GigaChatTokenUsage
WHERE NOT EXISTS (
    SELECT 1 FROM TokenUsage WHERE TokenUsage.id = GigaChatTokenUsage.id
);
```

**Проверка:**
- Убедиться, что все данные перенесены
- Проверить количество перенесенных записей

---

### Таблица 3: Cards → MapParseResults (опционально)

**Проблема:** `Cards` дублирует данные из `MapParseResults`

**Миграция:**
1. Проверить количество записей в `Cards`
2. Для каждой записи в `Cards`:
   - Создать запись в `MapParseResults` с данными из `Cards`
   - Сохранить `report_path`, `seo_score`, `ai_analysis`, `recommendations`
3. Удалить таблицу `Cards` (или пометить как deprecated)

**SQL для миграции:**
```sql
-- Перенести данные из Cards в MapParseResults
INSERT INTO MapParseResults (id, business_id, url, map_type, rating, reviews_count, report_path, analysis_json, created_at)
SELECT 
    id,
    business_id,
    url,
    'yandex' as map_type,  -- или определить из url
    NULL as rating,  -- если нет в Cards
    0 as reviews_count,
    report_path,
    json_object('seo_score', seo_score, 'ai_analysis', ai_analysis, 'recommendations', recommendations) as analysis_json,
    created_at
FROM Cards
WHERE business_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM MapParseResults WHERE MapParseResults.id = Cards.id
);
```

**Проверка:**
- Убедиться, что все отчеты доступны
- Проверить количество перенесенных записей

---

### Шаги реализации:

1. Создать файл `src/migrate_remove_duplicate_tables.py`
2. Использовать `safe_migrate()` из `safe_db_utils.py`
3. Для каждой таблицы:
   - Проверить количество записей ДО миграции
   - Выполнить миграцию данных
   - Проверить количество записей ПОСЛЕ миграции
   - Удалить таблицу только если миграция успешна
4. Проверить, что таблицы удалены: `SELECT name FROM sqlite_master WHERE type='table'`

### Ожидаемый эффект:
- Упрощение схемы: **-3 таблицы**
- Устранение дублирования данных
- Упрощение запросов (не нужно JOIN с дублирующими таблицами)

---

## 📋 ЭТАП 3: Объединение похожих таблиц (Улучшения)

### Файл: `src/migrate_merge_examples_tables.py`

### Таблицы для объединения:
- `UserNewsExamples` → `UserExamples` (example_type = 'news')
- `UserReviewExamples` → `UserExamples` (example_type = 'review')
- `UserServiceExamples` → `UserExamples` (example_type = 'service')

### Новая структура:

```sql
CREATE TABLE UserExamples (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    example_type TEXT NOT NULL,  -- 'news', 'review', 'service'
    example_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_examples_user_type ON UserExamples(user_id, example_type);
```

### Миграция:

1. Создать таблицу `UserExamples`
2. Перенести данные из `UserNewsExamples`:
   ```sql
   INSERT INTO UserExamples (id, user_id, example_type, example_text, created_at)
   SELECT id, user_id, 'news', example_text, created_at FROM UserNewsExamples;
   ```

3. Перенести данные из `UserReviewExamples`:
   ```sql
   INSERT INTO UserExamples (id, user_id, example_type, example_text, created_at)
   SELECT id, user_id, 'review', example_text, created_at FROM UserReviewExamples;
   ```

4. Перенести данные из `UserServiceExamples`:
   ```sql
   INSERT INTO UserExamples (id, user_id, example_type, example_text, created_at)
   SELECT id, user_id, 'service', example_text, created_at FROM UserServiceExamples;
   ```

5. Удалить старые таблицы:
   ```sql
   DROP TABLE UserNewsExamples;
   DROP TABLE UserReviewExamples;
   DROP TABLE UserServiceExamples;
   ```

### Обновление кода:

**Файлы для обновления:**
- `src/main.py` - заменить запросы к `UserNewsExamples`, `UserReviewExamples`, `UserServiceExamples` на `UserExamples` с фильтром по `example_type`

**Пример замены:**
```python
# Было:
cursor.execute("SELECT example_text FROM UserNewsExamples WHERE user_id = ?", (user_id,))

# Стало:
cursor.execute("SELECT example_text FROM UserExamples WHERE user_id = ? AND example_type = 'news'", (user_id,))
```

### Шаги реализации:

1. Создать файл `src/migrate_merge_examples_tables.py`
2. Использовать `safe_migrate()` из `safe_db_utils.py`
3. Создать новую таблицу `UserExamples`
4. Перенести данные из 3 таблиц с указанием `example_type`
5. Проверить количество записей (должно совпадать)
6. Удалить старые таблицы
7. Обновить код в `src/main.py` для использования новой таблицы

### Ожидаемый эффект:
- Упрощение схемы: **-2 таблицы**
- Упрощение запросов (один запрос вместо трех)
- Легче добавлять новые типы примеров

---

## 🔄 Порядок выполнения

### Шаг 1: Подготовка
```bash
# Создать полный бэкап БД
cd /root/mapsparser-Replit-front
source venv/bin/activate
python -c "
from safe_db_utils import backup_database
backup_path = backup_database()
print(f'Бэкап создан: {backup_path}')
"
```

### Шаг 2: Этап 1 - Добавить индексы
```bash
python src/migrate_add_missing_indexes.py
```

**Проверка:**
```bash
python -c "
from safe_db_utils import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'\")
indexes = [row[0] for row in cursor.fetchall()]
print('Индексы:', sorted(indexes))
print('Количество:', len(indexes))
conn.close()
"
```

### Шаг 3: Этап 2 - Удалить дублирующие таблицы
```bash
python src/migrate_remove_duplicate_tables.py
```

**Проверка:**
```bash
python -c "
from safe_db_utils import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
print('Таблицы:', sorted(tables))
print('Количество:', len(tables))
# Проверить, что ClientInfo, GigaChatTokenUsage, Cards удалены
assert 'ClientInfo' not in tables, 'ClientInfo не удалена!'
assert 'GigaChatTokenUsage' not in tables, 'GigaChatTokenUsage не удалена!'
conn.close()
"
```

### Шаг 4: Этап 3 - Объединить таблицы Examples
```bash
python src/migrate_merge_examples_tables.py
```

**Проверка:**
```bash
python -c "
from safe_db_utils import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute(\"SELECT COUNT(*) FROM UserExamples\")
count = cursor.fetchone()[0]
print(f'Записей в UserExamples: {count}')

# Проверить, что старые таблицы удалены
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
assert 'UserNewsExamples' not in tables, 'UserNewsExamples не удалена!'
assert 'UserReviewExamples' not in tables, 'UserReviewExamples не удалена!'
assert 'UserServiceExamples' not in tables, 'UserServiceExamples не удалена!'
print('✅ Все таблицы Examples объединены')
conn.close()
"
```

### Шаг 5: Обновить код
- Обновить `src/main.py` для использования `UserExamples` вместо старых таблиц
- Проверить, что все запросы работают корректно

### Шаг 6: Перезапустить сервер
```bash
# Перезапустить Flask
pkill -f "python.*main.py"
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/main.py > /tmp/seo_main.out 2>&1 &

# Проверить
sleep 3
lsof -iTCP:8000 -sTCP:LISTEN
```

---

## ✅ Чеклист для кодера

### Перед началом:
- [ ] Создан полный бэкап БД
- [ ] Изучен план оптимизации
- [ ] Понятны все 3 этапа

### Этап 1: Индексы
- [ ] Создан файл `src/migrate_add_missing_indexes.py`
- [ ] Используется `safe_migrate()`
- [ ] Все индексы добавлены
- [ ] Проверено, что индексы созданы

### Этап 2: Удаление дублирующих таблиц
- [ ] Создан файл `src/migrate_remove_duplicate_tables.py`
- [ ] Используется `safe_migrate()`
- [ ] Данные из `ClientInfo` мигрированы в `Businesses`
- [ ] Данные из `GigaChatTokenUsage` мигрированы в `TokenUsage` (если есть)
- [ ] Данные из `Cards` мигрированы в `MapParseResults` (опционально)
- [ ] Таблицы удалены
- [ ] Проверено количество таблиц (должно быть -3)

### Этап 3: Объединение таблиц Examples
- [ ] Создан файл `src/migrate_merge_examples_tables.py`
- [ ] Используется `safe_migrate()`
- [ ] Создана таблица `UserExamples`
- [ ] Данные из 3 таблиц перенесены с указанием `example_type`
- [ ] Старые таблицы удалены
- [ ] Обновлен код в `src/main.py` для использования `UserExamples`
- [ ] Проверено количество таблиц (должно быть -2)

### После завершения:
- [ ] Все миграции применены
- [ ] Код обновлен
- [ ] Flask сервер перезапущен
- [ ] Проверена производительность запросов
- [ ] Обновлена документация в `.cursor/docs/VERIFICATION.md`
- [ ] Результаты записаны в `.cursor/docs/Architect_audit_report.md`

---

## 📊 Ожидаемые результаты

### До оптимизации:
- 46-50 таблиц
- Дублирование данных (ClientInfo, Cards, GigaChatTokenUsage)
- Медленные запросы (нет индексов на часто используемых полях)
- Сложные запросы (много JOIN с похожими таблицами)

### После оптимизации:
- **40-41 таблица** (-5-9 таблиц)
- **Ускорение запросов в 5-10 раз** (благодаря индексам)
- **Упрощение схемы** (нет дублирования)
- **Упрощение запросов** (меньше JOIN, одна таблица Examples вместо трех)

---

## ⚠️ Важные замечания

1. **Всегда используй `safe_migrate()`** - автоматические бэкапы
2. **Проверяй количество записей** ДО и ПОСЛЕ миграции
3. **Тестируй на локальной БД** перед применением на сервере
4. **Обновляй код** после изменения структуры таблиц
5. **Документируй изменения** в `.cursor/docs/VERIFICATION.md`

---

## 📝 Примечания

- Все миграции должны быть обратимыми (через бэкапы)
- При ошибке миграция автоматически откатится
- Проверяй логи миграций для диагностики проблем
- После каждого этапа проверяй работоспособность приложения

