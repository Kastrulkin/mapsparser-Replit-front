# Исправления неполных данных парсинга и расхождений в UI

**Дата:** 17.02.2026

## Проблемы

### 1. Вкладка «Прогресс»
| Метрика | Ожидается | Показывается |
|---------|-----------|--------------|
| Отзывы | 75 | 25 |
| Рейтинг | 4.8 | 4.1 |
| Фото | 64 | — |
| Услуги | 36 | — |

### 2. Вкладка «Работа с картами»
- **Услуги и цены**: рейтинг не обновился; услуги от 6.01 — без полного текста, описания, категории, цены
- **Отзывы**: нет текста отзывов и ответов
- **Новости и сторис**: нет текста новостей
- **Конкуренты**: пусто (должны извлекаться из карточки Яндекс)

## Корневые причины

### A. Разные источники данных
- **external/summary** (CardOverviewPage): externalbusinessstats + externalbusinessreviews → 75 отзывов, 4.8 рейтинг ✅
- **progress_calculator, growth_api**: только MapParseResults → 25, 4.1 ❌
- **network/health** (BusinessHealthWidget): MapParseResults + unanswered_reviews_count=0

### B. MapParseResults заполняется неполно
- **YandexBusinessSyncWorker** пишет в MapParseResults, но `reviews_count` берёт из парсера (len(reviews)) — ограничено пагинацией (~25)
- **Parsing worker** НЕ пишет в MapParseResults — только в cards. Бизнесы без external-аккаунта не обновляют MapParseResults

### C. Парсинг (parser_interception)
- **competitors**: инициализируется как `[]`, из API не извлекаются. Только fallback HTML (parse_competitors) заполняет
- **news**: `_is_posts_data()` не распознаёт структуру getPosts (items внутри data)
- **photos**: нет обработчика getByBusinessId
- **reviews**: текст отзывов из API может не сохраняться в cards

### D. Услуги
- UserServices обновляются из products при парсинге. Если парсинг возвращает 1 категорию вместо 36 услуг — данные неполные (исправлено `_products_count`)

## План исправлений (реализовано 17.02.2026)

1. ✅ **Унифицировать источник метрик** — progress_calculator, growth_api, network_health: приоритет external → cards → MapParseResults (`_get_map_metrics`)
2. ✅ **Parsing worker** — после save_new_card_version писать в MapParseResults (`_upsert_map_parse_from_card`)
3. ✅ **Sync worker** — использовать COUNT(*) из ExternalBusinessReviews вместо len(reviews)
4. ✅ **parser_interception** — вызывать parse_competitors(page) из HTML при пустых competitors из API
5. ✅ **network_health** — для business_id использовать _get_map_metrics + unanswered из externalbusinessreviews

## Оставшиеся задачи (парсинг)

- **Новости (текст)**: `_is_posts_data()` не распознаёт getPosts (items внутри data) — см. PARSING_0904017c_ROOT_CAUSES.md
- **Фото (массив)**: добавить обработчик getByBusinessId в parser_interception
- **Услуги (полный текст)**: проверить map_card_services и структуру products из API
