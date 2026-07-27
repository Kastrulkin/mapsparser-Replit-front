# LocalOS Mini App: readiness и production gate

Этот документ фиксирует реальный статус мобильных сценариев. Статус `available` нельзя выдавать только за наличие экрана: нужны реальные данные, завершённый ежедневный сценарий, scope-проверка и mobile E2E.

## Текущий статус

| Раздел | Статус | Что уже работает | Что закрывает gate |
|---|---|---|---|
| Сегодня | available | приоритет, реальная фоновая работа, изменения, результаты, Пульс | parity приоритета для всех network/platform edge cases |
| Задачи | available | единая очередь и переходы к объекту | безопасный retry и live update всех типов job |
| Отзывы | available | список/counts, фильтры, пагинация, черновики, bulk preview, ручная публикация | production E2E на живом provider snapshot |
| Оператор | available | серверная история, deterministic-first routing, мобильный route результата | common preview для всех подготовленных model actions |
| Прогресс | available | нативный экран и общий Growth backend | parity-тесты с web по пяти направлениям |
| Карточки | available | Андекс/2ГИС, freshness, очередь, расписание через preview | ручной paid refresh и OAuth return E2E |
| Контент | available | текущий план, календарь, редактирование, генерация, preview удаления | общий action/job contract для генерации плана и network distribution |
| Услуги | available | canonical catalog, редактор, оптимизация/сжатие через common preview | archive/rollback E2E и вывод подготовленных suggestions |
| Финансы | available | обзор, аналитика, ввод, услуги, команда, рабочие места, импорт, preview удаления | common preview для CRM и photo/document production E2E |
| Партнёрства | available | поиск, лид, черновик, канал, preview, статусы | E2E controlled send/reply/suppression для всех каналов |
| ИИ-сотрудники | read_only | статус, последний результат, ошибка | preview, запуск, live run, review, approval, retry |
| Настройки | read_only | scope-aware уведомления | подключения, OAuth, тариф, кредиты, ограничения |
| Диагностика | read_only | parser, integrations, embeddings backlog, Radar warnings | preview + safe retry для каждого типа очереди |
| Компании | feature flag | canonical card, search, scope access | production role matrix и object-level E2E |
| Пульс | available | публичные источники, подписки, статус сбора | production E2E ingestion + embeddings + personalized analysis |

## Обязательный gate

Модуль меняет статус на `available` только после всех шагов:

1. Web и Mini App используют один доменный сервис.
2. Scope и object ID повторно проверяются на сервере.
3. Внешние, массовые, платные и необратимые действия проходят preview/confirm/idempotency.
4. Есть loading, empty, stale, offline, permission и recoverable error.
5. Пройдены backend tests и Playwright на 360×800 и 393×852.
6. Нет перехода в legacy desktop.

## Порядок закрытия

1. Довести common action/job contract для контента, услуг, финансов и партнёрств.
2. Закрыть рабочие сценарии ИИ-сотрудников, настроек и диагностики.
3. Добавить object-level deep-link tests и E2E для каждого раздела.
4. Провести production-like role matrix: одиночный бизнес, сеть, суперадмин.
5. Только после этого удалить переходные inline-модули из `TelegramControlPage`.
