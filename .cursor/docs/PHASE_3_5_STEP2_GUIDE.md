# Phase 3.5 Step 2: Запуск USE_SERVICE_REPOSITORY

**Дата:** 2026-02-01  
**Статус:** ✅ **ГОТОВО К ЗАПУСКУ** - Интеграция ServiceRepository в main.py выполнена

---

## 🚀 Быстрый старт

### ⚠️ ВАЖНО: Не запускать раньше чем через 24 часа после Step 1!

**Текущий статус Step 1:** ✅ Работает (read-only)  
**Время запуска Step 2:** Не раньше чем через 24 часа от завершения Step 1

### Вариант 1: Автоматический (рекомендуется)

```bash
# 1. Остановить Flask (Ctrl+C если в терминале)

# 2. Настроить .env автоматически
./scripts/start_phase35_step2.sh

# 3. Запустить Flask
python3 src/main.py

# 4. В другом терминале - протестировать
./scripts/test_phase35_step2.sh YOUR_BUSINESS_ID
```

### Вариант 2: Ручной

```bash
# 1. Остановить Flask (Ctrl+C)

# 2. Включить Step 2
sed -i.bak 's/USE_SERVICE_REPOSITORY=false/USE_SERVICE_REPOSITORY=true/' .env

# 3. Проверить что флаг включен
grep USE_SERVICE_REPOSITORY .env
# Должно быть: USE_SERVICE_REPOSITORY=true

# 4. Запустить Flask
python3 src/main.py

# 5. Протестировать (в другом терминале)
curl -X POST http://localhost:8000/api/services/add \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"business_id": "YOUR_BUSINESS_ID", "name": "Test Step2", "price": "500"}'
```

---

## 📋 Что делает Step 2

**USE_SERVICE_REPOSITORY=true** включает:
- ✅ Создание услуг через `ServiceRepository.create()` вместо raw SQL
- ✅ Обновление услуг через `ServiceRepository.update()` вместо raw SQL
- ✅ Удаление услуг через `ServiceRepository.delete()` вместо raw SQL
- ✅ Использование explicit column lists (без SELECT *)
- ✅ Логирование SQL запросов (debug level)
- ✅ Обработка ошибок через типизированные исключения

**Изменяемые endpoints:**
- `/api/services/add` (POST) - создание услуги
- `/api/services/update/<service_id>` (PUT) - обновление услуги
- `/api/services/delete/<service_id>` (DELETE) - удаление услуги

**⚠️ Риск:**
- Это **запись в БД** (INSERT/UPDATE/DELETE)
- Ошибка здесь = потеря или повреждение данных
- В отличие от Step 1 (read-only), здесь нужна особая осторожность

---

## ✅ Интеграция ServiceRepository выполнена

**Проверено:** ServiceRepository интегрирован в main.py:
- ✅ `/api/services/add` (POST) - использует `ServiceRepository.create()` при `USE_SERVICE_REPOSITORY=true`
- ✅ `/api/services/update/<id>` (PUT) - использует `ServiceRepository.update()` при `USE_SERVICE_REPOSITORY=true`
- ✅ `/api/services/delete/<id>` (DELETE) - использует `ServiceRepository.delete()` при `USE_SERVICE_REPOSITORY=true`

**Legacy код сохранен** как fallback при `USE_SERVICE_REPOSITORY=false`

**Исправления:**
- ✅ `ServiceRepository.create()` - исправлен `CURRENT_TIMESTAMP` (используется как SQL выражение)
- ✅ `business_id` сделан опциональным в репозитории (для совместимости с legacy кодом)

---

## ✅ Предварительные проверки (ОБЯЗАТЕЛЬНО перед запуском)

### 1. Проверка FK constraints в PostgreSQL

**Перед включением Step 2 проверьте:**

```sql
-- Подключитесь к PostgreSQL
psql -d your_database_name

-- Проверьте constraints для UserServices
\d UserServices

-- Должны быть:
-- - FOREIGN KEY (business_id) REFERENCES Businesses(id)
-- - FOREIGN KEY (user_id) REFERENCES Users(id) [опционально, но рекомендуется]
```

**Если FK нет - НЕ ВКЛЮЧАТЬ Step 2!** Сначала накатить миграции.

### 2. Проверка orphaned records

```sql
-- Должно быть 0
SELECT COUNT(*) FROM UserServices WHERE business_id IS NULL;
SELECT COUNT(*) FROM UserServices WHERE business_id NOT IN (SELECT id FROM Businesses);
```

**Если найдены orphaned records - удалить перед запуском Step 2.**

### 3. Проверка что Step 1 работает стабильно

```bash
# Проверить логи Flask за последние 15-30 минут
# Не должно быть ошибок IntegrityError, violat, traceback
```

---

## 🧪 Тестирование

### 1. Проверка что флаг включен

```bash
# Проверить .env
grep USE_SERVICE_REPOSITORY .env
# Должно быть: USE_SERVICE_REPOSITORY=true
```

### 2. Тест создания услуги (POST)

```bash
# Создать тестовую услугу
curl -X POST http://localhost:8000/api/services/add \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "YOUR_BUSINESS_ID",
    "name": "Test Service Step2",
    "category": "Test",
    "price": "500",
    "description": "Test description"
  }'

# Ожидаемый результат:
# {"success": true, "message": "Услуга добавлена"}
```

### 3. Тест обновления услуги (PUT)

```bash
# Обновить услугу (используйте ID из предыдущего шага)
curl -X PUT http://localhost:8000/api/services/update/SERVICE_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Service Step2",
    "price": "600"
  }'

# Ожидаемый результат:
# {"success": true, "message": "Услуга обновлена"}
```

### 4. Тест удаления услуги (DELETE)

```bash
# Удалить услугу (soft delete)
curl -X DELETE http://localhost:8000/api/services/delete/SERVICE_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# Ожидаемый результат:
# {"success": true, "message": "Услуга удалена"}
```

### 5. Проверка ошибок

**Что искать в логах Flask (первые 15-30 минут):**
- ❌ `IntegrityError` - нарушение constraints
- ❌ `violat` - нарушение constraints
- ❌ `traceback` - ошибки выполнения
- ❌ `rollback` - откат транзакций (может быть нормально при ошибках)

**Если ошибок нет** - Step 2 успешен! ✅

---

## 🔍 Мониторинг

### Вариант 1: Смотреть вывод Flask в терминале

Если Flask запущен в терминале - просто смотрите вывод.

### Вариант 2: Логи в файл

```bash
# Запустить Flask с логированием
python3 src/main.py > /tmp/seo_main_phase35_step2.log 2>&1 &

# Смотреть логи
tail -f /tmp/seo_main_phase35_step2.log | grep -i "integrity\|violat\|error\|rollback"
```

### Вариант 3: Через journalctl (если systemd на сервере)

```bash
journalctl -u beautybot-backend -f | grep -i "integrity\|violat\|error"
```

---

## ⚠️ Что делать при ошибках

### Ошибка: IntegrityError

**Причина:** Constraints не применены или orphaned records

**Решение:**
1. Немедленно выключить флаг: `USE_SERVICE_REPOSITORY=false`
2. Перезапустить Flask
3. Проверить constraints (см. предварительные проверки)
4. Исправить проблему
5. Повторить Step 2

### Ошибка: DuplicateServiceError

**Причина:** Попытка создать дубликат услуги

**Решение:**
- Это нормальная ошибка - проверьте логику создания услуг
- Убедитесь, что проверка на дубликаты работает корректно

### Ошибка: OrphanRecordError

**Причина:** Попытка создать услугу с несуществующим business_id или user_id

**Решение:**
- Проверить что business_id и user_id существуют в БД
- Убедиться, что FK constraints работают

---

## ✅ Критерии успеха Step 2

- [ ] Flask запустился без ошибок
- [ ] Endpoint `/api/services/add` (POST) работает через ServiceRepository
- [ ] Endpoint `/api/services/update/<id>` (PUT) работает через ServiceRepository
- [ ] Endpoint `/api/services/delete/<id>` (DELETE) работает через ServiceRepository
- [ ] Нет ошибок в логах за 15-30 минут
- [ ] Данные корректно сохраняются в БД

**Если все ✅ - можно переходить к Step 3 через неделю**

---

## 📝 Следующие шаги

После успешного Step 2:

1. **Через неделю:** Включить Step 3 (`USE_BUSINESS_REPOSITORY=true`)

См. `.cursor/docs/PHASE_3_5_PRODUCTION_CHECKLIST.md` для деталей.

---

## 🔄 Откат (если нужно)

Если что-то пошло не так:

```bash
# 1. Выключить флаг
sed -i.bak 's/USE_SERVICE_REPOSITORY=true/USE_SERVICE_REPOSITORY=false/' .env

# 2. Перезапустить Flask
# (Ctrl+C если в терминале, или перезапустить systemd сервис)

# 3. Проверить что работает legacy код
curl -X POST http://localhost:8000/api/services/add \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"business_id": "YOUR_BUSINESS_ID", "name": "Test"}'
```

Система вернется к legacy коду автоматически.

---

## 📊 Текущий статус Phase 3.5

- ✅ Step 1: `USE_REVIEW_REPOSITORY=true` (READ-ONLY) - РАБОТАЕТ
- ⏳ Step 2: `USE_SERVICE_REPOSITORY=false` (ожидает запуска)
- ⏳ Step 3: `USE_BUSINESS_REPOSITORY=false` (ожидает)

**Время запуска Step 2:** Не раньше чем через 24 часа после завершения Step 1
