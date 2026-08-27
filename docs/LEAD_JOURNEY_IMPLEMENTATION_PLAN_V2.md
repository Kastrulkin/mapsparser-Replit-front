# План внедрения продающих маршрутов LocalOS v2

## 1. Цель

Администратор выбирает проблему потенциального клиента — инфлюенсеры,
партнёрства, карты или контент — и получает персональную ссылку. Клиент по этой
ссылке видит заранее выбранный пример, совершает одно понятное действие,
регистрируется только на границе полного результата и после подтверждения email
попадает непосредственно в нужную рабочую область.

Пользователь может открывать другие области LocalOS. Недоступные блоки объясняют
пользу и условие открытия; доступ проверяется backend, а blur служит только
визуальным preview.

UX-контракт: `docs/LEAD_JOURNEY_PRODUCT_UX_ARCHITECTURE.md`.

## 2. Текущее состояние и разрыв

| Уже есть | Не хватает |
| --- | --- |
| `/start/:token`, token hash, expiry, revoke и one-time claim | Обязательного выбора flow при создании ссылки |
| Journey actions, события, version и idempotency | `content` в flow constraints, state machine и адаптере |
| Публичные preview для influencer, partnership и maps | Фокусировки public-экрана на выбранном оператором пути |
| Сохранение journey token при регистрации | Надёжного post-auth resolver в нужную область и action |
| `/dashboard/content` и существующий content domain | Проекции content journey поверх существующих планов и черновиков |
| Today и Mini App action queue | Единой навигационной модели «Сегодня / Пути роста / Результаты / Ещё» |
| Route-wide платный overlay | Общего block-level access contract |
| Рабочие разделы карт, контента и продвижения | Административного мастера создания и preview маршрута |

## 3. Флаги и границы релиза

Сохранить существующие флаги и добавить:

- `CONTENT_JOURNEY_ENABLED` — backend и UI content flow;
- `JOURNEY_ADMIN_BUILDER_ENABLED` — создание маршрутов в админке;
- `JOURNEY_POST_AUTH_REDIRECT_ENABLED` — claim и прямой переход после auth;
- `GROWTH_PATHS_NAVIGATION_ENABLED` — новая глобальная IA;
- `BLOCK_ACCESS_V2_ENABLED` — блочные preview и ограничения.

Каждый флаг выключается без удаления данных. Существующие прямые URL и старая
навигация сохраняются до завершения rollout.

## 4. Инкремент 0 — фиксация контрактов

### Backend contract

- Канонические flow: `influencer`, `partnership`, `maps`, `content`.
- Канонический destination resolver хранит не произвольный URL, а allowlisted
  screen key: `influencers`, `partnerships`, `maps`, `content`.
- При создании нового персонального journey `selected_flow` обязателен.
- Для старых journey с `selected_flow = NULL` сохраняется текущий выбор на
  public-экране до истечения ссылки; новые ссылки так не создаются.
- Выбранный entity и безопасный preview фиксируются в journey до отправки ссылки.
- Access state имеет значения `available`, `registration_required`,
  `payment_required`, `setup_required`, `approval_required`, `unavailable`.

### Frontend contract

- Один resolver преобразует screen key в route.
- Journey action одинаков для web и Mini App.
- Query-параметр фокуса — `journey_action=<uuid>`; workspace проверяет, что action
  принадлежит текущему бизнесу.
- CSS blur никогда не определяет фактический доступ.

### Выход

Согласованы типы, команды content flow, allowlist маршрутов, доступы и обратная
совместимость старых токенов.

## 5. Инкремент 1 — данные и backend foundation

### Миграция

Создать новую Alembic-миграцию после текущего head `20260827_001`:

- расширить `ck_lead_journeys_flow` значением `content`;
- расширить `ck_journey_actions_flow` значением `content`;
- не переписывать уже применённую миграцию `20260826_add_lead_journeys.py`;
- при необходимости добавить индекс по `selected_flow, status, created_at` для
  административной очереди;
- не менять существующие journey и actions.

Перед production-миграцией обязателен PostgreSQL backup.

### Service/API

Обновить `src/services/lead_journey_service.py`:

- `FLOW_TYPES`, `FLOW_FLAGS`, `_screen_for_flow`;
- сериализацию и очистку публичного content preview;
- обязательный flow при создании нового journey;
- фильтрацию primary opportunity по `selected_flow`;
- обратную совместимость legacy journey без выбранного flow.

Обновить `src/api/lead_journey_api.py`:

- `POST /api/journeys` принимает `selected_flow`, `selected_entity_type`,
  `selected_entity_id`;
- проверяет соответствие выбранной сущности preview;
- возвращает готовые `public_path`, `public_url`, expiry и preview sequence;
- diagnostics показывает content flag и количество journey по flow/status.

### Тесты

- migration upgrade/downgrade;
- четыре разрешённых flow и неизвестный flow;
- создание нового journey без flow отклоняется;
- legacy `selected_flow = NULL` остаётся читаемым;
- token expiry, revoke, second claim и tenant isolation.

### Выход

Backend способен безопасно хранить content journey и создавать детерминированную
ссылку под один выбранный путь. Флаг `CONTENT_JOURNEY_ENABLED=0`.

## 6. Инкремент 2 — детерминированная public-ссылка и auth continuity

### Public experience

Обновить `frontend/src/pages/LeadJourneyPage.tsx`:

- если `selected_flow` задан, сразу открыть выбранный путь;
- main layer показывает только выбранную возможность;
- остальные пути находятся в тихом блоке «Что ещё можно улучшить»;
- один основной CTA;
- public response не содержит полного сообщения, закрытых контактов и платного
  результата;
- добавить content copy, icon и partial preview.

Обновить общие типы в `frontend/src/lib/leadJourney.ts` и onboarding Mini App.

### Post-auth resolver

Вынести claim/redirect из `TodayPage` в общий resolver:

1. Login и VerifyEmail видят сохранённый journey token.
2. После получения пользователя и бизнеса выполняется idempotent claim.
3. Backend возвращает action с allowlisted `cta_target.screen`.
4. Frontend открывает соответствующий workspace с `journey_action`.
5. Token очищается только после успешного claim и навигации.
6. При временной ошибке показывается retry; при expired/revoked — понятное
   восстановление без бесконечного цикла.

Изменить `Login.tsx`, `VerifyEmail.tsx`, `TodayPage.tsx` и общий auth helper.

### Тесты

- guest -> register -> verify -> selected workspace;
- existing user -> login -> selected workspace;
- повторный login/claim;
- expired/revoked token;
- business mismatch;
- network account с несколькими бизнесами;
- browser back/reopen;
- web и Mini App deep link.

### Выход

Для каждого из трёх существующих flow оператор может отправить ссылку и точно
предсказать первый экран после регистрации.

## 7. Инкремент 3 — content journey

### Domain adapter

Content journey переиспользует существующие content plans, items, social drafts,
voice profile, calendar и supervised publication. Новую таблицу контент-планов
не создавать.

Источники safe preview по приоритету:

1. существующий подготовленный content-plan item;
2. существующая draft recommendation;
3. безопасная тема из услуг, сезона, отзывов или карточки;
4. fallback без выдуманных результатов.

Public preview может содержать тему, короткий excerpt, причину и каналы. Он не
содержит полный платный текст, provider credentials или приватный контекст.

### State machine

Рекомендуемая цепочка:

`prepare_content -> review_content -> save_to_calendar -> waiting_for_publication -> add_content_result -> start_next_content_cycle`

Команды:

- `prepare` — подготовить полный draft после регистрации;
- `save_draft` — сохранить подтверждённую редакцию;
- `schedule` — добавить в существующий календарь;
- `mark_published` — зафиксировать ручную или подтверждённую provider-публикацию;
- `add_result` — сохранить известный результат;
- `start_next_cycle` — выбрать следующую тему.

Доменное обновление и переход action выполняются одной транзакцией. Публикация во
внешнюю систему остаётся в существующем approval/preflight-контуре.

### Workspace focus

`/dashboard/content?journey_action=:id` открывает нужный план/item/draft и один
CTA, а не общий календарь без контекста. После завершения показывает следующий
journey action.

### Тесты

- все разрешённые и запрещённые transitions;
- повторное сохранение/двойной клик;
- draft generation failure;
- отсутствующий content context;
- бесплатный preview и платная генерация;
- manual publication и provider-confirmed publication;
- результат создаётся только после доменного commit.

### Выход

Полный content journey проходит от персональной ссылки до первого сохранённого
материала и следующего шага.

## 8. Инкремент 4 — административный мастер

Создать отдельную административную поверхность, например
`/dashboard/bazich/journeys`, сохранив superadmin access boundary.

### Шаги мастера

1. **Клиент** — выбрать prospect lead или существующий тестовый бизнес.
2. **Проблема** — выбрать один из четырёх путей.
3. **Пример** — выбрать автора, партнёра, audit issue или content item.
4. **Предпросмотр** — переключение «до регистрации / после регистрации / после
   оплаты».
5. **Отправка** — получить готовый текст сообщения и персональную ссылку.

### После создания

Показать:

- lifecycle status;
- текущий шаг и последнее событие;
- срок действия;
- кто и когда claim-нул ссылку;
- открыть глазами клиента;
- скопировать ссылку/сообщение;
- отозвать ссылку;
- создать новую версию без изменения старой ссылки.

Не добавлять произвольный workflow builder, JSON-поля или ручной redirect URL.

### Тесты

- keyboard/focus;
- empty lead and no candidates;
- preview generation error;
- expired/revoked state;
- длинные русские названия;
- narrow laptop;
- запрет доступа не-superadmin.

### Выход

Администратор создаёт любой из четырёх маршрутов без SQL и точно видит будущий
путь клиента.

## 9. Инкремент 5 — экран «Пути роста» и новая IA

Добавить `/dashboard/growth-paths` как authenticated product surface. Не путать с
публичным legacy `/growth`.

### Первый уровень

- **Сегодня** — focus action и короткая очередь;
- **Пути роста** — Карты, Контент, Инфлюенсеры, Партнёрства;
- **Результаты** — существующий Progress, завершённые циклы и подтверждённые
  изменения;
- **Ещё** — профиль, финансы, агенты, чаты, интеграции и настройки.

### Growth path row

Каждый путь показывает status, одну возможность, последний результат/препятствие,
условие доступа и один CTA. Активный journey — первый. Due reply и blocked выше
discovery.

### Миграция навигации

- новая sidebar-конфигурация включается флагом;
- старые URL и bookmarks продолжают работать;
- desktop получает компактный sidebar;
- mobile/Mini App получают тот же порядок в bottom nav/More;
- внутренняя навигация каждого пути описывает стадии результата, а не backend
  сущности.

### Выход

Новый пользователь понимает, что сделать сейчас, какие четыре пути роста есть и
где увидеть результат, не просматривая плоское меню из множества инструментов.

## 10. Инкремент 6 — block-level access

### Общий access contract

Backend или tenant-aware selector возвращает для блока:

- status;
- human-readable reason;
- result preview;
- required action;
- CTA label/target;
- entitlement source.

Создать общий frontend-компонент `AccessPreview`/`AccessBoundary` для
`registration_required`, `payment_required`, `setup_required` и
`approval_required`.

### Порядок замены route-wide blur

1. Content.
2. Influencers and Partnerships.
3. Maps/Progress.
4. Остальные платные разделы.

Пока конкретный экран не переведён на block-level contract, его существующий
route-wide gate сохраняется. Нельзя одновременно убрать старую защиту и не
добавить серверную проверку действий.

### UX требования

- title, value, lock reason и CTA всегда читаемы;
- representative preview может быть softened/blurred;
- закрытые controls не focusable;
- lock click открывает drawer с ожидаемым результатом, а не dead end;
- touch targets минимум 40x40 px;
- числа tabular;
- heading balance/body pretty wrap;
- только specific CSS transitions;
- press feedback `scale(0.96)` там, где не мешает работе.

### Выход

Пользователь может исследовать продукт и понимать ценность закрытых блоков, но
не может получить данные или выполнить действие без нужного entitlement.

## 11. Инкремент 7 — Mini App, telemetry и уведомления

### Mini App

- те же четыре flow;
- тот же action payload и allowed commands;
- deep link сразу на action/version;
- последовательный mobile flow: action -> result -> next action;
- другие пути доступны через Growth paths/More.

### Telemetry

Funnel по `flow_type`, `surface`, `access_state`, `journey_id`, `action_id`:

`link_open -> preview -> partial_result -> registration_started -> verified -> claimed -> workspace_opened -> first_action -> result -> next_cycle -> payment_view -> subscription_started`

Дополнительно:

- auth redirect failure;
- orphan/stale action;
- domain/action mismatch;
- access CTA conversion;
- route-to-route hunting до первого результата;
- time-to-first-value.

### Notifications

Включать только после стабильного прохождения flow. Ссылка ведёт на конкретный
action/version. Completed, cancelled и superseded действия не отправляются.

### Выход

Web и Mini App продолжают один сценарий, а команда видит конверсию и реальные
препятствия на каждом шаге.

## 12. Проверка по слоям

### Backend

- state machine unit tests для четырёх flow;
- transaction rollback;
- idempotency, stale version, concurrent web/Mini action;
- tenant and token security;
- public field allowlist;
- access enforcement вне frontend;
- Today selector priority;
- migration на копии production schema.

### Frontend

- public selected-flow experience;
- auth continuation;
- четыре focused workspace;
- loading, empty, blocked, stale, permission, payment, setup, offline/retry;
- keyboard, focus, long Russian text, narrow laptop and Telegram viewport;
- build и targeted component tests.

### Browser acceptance

- influencer, partnership, maps и content end-to-end;
- guest -> register -> verify -> exact destination;
- logged-in link open;
- cross-area exploration without losing current action;
- browser refresh/back;
- no console errors;
- response не содержит закрытых данных.

## 13. Rollout

### Release A — deterministic links

`internal only -> Варвара -> ещё 2 тестовых лида`.

Включить foundation, selected flow и post-auth redirect для существующих трёх
flow. Новая глобальная навигация выключена.

### Release B — Content pilot

Включить content только для внутренних journey. Пройти draft -> calendar ->
manual publication/result. После стабильных циклов открыть ограниченному cohort.

### Release C — Admin builder

Перевести создание ссылок с ручного API/SQL на мастер. Запретить новые journey
без selected flow.

### Release D — Growth paths navigation

Включить сотрудникам, затем тестовым аккаунтам, затем 10–20% пользователей.
Сравнить time-to-first-action, возвраты в Today и количество лишних переходов.

### Release E — Block access and monetization

Переводить области по одной. Upgrade CTA показывать по существующим правилам
eligibility; paywall не открывать автоматически.

### Release F — Mini App and notifications

Включить после подтверждённой синхронизации action state и notification dedupe.

## 14. Приоритеты

### P0 — продающий сценарий работает

- selected flow создаётся в админке/API;
- public показывает выбранный путь;
- post-auth redirect ведёт в exact workspace/action;
- content flow проходит до сохранённого draft;
- token and tenant security подтверждены.

### P1 — продукт легко исследовать

- Growth paths screen;
- новая сгруппированная навигация;
- cross-area exploration;
- block-level access для четырёх продающих путей.

### P2 — масштабирование

- полная Mini App parity;
- notifications;
- расширенная аналитика;
- перенос остальных платных экранов на block access.

## 15. Definition of Done

Внедрение считается завершённым, когда:

1. Администратор без SQL создаёт ссылку на любой из четырёх путей и видит точную
   последовательность экранов.
2. Новый пользователь после регистрации и email verification попадает в
   выбранную область и видит подготовленное действие.
3. Пользователь может открыть другие области, не теряя текущий journey.
4. Недоступный блок объясняет ценность и условие открытия, а backend запрещает
   неразрешённое чтение/действие.
5. Все четыре flow проходят acceptance в web; критические переходы совпадают в
   Mini App.
6. External send, publish, payment и destructive actions сохраняют approval.
7. Funnel, stale/orphan actions и domain/action mismatch наблюдаемы.
8. Старые прямые URL работают в течение навигационной миграции.
9. Production rollout имеет backup, feature-flag rollback и smoke evidence.

## 16. Рекомендуемый первый рабочий пакет

Начать не с редизайна меню, а с одного вертикального среза:

1. новая migration с `content`;
2. обязательный `selected_flow` для новых journey;
3. public auto-focus выбранного пути;
4. общий post-auth resolver;
5. content safe preview и первая action;
6. минимальный admin selector «клиент + путь + пример»;
7. acceptance на Варваре.

Этот пакет доказывает основную продажную идею. Новая IA и block-level access
строятся поверх уже работающего сценария, а не маскируют отсутствие continuity.
