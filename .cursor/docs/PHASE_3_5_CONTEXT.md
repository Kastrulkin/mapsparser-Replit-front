# Phase 3.5 Implementation - Контекст для Cursor

**Источник:** Контекст от КИми  
**Дата:** 2026-02-01  
**Статус:** Активный контекст для разработки

---

## 🎯 Цель Phase 3.5

**Рефакторинг `main.py` (~10,000 строк) с выносом SQL в Repository Pattern.**

- **Stack**: Flask + PostgreSQL (миграция с SQLite завершена, но схема "грязная")
- **Проблема**: `main.py` - God File с raw SQL (`cursor.execute`)
- **Решение**: Repository Pattern (`BusinessRepository`, `ServiceRepository`, `ReviewRepository`)
- **Важно**: БЕЗ перехода на ORM (SQLAlchemy пока не используем)

---

## 📐 Философия Phase 3.5

### "Data Integrity First, Code Second"

**Порядок действий:**
1. ✅ Сначала чистим данные и накладываем constraints
2. ✅ Потом пишем код репозиториев

**Почему:** Иначе получим "красивый код с гнилыми данными".

---

## 🚫 Жесткие Ограничения (Не нарушать!)

### A. SQL Синтаксис (Ловушка)

#### ❌ ЗАПРЕЩЕНО:
```sql
SELECT * EXCLUDING chatgpt_enabled FROM businesses
```
**Такого синтаксиса нет в PostgreSQL/SQLite!**

#### ✅ ОБЯЗАТЕЛЬНО: Explicit column lists
```python
# Правильно
SELECT id, name, owner_id, ai_agent_type FROM businesses WHERE id = %s

# Неправильно
SELECT * EXCLUDING chatgpt_enabled FROM businesses
```

#### 💡 Альтернатива:
Создать VIEW `businesses_clean` (без legacy колонок) и селектить из него.

---

### B. Порядок Операций (Critical Path)

#### 1. Backup (ОБЯЗАТЕЛЬНО)
- `pg_dump` (файл вне сервера)
- `CREATE TABLE ..._backup` (для быстрого rollback)

#### 2. Data Cleanup (Перед constraints!)
- Удалить orphaned `UserServices` (где `business_id IS NULL`)
- Исправить `UserServices.user_id = NULL` → присвоить `Businesses.owner_id`

#### 3. Constraints (Только после cleanup!)
- **FK**: `ON DELETE RESTRICT` (не CASCADE!)
- **Unique**: `CREATE UNIQUE INDEX CONCURRENTLY`
  - ⚠️ **КРИТИЧНО**: Не забыть `autocommit=True` в psycopg2!
  - Иначе упадет с ошибкой: "cannot execute CONCURRENTLY in a transaction block"
- **Проверка перед FK**: Убедиться, что все `Businesses.owner_id` существуют в `Users.id`
  - Иначе FK creation упадет

---

### C. Архитектура Repository

#### ❌ ЗАПРЕЩЕНО:

1. **Commit в Repository:**
```python
# НЕПРАВИЛЬНО
def create_business(self, ...):
    cursor.execute(...)
    self.db.conn.commit()  # ❌ НЕТ!
```

2. **Создание новых подключений:**
```python
# НЕПРАВИЛЬНО
conn = sqlite3.connect(...)  # ❌ Утечки пула!
```

3. **Пропуск SQL-traceback наружу:**
```python
# НЕПРАВИЛЬНО
except Exception as e:
    raise e  # ❌ SQL-ошибки наружу!
```

#### ✅ ОБЯЗАТЕЛЬНО:

1. **No Commit в Repository:**
```python
# ПРАВИЛЬНО
def create_business(self, ...):
    cursor.execute(...)
    # НЕТ commit() - делается на уровне route handler
```

2. **Connection через Flask `g.db`:**
```python
# ПРАВИЛЬНО
from flask import g

def get_db():
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db
```

3. **Обработка ошибок:**
```python
# ПРАВИЛЬНО
from psycopg2 import IntegrityError
from psycopg2.errorcodes import UNIQUE_VIOLATION, FOREIGN_KEY_VIOLATION

try:
    cursor.execute(...)
except IntegrityError as e:
    if e.pgcode == UNIQUE_VIOLATION:  # '23505'
        raise DuplicateServiceError(...)
    elif e.pgcode == FOREIGN_KEY_VIOLATION:  # '23503'
        raise OrphanRecordError(...)
    raise
```
**Почему `e.pgcode`, а не парсинг строки:**
- Надежнее (не зависит от локали сообщения об ошибке)
- Явные коды ошибок PostgreSQL
- Не ломается при изменении текста ошибки

4. **Legacy колонки:**
```python
# ПРАВИЛЬНО - игнорировать chatgpt_* полностью
SELECT id, name, owner_id, ai_agent_type 
FROM businesses 
WHERE id = %s
# НЕ включать chatgpt_enabled, chatgpt_api_key и т.д.
```

---

### D. Feature Flags (Granularity)

#### ❌ НЕПРАВИЛЬНО:
```python
USE_REPOSITORIES = True  # Глобальный флаг
```

#### ✅ ПРАВИЛЬНО:
```python
# src/config.py
USE_BUSINESS_REPOSITORY = True
USE_SERVICE_REPOSITORY = False  # Пока не стабилен
USE_REVIEW_REPOSITORY = True
```

**Использование:**
```python
from config import USE_BUSINESS_REPOSITORY

if USE_BUSINESS_REPOSITORY:
    repo = BusinessRepository(g.db)
    business = repo.get_by_id(business_id)
else:
    # Legacy код
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM Businesses WHERE id = ?", (business_id,))
```

---

### E. Golden Master Testing

#### Цель:
Убедиться, что рефакторинг не сломал функциональность.

#### Процесс:

1. **Capture (до рефакторинга):**
```python
# tests/fixtures/golden/businesses_list.json
{
  "businesses": [...],
  "total": 42
}
```

2. **Compare (после рефакторинга):**
```python
# tests/test_golden_master.py
def test_businesses_list_matches_golden():
    response = client.get('/api/businesses')
    actual = response.json
    
    with open('tests/fixtures/golden/businesses_list.json') as f:
        expected = json.load(f)
    
    assert_json_equal(actual, expected)
```

3. **Важно:**
- Использовать `json.dumps(sort_keys=True)` (игнорировать порядок ключей)
- Tolerance для float (`4.5` vs `4.50`)

---

## 📁 Файловая Структура

```
src/
  repositories/
    __init__.py
    base.py              # Base class с логированием (logger.debug(SQL))
    business_repository.py
    service_repository.py
    review_repository.py
  config.py              # Фича-флаги USE_*_REPOSITORY
    
tests/
  fixtures/
    golden/
      businesses_list.json
  test_golden_master.py  # Сравнение legacy vs new
```

---

## ✅ Go/No-Go Чеклист (Перед стартом работ)

- [ ] Все orphaned records удалены (user_id NULL + business_id NULL)
- [ ] `pg_dump` сохранен на S3/внешний диск (не только `_backup` таблица)
- [ ] `CREATE UNIQUE INDEX CONCURRENTLY` протестирован на копии БД
  - Проверено, что не блокирует таблицу
  - Проверено, что `autocommit=True` работает
- [ ] Написан `rollback_3_5.sh` (скрипт отката FK/Unique constraints за <5 минут)
- [ ] Code Freeze объявлен: парсеры (`worker.py`) не пишут в БД во время миграции
  - **Уточнение:** Достаточно остановить запись (INSERT/UPDATE)
  - Чтение (SELECT) можно оставить
  - Альтернатива: использовать `SET lock_timeout` на время создания индексов

---

## 🔍 Текущее Состояние Проекта

### ✅ Что уже есть:

1. **Начальная реализация Repository Pattern:**
   - `src/repositories/business_repository.py`
   - `src/repositories/external_data_repository.py`

2. **Query Adapter:**
   - `src/query_adapter.py` - конвертация SQLite → PostgreSQL

3. **Database Manager:**
   - `src/database_manager.py` - поддержка PostgreSQL через wrappers

### ⚠️ Что нужно исправить:

1. **`SELECT *` в репозиториях:**
   - `business_repository.py` использует `SELECT *` (нарушение правил)
   - Нужно заменить на explicit column lists

2. **Commit в репозиториях:**
   - `business_repository.py` делает `self.db.conn.commit()` (нарушение правил)
   - Нужно убрать commit, делать на уровне route handler

3. **Нет использования `g.db`:**
   - Репозитории создают свои подключения
   - Нужно использовать Flask `g.db`

4. **Нет feature flags:**
   - Нет `config.py` с `USE_*_REPOSITORY`
   - Нужно создать и использовать

5. **Нет Golden Master Testing:**
   - Нет `tests/fixtures/golden/`
   - Нет `test_golden_master.py`

---

## 💡 Как использовать в Cursor

**Скопируйте этот контекст в чат Cursor с префиксом:**

> "Вот контекст нашего текущего технического задания (Phase 3.5). Придерживайся этих ограничений при генерации кода. Особое внимание на: explicit column lists (no SELECT *), CONCURRENTLY indexes с autocommit, transaction management (no commits in repos), и Go/No-Go чеклист перед деплоем."

Это даст Cursor достаточно контекста, чтобы не генерировать опасный код (типа `EXCLUDING` или коммитов внутри Repository).

---

## 📚 Связанные Документы

- `.cursor/docs/POSTGRES_MIGRATION_ANALYSIS.md` - анализ миграции на PostgreSQL
- `.cursor/docs/Architect_audit_report.md` - архитектурный отчет
- `postgres_migration_guide.md` - руководство по миграции

---

## 🎯 Приоритеты

1. **Критично:** Исправить существующие репозитории (убрать `SELECT *`, убрать commit)
2. **Важно:** Создать feature flags и использовать `g.db`
3. **Важно:** Настроить Golden Master Testing
4. **Желательно:** Создать `base.py` с логированием SQL
