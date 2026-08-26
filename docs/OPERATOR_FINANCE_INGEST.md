# Operator Finance Ingest

Статус: beta, внутренняя запись только после явного подтверждения.

## Задача

Пользователь вставляет в чат Оператора одну или несколько продаж. Planner один раз компилирует текст в `finance.ingest_sales`. Runtime валидирует строки, проверяет дубли и создаёт preview. Запись в `financialtransactions` выполняет `finance.sales_import.apply_operator` только после отдельного human approval.

```text
user text
  -> planner compiler
  -> finance.ingest_sales
  -> validation + duplicate lookup
  -> preview or one clarification
  -> ActionOrchestrator pending_human
  -> finance.sales_import.apply_operator
  -> Finance summary for the calendar date
```

## Контракт

Один импорт содержит до 100 строк:

- `transaction_date`: ISO-дата;
- `amount`: положительная сумма до `99999999.99`;
- `title`: услуга или товар;
- `sale_type`: `service`, `upsell` или `cross_sell`;
- `notes`: необязательный комментарий.

`business_id` не принимается из model-generated arguments. Tenant берётся из авторизованного контекста чата.

## Безопасность

- Неоднозначные суммы, даты или валюты требуют уточнения.
- Preview и отказ не создают финансовых операций.
- `duplicate_key` уникален внутри бизнеса; повторный confirm или повторная вставка того же источника не создаёт копии.
- Это внутренняя LocalOS-запись; provider writes и external dispatch отсутствуют.
- Если preview нельзя безопасно подготовить, ответ содержит ссылку на `/dashboard/finance`.

## Миграция

`20260826_002` добавляет в `financialtransactions` поля `source`, `import_batch_id`, `source_hash`, `duplicate_key` и tenant-scoped unique index. Перед production upgrade обязателен backup PostgreSQL.
