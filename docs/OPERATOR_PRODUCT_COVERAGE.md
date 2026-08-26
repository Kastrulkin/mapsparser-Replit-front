# Operator product coverage

Статус: current implementation map.

Канонические источники продуктовой семантики: `PRODUCT.md` и `README.md`. Оператор не должен выводить возможности из названия таблицы, endpoint или внутренней capability.

## Режим ответа

Для каждой функции LocalOS Оператор выбирает один честный режим:

1. `execute` — выполнить доступное безопасное действие;
2. `read` — показать уже сохранённые tenant-scoped данные;
3. `prepare` — создать preview или draft и остановиться перед approval;
4. `explain` — объяснить назначение, ограничения и стоимость;
5. `handoff` — открыть точный раздел, если чат-handler отсутствует;
6. `gap` — прямо сказать, что действие пока не поддержано.

Публикация, внешняя отправка, финансовая запись, destructive/bulk mutation и изменение доступа не могут быть скрыты внутри `explain` или свободного текста модели.

## Матрица

| Область | Объяснение | Чтение через Оператор | Подготовка/действие | Маршрут |
| --- | --- | --- | --- | --- |
| Сегодня | available | attention/support brief | переходы к задачам | `/dashboard/today` |
| Профиль бизнеса | available | профиль выбранного tenant | ручное редактирование | `/dashboard/profile` |
| Карты и аудит | available | snapshot, cards, parse status | governed refresh | `/dashboard/card` |
| Конкуренты | available | сохранённый snapshot, выбор «соседа» | новый audit пока handoff | `/dashboard/card?tab=competitors` |
| Услуги | available | inventory/list | draft, optimize, price update, approved apply | `/dashboard/card?tab=services` |
| SEO и Wordstat | available | объяснение и handoff | предложения по текстам через услуги | `/dashboard/card?tab=keywords` |
| Отзывы | available | unanswered/list | reply drafts, governed refresh | `/dashboard/card?tab=reviews&review_filter=all` |
| Контент | available | history/items | news, social и content-plan drafts | `/dashboard/content` |
| Финансы | available | summary | approved transaction и sales import | `/dashboard/finance` |
| Средний чек | available | overview | рекомендации и handoff | `/dashboard/average-ticket` |
| Прогресс/CRM-метрики | available | progress, appointments, analytics | источник записей остаётся CRM | `/dashboard/progress` |
| Аналитика сайта | beta | объяснение и handoff | dashboard зависит от tracker flag | `/dashboard/web-analytics` |
| Партнёрства/outreach | beta | leads/search | drafts; dispatch только через approval/preflight | `/dashboard/partnerships` |
| Продвижение/авторы | beta | объяснение и handoff | кампании проверяются в разделе | `/dashboard/promotion` |
| Telegram-радар | beta | объяснение и handoff | отдельные scoped radar/outreach permissions | `/dashboard/telegram-radar` |
| Telegram owner-bot/Mini App | available | сводки, approvals, уведомления | подтверждённые действия в общем Operator Core | `/telegram/control` |
| Брендированный бот бизнеса | beta | объяснение и connection handoff | клиентские webhook-сценарии | `/dashboard/settings/integrations` |
| AI-видимость | beta | объяснение и handoff | проверки в профильном разделе | `/dashboard/ai-chat-promotion` |
| Агенты | beta | list/status | управление и запуски в cockpit | `/dashboard/agents` |
| Чаты | beta | объяснение | draft и governed send request | `/dashboard/chats` |
| Сеть | available | network status | управление scope в разделе | `/dashboard/network` |
| Интеграции | available | connection health без секретов | настройка вручную | `/dashboard/settings/integrations` |
| Подписка и кредиты | available | объяснение cost/limits | платёж остаётся явным пользовательским действием | `/dashboard/settings` |
| Публичные материалы | beta | объяснение и публичные страницы | публикация/sales-room доступ только отдельным действием | `/documents` |

## Реализация

- канонический каталог и resolver: `services.operator_product_knowledge`;
- planner tool: `product.explain_feature`;
- cached competitor tool: `competitors.list`;
- общий список возможностей: `services.operator_capabilities.build_operator_help_response`;
- исполняемые tool contracts: `services.operator_core._operator_tool_catalog`;
- runtime validation and deterministic grounded responses: `services.operator_tool_loop`.

Новая функция считается понятной Оператору только после добавления в продуктовый каталог с назначением, алиасами пользовательского языка, ограничениями, статусом и маршрутом. Наличие страницы или backend endpoint само по себе не считается покрытием.
