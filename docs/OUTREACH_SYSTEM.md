# LocalOS Outreach System

Статус: `beta` для поиска, обогащения, персонализации и versioned drafts; внешняя отправка остаётся supervised и зависит от подключённого канала, разрешений, approval и runtime preflight.

## Цель

LocalOS ведёт потенциального клиента или партнёра от публичного поиска до первого ответа:

```text
настройка контекста
→ поиск и импорт
→ карточка и парсинг
→ обогащение и проверка контактов
→ evidence ledger и сигнал
→ подтверждённая личность отправителя
→ персонализация
→ проверка текста
→ versioned draft цепочки
→ human approval
→ контролируемые касания
→ stop-on-reply
→ outcome и обучающая петля
```

PostgreSQL LocalOS является единственным CRM/source of truth после импорта. JSON-отчёты и skill-контракты используются как спецификация и транспорт, а не как вторая база лидов.

## Сценарии и отправитель

Поддерживаются два workstream и три явных sender mode:

| Workstream | Sender mode | Поведение |
|---|---|---|
| `localos_sales` | `localos` | LocalOS ищет клиентов и обращается через platform-scoped профиль и аккаунт. |
| `client_partnership` | `partner_business` | Бизнес обращается к своим потенциальным партнёрам через собственный профиль и tenant-scoped аккаунты. Неполный профиль блокирует кампанию, но не matching. |
| `client_partnership` | `localos_for_partner` | После явного разрешения бизнеса сообщение пишется от первого лица этого бизнеса, а доставляется через platform-scoped аккаунт LocalOS. Во внешнем тексте LocalOS не упоминается; факты и предложение берутся из услуг, аудита, matching и публичных данных представляемого бизнеса. Технический отправитель и разрешение сохраняются в audit trail. |

Скрытое переключение между sender mode запрещено. Изменение sender mode, текста, порядка каналов или интервалов создаёт новую версию и требует нового approval.

## Календарь касаний

До сохранения и подтверждения цепочки карточка лида показывает компактный календарь: номер шага, абсолютную дату и время, канал и текущий статус. Текст не дублируется в календаре: все сообщения целиком показаны в секции «История сообщений», где каждое касание можно отредактировать отдельно и сразу запустить проверку новой версии. Пользователь задаёт дату первого касания, а следующие даты рассчитываются по интервалам цепочки. Прошедшая дата помечается предупреждением и не принимается backend при подготовке новой версии.

Календарь и редактор доступны и для продаж LocalOS, и для партнёрского аутрича. После ручной правки LocalOS повторно запускает deterministic quality gate без расхода AI-токенов. Успешная правка сохраняется только как новая draft-версия, хранит исходный текст для истории и learning loop и требует нового approval. Само редактирование ничего не отправляет и не ставит в очередь.

## Очередь сообщений

Вкладка «Сообщения» в административном реестре показывает касания последних версий кампаний отдельными строками, а не повторяет список лидов. Для каждого касания видны компания, представляемый бизнес, получатель, канал, шаг и версия цепочки, текст, запланированное или фактическое время, отправитель, provider ID, ошибка и ответ. Фильтры работают по workstream, бизнесу, каналу, статусу, компании, получателю и тексту сообщения; из строки можно открыть нужную карточку лида или подтверждение в канале.

Статусы основаны только на сохранённых событиях: `draft`, `scheduled`, `queued`, `sending`, `sent`, `delivered`, `read`, `replied`, `awaiting_manual_send`, `paused`, `cancelled`, `skipped` и `failed`. `delivered` не выводится из успешной отправки, а `read` — из факта доставки: они появляются только при соответствующем подтверждении провайдера. Ответ имеет приоритет над delivery/read и останавливает следующие касания по stop-on-reply.

## Поиск лидов

### Клиенты LocalOS

Источники включают административный поиск, карты, публичные аудиты и контролируемый импорт. После dedupe создаётся `prospectingleads` и workstream `localos_sales`.

### Партнёры бизнеса

LocalOS использует услуги, аудиторию, географию, желаемые типы партнёров и исключения бизнеса. Кандидаты приходят из geo-search, Яндекс/Apify там, где provider доступен, либо из CSV/JSON/JSONL fallback. Geo-search проверяет радиус и удаляет дубли; закрытие компании проверяется по результату парсинга. Собственный бренд, прямые конкуренты и другие disqualifiers исключаются по настройкам поиска и при shortlist review.

Для партнёра выполняется путь:

```text
карточка → парсинг → аудит → matching → контактное обогащение
```

Совместимость услуг хранится отдельно от полноты sender profile. Для партнёрского сигнала допустима подтверждённая совместимость услуг и аудиторий без придуманной боли.

## Обогащение и проверка контактов

Контакты собираются из карточки, raw/enrich payload карты и официального сайта. Website collector безопасно проверяет главную и до пяти релевантных страниц (`contacts`, `about`, `team`), извлекает:

- `mailto:` и email из публичного текста;
- `tel:` и телефоны;
- Telegram, WhatsApp, VK, Instagram и MAX;
- формы обратной связи;
- JSON-LD с именем, должностью и `sameAs`.

Каждая запись в `lead_contact_points` хранит тип, нормализованное значение, владельца контакта, имя и роль, URL и тип источника, provider, confidence, observed/verified timestamps и verification status.

Проверки:

- телефон нормализуется в международный формат;
- email проверяется по формату и публичному источнику; адреса не угадываются;
- social URL должен соответствовать выбранному каналу;
- недействительный или stale контакт не участвует в выборе получателя;
- paid enrichment не запускается без отдельного разрешения и настроенного provider key.

## Telegram: один аккаунт, две функции

Telegram Bot API и Telegram-аккаунт отправителя являются разными подключениями. `@LocalOspro_bot` управляет LocalOS и может публиковать в подключённый канал, но не читает личные контакты и не отправляет сообщения от имени пользовательского аккаунта бизнеса.

Для радара и аутрича текущая BYO-модель требует Telegram API application бизнеса с `my.telegram.org`. Бизнес вводит номер, `api_id` и `api_hash`, подтверждает код и при необходимости проходит 2FA. LocalOS хранит `api_id`, `api_hash` и `session_string` в зашифрованной business-scoped записи `externalbusinessaccounts`; пароль 2FA не сохраняется.

Одна авторизованная `Telethon session` и одна запись `externalbusinessaccounts` используются для двух независимых назначений:

- `radar_enabled`: чтение разрешённых публичных источников и поиск сигналов;
- `outreach_enabled`: отправка только одобренных сообщений и обязательный reply sync.

Существующий radar account не получает право на отправку автоматически. Перед чтением и отправкой проверяются concrete `account_id`, tenant/platform scope и соответствующее разрешение.

API application является техническим MTProto-клиентом. Видимый отправитель, контакты и диалоги определяются авторизованной пользовательской сессией. Сессия бизнеса не может быть выбрана для другого бизнеса.

Публичная Telegram-ссылка проходит `get_entity` через Telegram entity API:

- `User` — возможный личный получатель;
- `bot` — не получатель;
- `broadcast_channel` — источник сигналов, не получатель;
- `megagroup`, `gigagroup`, `group_chat` — источник/группа, не личный получатель;
- `unknown` — автоматическая отправка запрещена.

Для временной сетевой ошибки public HTML preview может подтвердить публичный источник как fallback, но не может доказать, что ссылка ведёт на личного получателя. Повторное обогащение сайта не должно вернуть уже классифицированный канал в DM-контакты.

Публичные посты сохраняются в `knowledge_documents` с текстом, датой, permalink, source и allowed uses. Они остаются доказательствами для персонализации и будущего обучения; это не означает автоматический fine-tuning языковой модели.

## Evidence ledger и сигнал

Источники фактов:

- карта и публичный аудит;
- рейтинг, количество отзывов и полнота услуг;
- официальный сайт;
- публичные отзывы с дополнительным safety review;
- новости и social activity;
- Telegram-радар;
- `partnershipleadartifacts.match_json` для партнёрской совместимости.

Каждый факт хранит `evidence_id`, наблюдение, источник, дату, freshness, confidence, статус, отдельно помеченную гипотезу и relevance bridge. Факт без URL, stale-факт, недоступный источник или декоративное наблюдение не допускаются в сообщение.

LocalOS не превращает любую публикацию в сигнал. Для evidence считается объяснимый `signal_score` по relevance, source confidence, freshness, specificity и сопоставимому engagement. Если engagement отсутствует, его вес перераспределяется. До scoring работают hard gates: reply/suppression/terminal state, tenant scope, sender mode/profile/account и валидность контакта.

После gates рассчитываются fit, signal, readiness и priority. Решение возвращает одно действие: `write_now`, `observe`, `needs_contact`, `needs_sender_setup`, `needs_evidence` или `excluded`. Сильная подтверждённая партнёрская совместимость может дать `write_now` без свежего social post; общий отраслевой fit остаётся `observe`.

## Где добавляется личность отправителя

Личность хранится в `outreach_sender_profiles`:

- имя, роль и компания;
- опыт основателя или команды;
- подтверждённые кейсы и proof points;
- кому полезен этот опыт;
- допустимые offers и CTA;
- voice examples;
- запрещённые утверждения.

Факты профиля имеют статус `approved`, `observed`, `hypothesis` или `missing`. В сообщение попадают только `approved` и `observed`.

Sender profile не участвует в поиске и не подменяет evidence получателя. После decision LocalOS сначала выбирает допустимый offer и trust strategy, затем применяет recipe режима:

```text
localos: signal → founder story/proof LocalOS → offer LocalOS → CTA
partner_business: compatibility/signal → reputation бизнеса → partnership offer → CTA
localos_for_partner: «мы ваши соседи» от лица представляемого бизнеса → compatibility/signal → partnership offer бизнеса → CTA; аккаунт LocalOS виден только во внутреннем audit trail
```

LocalOS ранжирует proof points по связи с конкретным evidence. Поэтому разные получатели могут получить разные части одной подтверждённой истории отправителя.

## Персонализация и quality gate

Для workstream создаётся до трёх personalization candidates. Каждый содержит наблюдение, evidence IDs, отдельно помеченную гипотезу, relevance bridge, выбранные offer/trust, допустимое для режима доказательство, source URL, confidence, freshness и CTA.

## Relationship memory, комнаты и песочница

`lead_relationship_states` хранит проекцию отношений: предпочтительный канал, follow-up, явные ограничения, summary, открытые вопросы, следующий шаг и стадию переговоров с provenance/confidence. Исходная переписка остаётся в inbound events и `sales_room_messages`; личные Telegram-чаты вне кампании не импортируются.

`sales_rooms` — единая инфраструктура переговоров. Качественный campaign draft идемпотентно готовит приватную комнату на workstream. Повторные кампании обновляют её. Положительный ответ останавливает касания, обновляет relationship memory, переводит комнату в `ready_to_share` и создаёт черновик приглашения. Публикация комнаты и отправка приглашения требуют отдельных явных действий.

В «Чатах» аутрич-песочница использует реальные decision/personalization/quality-gate правила. `POST /api/outreach/sandbox/preview` и `POST /api/outreach/sandbox/simulate-reply` всегда возвращают `dry_run=true`, откатывают транзакцию, не создают campaign/room/approval/learning events и не вызывают provider. Сохранение выполняется отдельным вызовом campaign preview с `save=true`.

Сообщение проходит:

- removal test;
- bridge test;
- fact/source test;
- freshness test;
- specificity test;
- proof integrity;
- channel fit;
- single CTA;
- suppression safety;
- human tone и semantic review.

Текущий gate требует результат не ниже `15/18` и отсутствие blocking reasons. AI может переписать evidence-bound каркас живым языком, но не получает права добавлять факты, обещания или результаты. Ошибка проверки даёт `revise`, `reject` или `needs_evidence`, а не generic fallback.

## Каналы и цепочка

Автоматические adapters сейчас предусмотрены для Telegram, email и VK-сообщества. VK подключается как отдельный sender account через зашифрованный ключ сообщества с правом `messages`. LocalOS проверяет фактические group ID, название, аватар и доступ к поверхности сообщений без отправки. Получатель видит имя и аватар сообщества. При подключении право отправки выключено; оно включается отдельно и только вместе с stop-on-reply. Reply sync проверяет только peer ID сообщений, ранее отправленных LocalOS, и не импортирует остальные диалоги. Личный MAX-аккаунт можно зарегистрировать как scoped manual sender: для него нельзя включить direct send и reply sync, а отправка и фиксация ответа остаются ручными. WhatsApp, SMS и другие каналы могут участвовать как manual touches до появления проверенного direct-message adapter с reply sync.

VK сам определяет, может ли сообщество начать диалог с конкретным профилем. Отказы privacy/message-request сохраняются как точные provider reason codes; LocalOS не обходит их другим VK-аккаунтом.

### VK: сообщения, публикации и имя отправителя

Одно и то же VK-сообщество может быть источником двух независимо управляемых действий:

| Назначение | Право ключа | Текущий binding | Статус |
|---|---|---|---|
| Аутрич и reply sync | `messages` | `outreach_sender_accounts` | `beta`, доступно после отдельного outreach permission и approval кампании |
| Текстовые публикации | `wall` / `wall.post` | `externalbusinessaccounts` | `beta`, доступно после проверки binding и отдельного подтверждения публикации |

Целевая модель — одна карточка сообщества и два независимых переключателя: «Публикации» и «Аутрич». Текущая beta пока хранит два зашифрованных binding. Один community key можно создать с обоими правами и использовать в обеих карточках настроек, но подключение аутрича не включает автопостинг, а подключение стены не разрешает сообщения. LocalOS не публикует и не пишет во время проверки ключа.

Получатель видит настоящее название и аватар сообщества. Для platform outreach название должно соответствовать LocalOS; текст сообщения не должен маскировать несоответствие имени. Публичный контент сообщества допустимо использовать как дополнительную trust опору, если это правда и материалы релевантны, например: «В нашем VK-сообществе публикуем практические материалы для предпринимателей». Такая фраза:

- не заменяет конкретный факт о получателе;
- не является единственным поводом написать;
- не подменяет founder story, offer или bridge;
- не должна обещать качество или регулярность контента, которые не подтверждены публичной лентой.

Для каждого канала вычисляется одно из состояний:

- `ready`;
- `connect_required`;
- `permission_required`;
- `recipient_missing`;
- `manual`;
- `adapter_unavailable`;
- `sender_selection_required`;
- sender health state.

Рекомендуемая цепочка:

1. Telegram, день 0 — сигнал.
2. Email, день 3 — founder story.
3. Следующий доступный канал, день 7 — proof или полезный материал.
4. Следующий доступный канал, день 12 — respectful close.

Пользователь может менять порядок и интервалы. Каждый touch должен использовать новый угол и быть понятным без чтения предыдущих сообщений.

## Approval, отправка и остановка

Preview и сохранённая кампания не являются разрешением на отправку. Новые кампании и touches создаются как `draft`. Перед каждым автоматическим касанием проверяются:

- актуальная approved version и approval snapshot;
- concrete sender account и scope;
- разрешение канала и reply sync;
- валидность recipient contact;
- suppression, отказ и существующий ответ;
- конфликтующая кампания и cross-channel cooldown;
- sender health и дневной лимит.

Любой человеческий ответ останавливает все будущие каналы. Отключение outreach permission немедленно блокирует новые отправки и ставит будущие автоматические touches, включая Telegram и VK, на паузу. LocalOS не выбирает другой аккаунт скрытно.

## Обучающая петля

Для каждого touch сохраняется стратегия: workstream, sender mode, сегмент, роль, signal kind, evidence ID, freshness, founder story/proof там, где они разрешены, bridge, offer ID, trust strategy, CTA, канал, порядковый номер, интервал и angle.

Outcomes хранятся раздельно: `sent`, `delivered`, `replied`, `positive_reply`, `question`, `hard_no`, `unsubscribe`, `complaint`, `meeting_booked`, `converted`, `no_reply`.

`strategy_fingerprint` позволяет сравнивать повторяющиеся связки без вывода о причинности на маленькой выборке. Публичные evidence documents и outcome events формируют датасет для последующей оценки и контролируемого обучения. Автоматического online fine-tuning production-модели сейчас нет.

Для LocalOS sales в beauty-сегменте кодовый playbook хранит семь групп болей в формулировках владельцев, мосты к возможностям LocalOS, подтверждённую founder story и кейсы. Это словарь гипотез сегмента, а не факты о конкретном лиде. Каждое касание записывает `playbook_version` и `pain_key`, чтобы ответы, отказы и no-reply можно было оценивать по конкретной связке. Ручные редакторские правки продолжают храниться как `editorial_correction`; перенос правил в production playbook выполняется версионно и через тесты, а не как неконтролируемый online learning.

### Сигналы возможных болей

Для beauty-сегмента действует versioned signal hypothesis library. Она связывает только проверяемые публичные наблюдения с осторожной гипотезой:

```text
evidence 1 + evidence 2 → гипотеза боли сегмента → безопасная фраза → outcome
```

Первая версия содержит составные сигналы:

- активный официальный канал + слабая карточка на картах;
- минимум две свежие публикации свободных окон;
- минимум два свежих отзыва без ответа при активном публичном присутствии;
- минимум три публикации акций за 60 дней;
- минимум две публикации о найме за 90 дней;
- несколько точек одной сети + подтверждённые расхождения карточек.

Одна публикация, одна вакансия, единичная сезонная акция, неофициальный источник или старые данные не проходят gate. Система не пишет «у вас нет клиентов», «у вас текучка» или «у вас низкий средний чек». Она сохраняет `signal_hypothesis_key`, `signal_pain_key`, evidence IDs и статус `segment_hypothesis_only`; результаты тестируются малыми когортами в существующем outreach experiment flow. Новая связка не получает approval и не запускает отправку автоматически.

Pain library не является отдельной CRM или отдельным интерфейсом. Фоновый процесс читает только публичные knowledge sources с явным назначением `outreach_learning`/`marketing_learning`, сохраняет короткие формулировки вместе с provenance и при появлении нового материала создаёт новую draft-версию pattern type `pain`. Генератор читает только последнюю approved-версию; approval заменяет прежнюю активную версию, но сохраняет историю. В `strategy_json` дополнительно фиксируются версия и ID использованной pain library.

### B2B-корпус и поэтапные проверки

Telegram-корпус B2B используется только после обязательного фильтра `metadata_json->>'corpus_tag' = 'telegram_b2b'`. Он даёт методику и гипотезы формулировок, но не факты о получателе. Каждый compiled pattern хранит ссылки на исходные документы, версию, противопоказания и уровень поддержки; для approval нужны минимум три уникальных документа из двух независимых источников.

Первый паттерн — `active_social_with_map_gap`: бизнес регулярно ведёт официальную соцсеть, но карточка на картах проходит минимум два map-gap критерия. Само наблюдение не доказывает нехватку времени или потерю клиентов. Допустимая гипотеза: компания уже вкладывается в привлечение, а карты могут дополнять этот канал.

В дефолтной beauty-цепочке правила разнесены по углам: публичный сигнал и аудит → узнаваемая операционная ситуация и founder origin → подтверждённый кейс → другие задачи LocalOS и накопление опыта → ручной диагностический контакт → уважительное завершение. Карточка и аудит не повторяются в каждом follow-up.

Rollout не меняет существующий интерфейс и не создаёт вторую CRM. Отбор, формулировка и метрики работают внутри текущих лидов, цепочек и результатов. Этапы `1 → 10 treatment → 10 control → 10 treatment → 10 control → 50 → 100` переключаются человеком. Подходящие лиды с существующими draft-цепочками получают приоритет: исправленная цепочка сохраняется следующей версией, а прежняя остаётся в истории. Внешняя отправка по-прежнему проходит существующие approval и preflight.

Feature flags по умолчанию выключены:

- `OUTREACH_CORPUS_PATTERNS_ENABLED=false` — компиляция и применение corpus patterns;
- `OUTREACH_EXPERIMENTS_ENABLED=false` — отбор групп и подготовка staged drafts.

## Основные данные

- `prospectingleads` — единая идентичность лида;
- `lead_workstreams` — сценарий LocalOS sales или partnership;
- `lead_contact_points` — контакты и provenance;
- `knowledge_sources`, `knowledge_documents`, `lead_signal_links` — источники и сигналы;
- `lead_workstream_research` — research, evidence ledger и personalization candidates;
- `lead_relationship_states` — проекция отношений и следующего шага;
- `outreach_sender_profiles`, `outreach_sender_accounts` — личность и каналы отправителя;
- `externalbusinessaccounts` — отдельный текущий binding VK для контролируемых публикаций на стене; это не разрешение на аутрич;
- `telegram_account_permissions` — независимые разрешения radar/outreach;
- `outreach_campaigns`, `outreach_campaign_touches`, `outreach_campaign_events` — versioned campaign lifecycle;
- `sales_rooms`, `sales_room_messages`, `sales_room_events` — приватная переговорная инфраструктура и campaign-scoped mirror;
- `outreach_suppressions` — stop-list;
- `outreach_learning_events` и strategy stats — обучающая петля;
- `outreach_knowledge_patterns` — проверенные и версионируемые правила из корпуса;
- `outreach_experiments`, `outreach_experiment_members` — этап, группа и связь с существующим workstream/campaign;
- legacy/transitional drafts, batches и queue остаются compatibility boundary там, где старый UI ещё их использует.

## Capability status

| Capability | Status |
|---|---|
| Поиск/импорт и dedupe лидов | `available/beta` по provider path |
| Парсинг карточки и website contact enrichment | `available` |
| Telegram entity classification и public radar storage | `available` |
| Evidence ledger, sender profile и founder-led personalization | `beta` |
| Versioned multichannel preview/drafts и quality gate | `beta` |
| Календарь дат, каналов, текстов и статусов касаний до approval | `available` |
| Telegram/email/VK controlled dispatch | `beta`, только после approval/preflight; VK использует community key с правом `messages`, отдельный outreach permission и campaign-scoped reply sync; global dispatcher может быть выключен |
| VK text publishing | `beta`, отдельный business-scoped binding с правом `wall`; публикация только после review/approval |
| Единое VK-подключение для wall и messages | `gap/planned`; сейчас два независимых binding и две проверки прав |
| MAX personal sender binding | `available`, manual handoff; scoped phone identity, no credentials, direct send or reply sync |
| WhatsApp/MAX Bot/SMS direct adapters | `planned`; сейчас manual handoff |
| Outcome attribution и strategy learning events | `available/beta` |
| Автоматический fine-tuning модели | `gap/planned`, не заявляется как текущая возможность |
