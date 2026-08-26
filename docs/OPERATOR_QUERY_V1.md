# Operator Query v1

Статус: available behind the existing `OPERATOR_TOOL_LOOP_ENABLED` rollout gate.

## Цель

`localos_operator_query_v1` отделяет понимание свободной команды от исполнения. Модель один раз компилирует пользовательскую формулировку в типизированный read-only запрос. После этого LocalOS проверяет поля, применяет tenant scope, читает сохранённые данные и формирует ответ без второго вызова модели.

```text
natural language
  -> one model compiler step
  -> localos.query arguments
  -> schema and field allowlist validation
  -> tenant-scoped deterministic query
  -> deterministic response renderer
```

## Контракт

```json
{
  "schema": "localos_operator_query_v1",
  "operation": "query",
  "resource": "services | reviews | content",
  "filters": [
    {"field": "category", "operator": "contains", "value": "Трансферы"}
  ],
  "sort_by": "updated_at",
  "sort_direction": "desc",
  "limit": 10,
  "view": "auto | count | compact | full"
}
```

Поддерживаемые операторы: `eq`, `contains`, `gte`, `lte`, `is_empty`.

Поля разрешаются отдельно для каждого ресурса. Неизвестное поле, оператор, ресурс или сортировка отклоняются до чтения данных. `business_id` никогда не принимается из model-generated arguments и всегда передаётся runtime из авторизованного контекста.

## Ресурсы

### Services

Фильтры: `title`, `category`, `source`, `status`, `price`, `updated_at`.

Примеры запросов:

- услуги определённой категории;
- активные услуги с частью названия;
- самые свежие или дорогие услуги;

### Reviews

Фильтры: `author_name`, `source`, `rating`, `has_response`, `text`, `published_at`, `created_at`.

Запрос читает сохранённый snapshot и явно сообщает дату последнего сохранённого отзыва. Команда с явным требованием проверить внешние карты остаётся отдельным `maps.refresh`: это платный external read с собственным preflight, reservation и async result flow.

### Content

Фильтры: `title`, `status`, `content_type`, `scheduled_for`, `updated_at`.

Относительные даты компилятор переводит в ISO-даты по `Europe/Moscow`, переданному в planner state. Runtime не содержит отдельных веток для каждой формулировки даты.

## Ответ

Capability возвращает единый envelope:

- `items`, `count`;
- канонический `query`;
- `as_of`, `freshness`, `data_warnings`;
- `provenance` с tenant-scoped источником;
- `result_ref`, `ui_actions`;
- детерминированный `chat_response`;
- нулевые external calls/writes для query.

`localos.query` помечен `deterministic_response`. Tool loop завершает run сразу после успешного чтения и не просит модель повторно пересказывать результат.

## Совместимость и безопасность

- Старые `services.list`, `reviews.list_unanswered` и `content.list_items` сохранены как runtime compatibility handlers, но скрыты от нового planner catalog.
- При выключенном `OPERATOR_TOOL_LOOP_ENABLED` продолжают работать legacy deterministic routes.
- Публикации, внешние отправки, изменения, массовые операции и платежи не входят в query DSL.
- Явная команда проверки новых отзывов использует существующий `maps.refresh`, а не маскируется под локальный query.

## Проверка

Минимальный acceptance-набор:

1. Разные формулировки услуг, отзывов и контента достигают одного `localos.query`.
2. Неизвестные tenant или database fields отклоняются.
3. Категория услуги, последний отзыв и диапазон дат контента фильтруются одинаковым runtime.
4. Ответ содержит фактические item fields и не зависит от второго model response.
5. Запрос сохранённых отзывов не запускает парсинг.
6. Явная проверка новых внешних отзывов проходит через `maps.refresh`.
