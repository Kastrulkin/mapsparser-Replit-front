# Поэтапный рефакторинг: 3 этапа

Каждый этап — отдельный PR/коммит. После каждого этапа проект должен запускаться, ключевые экраны работают.

---

## Этап 1. Alembic heads (только merge)

**Цель:** один head, без изменения схемы.

**Что сделано:**
- Цепочка миграций линейная: `20250207_001` → … → `20250207_009` → `20250210_001`. Merge не требуется.
- Проверка: один head.

**Команды проверки:**
```bash
cd "<project_root>"
python3 -m alembic -c alembic.ini heads
# Ожидается одна строка: 20250210_001 (head) — до этапа 2; после этапа 2/3 — 20250211_002 (head)

python3 -m flask db upgrade   # или: python3 -m alembic -c alembic.ini upgrade head
```
**Результат:** миграции применяются без конфликтов, новых колонок/таблиц на этапе 1 нет.

---

## Этап 2. Rich-поля businesses + site/website + network-locations

**Цель:** убрать 500 на `/api/business/<id>/network-locations`, канон поля сайта `site`, не ломать `website`.

**Изменённые файлы:**
- `alembic_migrations/versions/20250211_add_business_site_and_backfill.py` — новая миграция: колонка `site`, backfill из `website`.
- `src/database_manager.py`: запись в `site` (не `website`), добавлен `industry` в `update_business_from_card`; `get_businesses_by_network` возвращает список dict по именам колонок; `get_business_by_id` переведён на `SELECT *`.
- `src/main.py`: эндпоинт `get_network_locations` — нормализация локаций, алиас `website = site`, защита от NULL.
- `src/worker.py`: в `sync_payload` добавлены `industry`, `geo`, `external_ids`.

**Команды проверки:**
```bash
python3 -m alembic -c alembic.ini upgrade head
```
В psql:
```sql
\d+ businesses
-- Должны быть колонки: description, industry, phone, email, site, website, rating, reviews_count, categories, hours, hours_full, geo, external_ids, last_parsed_at
```
```bash
curl -s -H "Authorization: Bearer <token>" "http://localhost:8000/api/business/<business_id>/network-locations"
# Ожидается 200, в locations — объекты с полями site/website, без 500
```
После парсинга в psql:
```sql
SELECT id, site, rating, reviews_count, categories, last_parsed_at FROM businesses WHERE id = '<business_id>';
```

**Результат:** нет 500 на network-locations, в `businesses` есть rich-поля и `site`, фронт не ломается по `website`/`site`.

---

## Этап 3. Услуги: userservices + upsert из парсинга

**Цель:** после парсинга вкладка «Услуги и цены» заполняется из карточки через `userservices`, `/api/services/list` отдаёт данные.

**Изменённые файлы:**
- `alembic_migrations/versions/20250211_expand_userservices_for_parsing.py` — новые колонки в `userservices`: `source`, `external_id`, `price_from`, `price_to`, `currency`, `unit`, `duration_minutes`, `raw` (JSONB); уникальный индекс `(business_id, source, external_id) WHERE external_id IS NOT NULL`.
- `src/worker.py`: функции `map_card_services`, `_one_service_row`; после `update_business_from_card` вызов `upsert_parsed_services`, лог `Saved services=N for business_id=...`.
- `src/database_manager.py`: метод `upsert_parsed_services(business_id, user_id, service_rows)` — INSERT/ON CONFLICT по `(business_id, source, external_id)`.
- `src/api/services_api.py`: `get_services` переведён на PostgreSQL (`information_schema`, `%s`, таблица `userservices`), фильтр `is_active`, сортировка по `category`, `name`, `price_from`, `updated_at`, нормализация NULL.

**Команды проверки:**
```bash
python3 -m alembic -c alembic.ini upgrade head
```
В psql:
```sql
\d+ userservices
-- Должны быть: source, external_id, price_from, price_to, currency, unit, duration_minutes, raw
```
После парсинга:
```sql
SELECT count(*) FROM userservices WHERE business_id = '<business_id>';
```
```bash
curl -s -H "Authorization: Bearer <token>" "http://localhost:8000/api/services/list?business_id=<business_id>"
# Ожидается 200 и массив services (если есть данные парсинга)
```

**Результат:** после парсинга услуги попадают в `userservices`, `/api/services/list` возвращает 200 и список услуг.

---

## Риски и рекомендации

1. **Уникальный индекс `(business_id, source, external_id) WHERE external_id IS NOT NULL`**  
   Если в проде уже есть дубли по этой тройке, миграция этапа 3 создаст индекс без ошибки, но последующие INSERT с тем же `(business_id, source, external_id)` будут конфликтовать и обновлять строку (DO UPDATE). Если нужно сначала почистить дубли: выполнить дедупликацию (оставить одну запись на тройку), затем применять миграцию.

2. **services_api: add/update/delete**  
   В этом рефакторинге под PostgreSQL переведён только `get_services` (list). Эндпоинты `add`, `update`, `delete` в `services_api.py` всё ещё используют `?` и могут использовать CamelCase таблицы — если runtime только PostgreSQL, их стоит перевести на `%s` и таблицу `userservices`.

3. **Поле `website`**  
   Не удаляется, используется как алиас в API. Новые записи пишутся в `site`; при ответе отдаётся и `site`, и `website` (website = site при наличии).

---

## Краткий список изменённых файлов по этапам

| Этап | Файлы |
|------|--------|
| 1 | (только проверка heads, merge не создавался) |
| 2 | `alembic_migrations/versions/20250211_add_business_site_and_backfill.py`, `src/database_manager.py`, `src/main.py`, `src/worker.py` |
| 3 | `alembic_migrations/versions/20250211_expand_userservices_for_parsing.py`, `src/worker.py`, `src/database_manager.py`, `src/api/services_api.py` |
