# Phase 3.5 Production Deployment Checklist

**Дата создания:** 2026-02-01  
**Статус:** ⚠️ Требует доработки перед включением в прод

---

## 🔴 Критические проверки (ОБЯЗАТЕЛЬНО)

### 1. Constraints в БД

**Проверка:**
```sql
-- PostgreSQL
\d ExternalBusinessReviews  -- должен быть UNIQUE(business_id, source, external_review_id)
\d UserServices              -- должен быть FK на Businesses.id и Users.id (если есть)

-- Или через SQL:
SELECT 
    conname, contype, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'ExternalBusinessReviews'::regclass;

SELECT 
    conname, contype, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'UserServices'::regclass;
```

**Ожидаемый результат:**
- `ExternalBusinessReviews`: `UNIQUE (business_id, source, external_review_id)` ✅
- `UserServices`: `FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE` ✅
- `UserServices`: `FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT` (опционально, но рекомендуется)

**Если нет — НЕ ВКЛЮЧАТЬ флаги!** Сначала накатить миграции:
```bash
python scripts/migrate_apply_phase_3_5_constraints.py
```

---

### 2. Cleanup Orphaned Records (должно быть 0)

**Проверка:**
```sql
-- Проверка orphaned UserServices
SELECT COUNT(*) FROM UserServices WHERE business_id IS NULL;
SELECT COUNT(*) FROM UserServices WHERE business_id NOT IN (SELECT id FROM Businesses);

-- Проверка orphaned ExternalBusinessReviews
SELECT COUNT(*) FROM ExternalBusinessReviews WHERE business_id IS NULL;
SELECT COUNT(*) FROM ExternalBusinessReviews WHERE business_id NOT IN (SELECT id FROM Businesses);
```

**Ожидаемый результат:** Все запросы должны вернуть `0`

**Если найдены orphaned records:**
```sql
-- Удалить orphaned UserServices
DELETE FROM UserServices WHERE business_id NOT IN (SELECT id FROM Businesses);

-- Удалить orphaned ExternalBusinessReviews
DELETE FROM ExternalBusinessReviews WHERE business_id NOT IN (SELECT id FROM Businesses);
```

---

### 3. Проверка репозиториев на commit() и SELECT *

**Проверка:**
```bash
# Должно быть пусто (только комментарии)
grep -n "\.commit()" src/repositories/*.py | grep -v "#" | grep -v "Note:"
grep -n "SELECT \*" src/repositories/*.py | grep -v "#" | grep -v "no SELECT"
```

**Ожидаемый результат:** Пустой вывод (или только комментарии)

**Текущий статус:** ✅ Проверено - репозитории чистые

---

### 4. Rollback в Route Handlers

**Проблема:** В текущем route `get_external_reviews` НЕТ rollback при ошибке!

**Текущий код (НЕПРАВИЛЬНО):**
```python
@app.route("/api/business/<business_id>/external/reviews", methods=["GET"])
def get_external_reviews(business_id):
    try:
        if USE_REVIEW_REPOSITORY:
            db = get_db()
            repo = ReviewRepository(db.conn)
            reviews_data = repo.get_by_business_id(business_id)
            db.conn.commit()  # ← commit даже для SELECT!
            return jsonify(...)
    except Exception as e:
        # ❌ НЕТ rollback!
        return jsonify({"error": str(e)}), 500
```

**Правильный код:**
```python
@app.route("/api/business/<business_id>/external/reviews", methods=["GET"])
def get_external_reviews(business_id):
    db = get_db()
    try:
        if USE_REVIEW_REPOSITORY:
            repo = ReviewRepository(db.conn)
            reviews_data = repo.get_by_business_id(business_id)  # SELECT - не нужен commit
            stats = repo.get_statistics(business_id)  # SELECT - не нужен commit
            # НЕТ commit для SELECT операций!
            return jsonify(...)
        else:
            # Legacy code
            ...
    except Exception as e:
        db.conn.rollback()  # ← КРИТИЧНО для write операций!
        return jsonify({"error": str(e)}), 500
```

**⚠️ ВАЖНО:** 
- Для **SELECT** операций commit НЕ нужен (но rollback тоже не повредит)
- Для **INSERT/UPDATE/DELETE** операций **ОБЯЗАТЕЛЬЕН** rollback в except

**Статус:** ❌ Требует исправления перед деплоем

---

## 🟡 Рекомендуемые проверки

### 5. Staged Rollout (постепенное включение)

**Этап 1: Только чтение (безопасно)**
```bash
# В .env
USE_REVIEW_REPOSITORY=true      # Только SELECT операции
USE_SERVICE_REPOSITORY=false    # Пока не трогать
USE_BUSINESS_REPOSITORY=false   # Пока не трогать
```

**Этап 2: После 24 часов стабильной работы**
```bash
USE_REVIEW_REPOSITORY=true
USE_SERVICE_REPOSITORY=true     # Теперь можно включить
USE_BUSINESS_REPOSITORY=false
```

**Этап 3: Полное включение (после недели стабильной работы)**
```bash
USE_REVIEW_REPOSITORY=true
USE_SERVICE_REPOSITORY=true
USE_BUSINESS_REPOSITORY=true
```

---

### 6. Мониторинг (первые 30 минут)

**Команды для мониторинга:**
```bash
# Логи Flask
tail -f /tmp/seo_main.out | grep -i "integrity\|violat\|error\|exception"

# Логи worker
tail -f /tmp/seo_worker.out | grep -i "integrity\|violat\|error"

# Или через journalctl (если systemd)
journalctl -u beautybot-backend -f | grep -i "integrity\|violat\|error"
```

**Что искать:**
- `IntegrityError` - нарушение constraints
- `DuplicateRecordError` - дубликаты (должны обрабатываться)
- `OrphanRecordError` - нарушение FK
- `psycopg2.errors.UniqueViolation` - уникальные constraint нарушения

**Если пойдут ошибки:**
1. Немедленно выключить флаги: `USE_*_REPOSITORY=false`
2. Перезапустить сервер
3. Проверить логи и исправить проблему
4. Повторить проверки из чеклиста

---

### 7. Golden Master Testing (опционально, но рекомендуется)

**Перед включением:**
```bash
# Запустить тесты сравнения legacy vs repository
python tests/test_golden_master.py

# Или вручную сравнить ответы API:
# 1. С флагами false (legacy)
# 2. С флагами true (repository)
# Должны быть идентичны
```

---

## ✅ Чеклист готовности к проду

- [x] Constraints проверены и существуют в БД ✅
- [x] Orphaned records = 0 ✅
- [x] Репозитории не содержат commit() (кроме комментариев) ✅
- [x] Репозитории не содержат SELECT * (кроме комментариев) ✅
- [x] **Rollback добавлен во ВСЕ route handlers с репозиториями** ✅
- [x] Staged rollout план готов ✅
- [ ] Мониторинг настроен (требуется настройка на сервере)
- [ ] Rollback скрипт готов (отключение флагов) (требуется создание скрипта)

---

## 🚨 Критические замечания

### ❌ Проблема 1: Rollback отсутствует

**Файл:** `src/main.py`, функция `get_external_reviews()`  
**Строки:** 1567-1616

**Требуется исправление:**
```python
db = get_db()
try:
    if USE_REVIEW_REPOSITORY:
        repo = ReviewRepository(db.conn)
        reviews_data = repo.get_by_business_id(business_id)  # SELECT
        stats = repo.get_statistics(business_id)  # SELECT
        # НЕТ commit для SELECT!
        return jsonify(...)
except Exception as e:
    db.conn.rollback()  # ← ДОБАВИТЬ!
    return jsonify({"error": str(e)}), 500
```

### ⚠️ Проблема 2: Ненужный commit для SELECT

**Файл:** `src/main.py`, строка 1608  
**Проблема:** `db.conn.commit()` вызывается для SELECT операций (не нужно, но и не критично)

**Рекомендация:** Убрать commit для SELECT операций

---

## 📝 Дополнительные рекомендации

1. **Backup перед включением:**
   ```bash
   pg_dump -U postgres reports > backup_before_phase35_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Тестирование на staging:**
   - Если есть staging окружение - сначала протестировать там
   - Проверить все routes с репозиториями

3. **Документация для команды:**
   - Объяснить, что делать при ошибках
   - Как быстро откатить (выключить флаги)

---

## 🎯 Итоговая оценка готовности

**Текущий статус:** ✅ **ГОТОВО К STAGED ROLLOUT (все этапы)**

**Выполнено:**
1. ✅ Rollback добавлен в `get_external_reviews()` (строки 1618-1620)
2. ✅ Commit для SELECT операций убран (нет commit для SELECT)
3. ✅ Constraints проверены и добавлены в БД:
   - Уникальный индекс для ExternalBusinessReviews создан
   - **FOREIGN KEY на user_id в UserServices добавлен (критично для Step 2)**
4. ✅ Orphaned records проверены (0 записей)
5. ✅ Миграции применены:
   - `add_unique_constraint_external_reviews.py`
   - `add_fk_user_services_user_id.py` (НОВОЕ)

**Оценка готовности по этапам:**
- ✅ **Step 1 (USE_REVIEW_REPOSITORY)**: Готово (только чтение)
- ✅ **Step 2 (USE_SERVICE_REPOSITORY)**: Готово (FK на user_id добавлен)
- ✅ **Step 3 (USE_BUSINESS_REPOSITORY)**: Готово

**Следующие шаги:**
1. Настроить мониторинг на сервере (опционально)
2. Создать rollback скрипт для быстрого отключения флагов (опционально)
3. Начать staged rollout:
   - **Этап 1**: `USE_REVIEW_REPOSITORY=true` (сейчас, безопасно)
   - **Этап 2**: `USE_SERVICE_REPOSITORY=true` (через 24 часа, теперь безопасно)
   - **Этап 3**: `USE_BUSINESS_REPOSITORY=true` (через неделю)
