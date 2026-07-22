# Семантическая память LocalOS

Статус: `beta infrastructure`. Пользовательские действия и внешние отправки по-прежнему требуют существующих preview и approval.

## Контур

Разрешённые документы очищаются, делятся на фрагменты примерно по 2400 символов с overlap 240 символов и дедуплицируются по SHA-256. `EmbeddingsGigaR` создаёт векторы размерности 2560. PostgreSQL хранит их как `halfvec(2560)` и индексирует HNSW cosine.

Поиск объединяет 50 семантических и 50 полнотекстовых кандидатов через reciprocal-rank fusion. До передачи результата модели применяются tenant, privacy, purpose, source type и date filters. Один источник может дать не более трёх фрагментов, итоговый контекст содержит до 15 фрагментов и provenance.

## Разрешённые данные

- публичные Telegram-материалы, карточки, аудиты, услуги, отзывы, опубликованные посты и подтверждённые новости;
- tenant-услуги и подтверждённые рекомендации после очистки;
- закрытые Telegram-источники только как обезличенные агрегаты минимум из трёх наблюдений внутри одного tenant;
- межбизнесовые claims только после порога в пять бизнесов и privacy review существующего knowledge layer.

Raw private/invite Telegram, клиентская переписка, bookings, контакты, credentials, сырые транзакции и неподтверждённые drafts во внешний Embeddings API не передаются.

## Feature flags

```text
KNOWLEDGE_LAYER_ENABLED=true
KNOWLEDGE_EMBEDDINGS_ENABLED=false
KNOWLEDGE_EMBEDDINGS_SHADOW=true
KNOWLEDGE_EMBEDDINGS_MODEL=EmbeddingsGigaR
KNOWLEDGE_EMBEDDINGS_MIN_BALANCE=10000000
KNOWLEDGE_EMBEDDINGS_BUSINESS_IDS=<comma-separated beta business ids>
```

При остатке ниже 10 млн токенов worker не забирает новые embedding jobs. Полнотекстовый поиск остаётся fallback. Embedding usage сохраняется как техническое потребление с `client_billing=false` и не списывает продуктовые кредиты.

## Безопасный rollout

1. Сделать production backup и проверить восстановление в отдельном контейнере.
2. Перевести Postgres на совместимый `pgvector/pgvector:0.8.0-pg16` и применить Alembic.
3. Оставить `KNOWLEDGE_EMBEDDINGS_ENABLED=false`, проверить schema и status endpoint.
4. Выполнить smoke `EmbeddingsGigaR` и проверить фактический пакетный баланс.
5. Указать три beta business IDs, включить embeddings и оставить shadow.
6. Запустить backfill порциями; контролировать очередь, ошибки, остаток и tenant isolation.
7. Оценить по 50 запросов для услуг, отзывов, контента и рекомендаций.
8. Снимать shadow последовательно: услуги → отзывы → контент → рекомендации.

Rollback выполняется выключением `KNOWLEDGE_EMBEDDINGS_ENABLED` или возвратом `KNOWLEDGE_EMBEDDINGS_SHADOW=true`. Schema и pgvector остаются совместимыми и не требуют отката данных.

## Операционные endpoint-ы

Только superadmin:

- `GET /api/admin/knowledge/embeddings/status`;
- `POST /api/admin/knowledge/embeddings/backfill`;
- `POST /api/admin/knowledge/embeddings/search`;
- `POST /api/admin/knowledge/embeddings/retrieval/<event_id>/outcome`.

## Gate

- tenant leaks и policy violations: 0;
- provenance: 100%;
- Recall@10 ≥ 85%, Precision@5 ≥ 75%;
- hybrid nDCG@10 как минимум на 10% выше baseline;
- p95 retrieval ≤ 3 секунд;
- provider fallback ≤ 3%;
- одинаковый content hash повторно индексируется не чаще 1%.
