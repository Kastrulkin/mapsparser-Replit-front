# Анализ миграции на PostgreSQL

**Дата:** 2025-01-06  
**Статус:** Анализ завершен

---

## Обзор изменений

Проект был мигрирован с SQLite на PostgreSQL. Ниже анализ всех изменений и необходимых обновлений.

---

## ✅ Что уже сделано

### 1. Инфраструктура PostgreSQL

- ✅ **`requirements.txt`** - добавлен `psycopg2-binary`
- ✅ **`src/schema_postgres.sql`** - полная схема PostgreSQL
- ✅ **`src/query_adapter.py`** - адаптер для конвертации SQLite → PostgreSQL
  - Конвертация `?` → `%s`
- ✅ **`src/database_manager.py`** - добавлена поддержка PostgreSQL
  - `DBConnectionWrapper` - определяет тип БД из `DB_TYPE` env
  - `DBCursorWrapper` - адаптирует запросы через `QueryAdapter`
- ✅ **`scripts/migrate_to_postgres.py`** - скрипт миграции данных
- ✅ **`postgres_migration_guide.md`** - руководство по миграции

### 2. Конфигурация

- ✅ Переменная окружения `DB_TYPE` (по умолчанию `sqlite`)
- ✅ Переменная окружения `DATABASE_URL` для PostgreSQL

---

## ⚠️ Что нужно исправить

### 1. КРИТИЧНО: `safe_db_utils.py` не поддерживает PostgreSQL

**Проблема:**
`src/safe_db_utils.py` все еще использует только SQLite. Все функции (`get_db_connection()`, `backup_database()`, `safe_migrate()`) работают только с SQLite.

**Файл:** `src/safe_db_utils.py`

**Что нужно сделать:**

1. **Обновить `get_db_connection()`** для поддержки PostgreSQL:

```python
def get_db_connection():
    """Получить соединение с базой данных (SQLite или PostgreSQL)"""
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'postgres':
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL env var is required for PostgreSQL")
        
        conn = psycopg2.connect(database_url)
        # Используем RealDictCursor для совместимости с sqlite3.Row
        conn.cursor_factory = RealDictCursor
        return conn
    else:
        # SQLite (существующий код)
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # WAL режим и PRAGMA только для SQLite
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception as e:
            print(f"⚠️ Не удалось установить PRAGMA: {e}")
        
        return conn
```

2. **Обновить `backup_database()`** для PostgreSQL:

```python
def backup_database():
    """Создать резервную копию базы данных"""
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'postgres':
        # Для PostgreSQL используем pg_dump
        import subprocess
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL env var is required for PostgreSQL")
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"reports_{timestamp}.sql.backup"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        try:
            # Используем pg_dump для создания бэкапа
            subprocess.run(
                ['pg_dump', database_url],
                stdout=open(backup_path, 'w'),
                check=True
            )
            print(f"💾 Создан бэкап PostgreSQL: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ Ошибка создания бэкапа PostgreSQL: {e}")
            return None
    else:
        # SQLite (существующий код)
        # ... существующий код ...
```

3. **Обновить `safe_migrate()`** для PostgreSQL:

```python
def safe_migrate(callback, description=""):
    """Безопасное выполнение миграции с автоматическим бэкапом"""
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    # Создаем бэкап перед миграцией
    backup_path = backup_database()
    if not backup_path:
        print("❌ Не удалось создать бэкап! Миграция отменена.")
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"🔄 Выполняю миграцию: {description}")
        
        # Проверяем существующие данные перед миграцией
        if db_type == 'postgres':
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            businesses_before = cursor.fetchone()[0] if hasattr(cursor.fetchone(), '__getitem__') else cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            services_before = cursor.fetchone()[0] if hasattr(cursor.fetchone(), '__getitem__') else cursor.fetchone()['count']
        else:
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            businesses_before = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            services_before = cursor.fetchone()[0]
        
        print(f"📊 Данные до миграции: {businesses_before} бизнесов, {services_before} услуг")
        
        # Выполняем миграцию
        callback(cursor)
        
        # Проверяем данные после миграции
        if db_type == 'postgres':
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            businesses_after = cursor.fetchone()[0] if hasattr(cursor.fetchone(), '__getitem__') else cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            services_after = cursor.fetchone()[0] if hasattr(cursor.fetchone(), '__getitem__') else cursor.fetchone()['count']
        else:
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            businesses_after = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            services_after = cursor.fetchone()[0]
        
        # Валидация
        if businesses_after < businesses_before:
            raise Exception(f"❌ Количество бизнесов уменьшилось! Было: {businesses_before}, Стало: {businesses_after}")
        if services_after < services_before:
            raise Exception(f"❌ Количество услуг уменьшилось! Было: {services_before}, Стало: {services_after}")
        
        conn.commit()
        print(f"✅ Данные после миграции: {businesses_after} бизнесов, {services_after} услуг")
        print(f"✅ Миграция выполнена успешно! Бэкап: {backup_path}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        print(f"💾 Откат к бэкапу: {backup_path}")
        # Для PostgreSQL восстановление из бэкапа требует pg_restore
        return False
    finally:
        conn.close()
```

### 2. Обновить `init_database_schema.py`

**Проблема:**
`init_database_schema.py` использует SQLite-специфичные команды (`PRAGMA table_info`, `CREATE TABLE IF NOT EXISTS` с INTEGER для boolean).

**Что нужно сделать:**

1. Проверять тип БД и использовать соответствующие команды
2. Для PostgreSQL использовать `schema_postgres.sql` вместо создания таблиц через Python
3. Для SQLite оставить существующий код

### 3. Обновить все миграции

**Проблема:**
Многие миграции используют SQLite-специфичные команды:
- `PRAGMA table_info` → для PostgreSQL использовать `information_schema.columns`
- `INTEGER` для boolean → для PostgreSQL использовать `BOOLEAN`
- `?` в запросах → уже обрабатывается через `QueryAdapter`, но нужно проверить

**Что нужно сделать:**

1. Создать helper функцию для определения типа БД
2. Обновить все миграции для поддержки обоих типов БД
3. Или создать отдельные миграции для PostgreSQL

### 4. Обновить `worker.py` и другие файлы

**Проблема:**
`worker.py`, `auth_system.py`, `telegram_bot.py` и другие файлы используют `safe_db_utils.get_db_connection()` напрямую, но ожидают SQLite-специфичное поведение.

**Что нужно сделать:**

1. Убедиться, что все используют `database_manager.get_db_connection()` (который уже поддерживает PostgreSQL)
2. Или обновить `safe_db_utils.get_db_connection()` для поддержки PostgreSQL

---

## 📋 Чеклист для кодера

### Критичные исправления

- [ ] Обновить `src/safe_db_utils.py`:
  - [ ] `get_db_connection()` - поддержка PostgreSQL
  - [ ] `backup_database()` - поддержка PostgreSQL (pg_dump)
  - [ ] `safe_migrate()` - поддержка PostgreSQL
  - [ ] `restore_from_backup()` - поддержка PostgreSQL (pg_restore)

### Важные обновления

- [ ] Обновить `src/init_database_schema.py`:
  - [ ] Проверка типа БД
  - [ ] Использование `schema_postgres.sql` для PostgreSQL
  - [ ] Сохранение SQLite логики для обратной совместимости

- [ ] Обновить все миграции:
  - [ ] Заменить `PRAGMA table_info` на универсальную функцию
  - [ ] Проверить использование boolean (INTEGER vs BOOLEAN)
  - [ ] Протестировать с PostgreSQL

### Дополнительные улучшения

- [ ] Создать helper функцию для определения типа БД:
  ```python
  def get_db_type():
      return os.getenv('DB_TYPE', 'sqlite').lower()
  ```

- [ ] Обновить документацию:
  - [ ] Обновить `DB_SAFETY_GUIDE.md` с информацией о PostgreSQL
  - [ ] Обновить правила работы с БД в `.cursor/rules/`

- [ ] Протестировать:
  - [ ] Все функции с SQLite
  - [ ] Все функции с PostgreSQL
  - [ ] Миграции на обоих типах БД

---

## 🔍 Дополнительные замечания

### 1. Совместимость типов данных

**SQLite:**
- Boolean: `INTEGER` (0/1)
- Timestamp: `TIMESTAMP` (строка ISO)

**PostgreSQL:**
- Boolean: `BOOLEAN` (true/false)
- Timestamp: `TIMESTAMP` (нативный тип)

**Решение:** `QueryAdapter.adapt_params()` уже обрабатывает boolean, но нужно проверить все места.

### 2. PRAGMA команды

**SQLite:** `PRAGMA table_info`, `PRAGMA journal_mode=WAL`, и т.д.  
**PostgreSQL:** Не поддерживает PRAGMA, нужно использовать `information_schema`.

**Решение:** Создать helper функции для получения информации о таблицах.

### 3. Бэкапы

**SQLite:** Простое копирование файла  
**PostgreSQL:** Требуется `pg_dump` и `pg_restore`

**Решение:** Обновить `backup_database()` и `restore_from_backup()`.

---

## 📝 Рекомендации

1. **Приоритет:** Сначала исправить `safe_db_utils.py` - это критично для работы системы
2. **Тестирование:** Протестировать все изменения на тестовой БД перед применением на продакшене
3. **Документация:** Обновить все документы с информацией о PostgreSQL
4. **Обратная совместимость:** Сохранить поддержку SQLite для разработки

---

## 🔗 Связанные файлы

- `src/safe_db_utils.py` - требует обновления
- `src/database_manager.py` - уже поддерживает PostgreSQL ✅
- `src/query_adapter.py` - уже работает ✅
- `src/schema_postgres.sql` - схема PostgreSQL ✅
- `scripts/migrate_to_postgres.py` - скрипт миграции ✅
- `postgres_migration_guide.md` - руководство ✅
