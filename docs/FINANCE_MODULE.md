# Finance Module

## Цель этапа 1

Раздел "Финансы" становится первым шагом к прибыльному бизнесу: владелец за 48 часов вручную вносит базовые данные за последние 3 месяца и видит P&L, точку безубыточности, дневную цель, загрузку мастеров и кресел, выручку на кресло и кресло-час.

Это не ERP, не CRM и не BI. Это минимальный расширяемый слой, который позже сможет принимать данные из CRM и файлов.

## Данные

Основные таблицы:

- `finance_entries` - ручные доходы и расходы.
- `finance_service_metrics` - агрегаты по услугам за период.
- `finance_staff_metrics` - агрегаты по мастерам за период.
- `finance_workplaces` - кресла, кабинеты и рабочие места.
- `finance_workplace_metrics` - загрузка и выручка рабочих мест.
- `finance_snapshots` - сохраненные результаты пересчета.
- `finance_import_batches` - история импортов, статус, ошибки, антидубли.
- `finance_crm_connections` - подключения CRM, статус, зашифрованные auth data и результат последней синхронизации.
- `finance_kpi_thresholds` - настраиваемые нормы KPI по бизнесу.
- `finance_action_logs` - отметки выполнения действий из финансовых рекомендаций.

Существующие `financialtransactions`, `financialmetrics` и `roidata` остаются для обратной совместимости.

## Agent Input Boundary

LocalOS agents can prepare finance writes through the controlled capability
`finance.transaction.create`.

In v1 this capability handler does not insert rows into `finance_entries`. It
accepts rows from a connector/source such as Google Sheets, normalizes them with
the same `core.finance_imports` logic used by file/CRM imports, and returns:

- normalized finance entry proposals;
- rows requiring human review;
- validation errors;
- duplicate keys;
- `approval_state=pending_human`;
- `apply_state=not_applied`.

When a custom agent reads rows in an earlier step, the compiled blueprint must
wire those rows through `payload.input_mappings` such as
`from_step=read_google_sheets`, `path=orchestrator.result.rows`,
`target=rows`. Runtime uses this saved mapping; it does not call an LLM again to
decide which table data should become finance proposals.

Actual writes to `finance_entries` happen only after approved execution through
`agent_domain_request_executor_v1`. The executor creates a
`finance_import_batches` record with `source_type=agent`, applies duplicate-key
checks, inserts approved rows with `source=agent`, and writes an audit ledger
event. This keeps custom agents useful without letting an unreviewed external
table mutate finance truth silently.

The agent run journal must expose finance import facts from step outputs:
`rows_read`, `proposal_count`, `review_count`, `error_count`, `rows_imported`,
`apply_state`, and recovery guidance. This makes the workflow reviewable without
asking an LLM to explain the run after the fact.

## Профили

На этапе 1 используется два уровня:

- `global` - выручка, расходы, прибыль, маржа, точка безубыточности.
- `service_business` / `beauty` - мастера, услуги, материалы, выплаты, кресла, кабинеты, no-show, rebooking.

Beauty-логика не применяется глобально к другим типам бизнеса.

## Формулы

- `revenue` = максимум из ручной выручки, выручки услуг и выручки рабочих мест.
- `expenses` = сумма расходов.
- `operating_profit` = `revenue - expenses`.
- `operating_margin` = `operating_profit / revenue * 100`.
- `gross_profit` = `revenue - payroll - materials`.
- `gross_margin` = `gross_profit / revenue * 100`.
- `break_even_revenue` = `fixed_costs / gross_margin_decimal`.
- `daily_revenue_target` = `break_even_revenue / 22`.
- `average_ticket` = `revenue / visits_count`.
- `no_show_rate` = `no_show_count / (visits_count + no_show_count) * 100`.
- `rebooking_rate` = `rebooking_count / visits_count * 100`.

## Кресла и рабочие места

- `active_workplaces` = количество активных рабочих мест.
- `available_workplace_hours` = сумма доступных минут / 60.
- `booked_workplace_hours` = сумма занятых минут / 60.
- `workplace_occupancy` = `booked_workplace_hours / available_workplace_hours * 100`.
- `idle_workplace_hours` = `available_workplace_hours - booked_workplace_hours`.
- `revenue_per_workplace` = `revenue / active_workplaces`.
- `gross_profit_per_workplace` = `gross_profit / active_workplaces`.
- `revenue_per_workplace_hour` = `revenue / available_workplace_hours`.
- `gross_profit_per_workplace_hour` = `gross_profit / available_workplace_hours`.

Все деления на ноль возвращают `null` и текстовое объяснение.

## Data Quality

Оценка от 0 до 100 снижается, если не заполнены:

- расходы;
- услуги;
- длительность услуг;
- материалы;
- выплаты мастерам;
- мастера;
- no-show;
- rebooking;
- кресла, кабинеты или рабочие места;
- доступные и занятые часы рабочих мест.

UI показывает, какие KPI точные, какие приблизительные и какие данные нужно дозаполнить.

## Рекомендации

Система показывает красные зоны:

- низкая операционная маржа;
- высокая доля ФОТ;
- высокая доля материалов;
- высокий no-show;
- низкий rebooking;
- низкая загрузка рабочих мест;
- высокая загрузка при низкой выручке на час;
- много пустых часов;
- низкая прибыль на кресло-час;
- высокая доля низкомаржинальных услуг.

Stage 5 превращает каждую красную зону в короткий операционный план. Рекомендация сохраняет совместимые поля `code`, `title`, `text`, `severity`, но дополнительно возвращает:

- `target_metric` - какой KPI нужно улучшить;
- `data_needed` - какие данные нужны для контроля;
- `actions.today` - что сделать сегодня;
- `actions.seven_days` - что довести за неделю;
- `actions.regular` - что отслеживать регулярно.

Пример: при низкой операционной марже система не только пишет “проверьте ФОТ и материалы”, но и предлагает сверить расходы, найти дорогие статьи, проверить низкомаржинальные услуги и дальше смотреть маржу каждую неделю.

Stage 6 добавляет чеклист выполнения. Каждое действие получает стабильный `action_key`, а отметка хранится в `finance_action_logs`. Это не полноценный task-manager, а легкий журнал: владелец видит, какие шаги уже сделаны, и может снять отметку, если действие снова актуально.

Stage 7 добавляет оценку влияния действий на KPI. LocalOS сравнивает текущий период с предыдущим таким же периодом и показывает, сколько действий отмечено выполненными, а также изменения по выручке, марже, no-show, rebooking, загрузке и выручке на рабочий час. Это не строгая причинно-следственная атрибуция, а управленческий ориентир: сделали действия, обновили данные, увидели направление изменений.

Stage 8 добавляет историю периодов. Endpoint возвращает месячные точки за 3, 6 или 12 месяцев: выручка, операционная маржа, no-show, rebooking, загрузка рабочих мест, выручка на рабочий час и качество данных.

## Нормы KPI

Stage 4 добавляет настройку KPI-порогов на уровне бизнеса. Базовые нормы остаются в коде как fallback, но владелец или администратор может изменить диапазоны без деплоя.

Настраиваются:

- `operating_margin`;
- `gross_margin`;
- `workplace_occupancy`;
- `rebooking_rate`;
- `no_show_rate`;
- `low_margin_services_share`;
- `payroll_share`;
- `material_share`;
- `revenue_per_workplace_hour`;
- `gross_profit_per_workplace_hour`.

Каждая норма хранит:

- зеленый диапазон;
- желтый диапазон;
- правило красной зоны;
- подпись;
- единицу измерения;
- источник: `default` или `custom`.

Dashboard, data quality, recommendations, import result и CRM-sync используют одни и те же нормы. Поэтому если для конкретного салона нормальная загрузка кресел отличается от дефолтной, статусы и рекомендации сразу пересчитываются по его правилам.

## API

- `GET /api/finance/dashboard?business_id=&from=&to=`
- `POST /api/finance/manual-entry`
- `POST /api/finance/recalculate`
- `GET /api/finance/data-quality?business_id=&from=&to=`
- `GET /api/finance/recommendations?business_id=&from=&to=`
- `GET /api/finance/thresholds?business_id=`
- `PUT /api/finance/thresholds`
- `POST /api/finance/thresholds/reset`
- `GET /api/finance/actions?business_id=&from=&to=`
- `POST /api/finance/actions`
- `GET /api/finance/impact?business_id=&from=&to=`
- `GET /api/finance/history?business_id=&months=`
- `GET /api/finance/import-templates`
- `GET /api/finance/import-template`
- `POST /api/finance/import-preview`
- `POST /api/finance/import-file`
- `GET /api/finance/imports`
- `GET /api/finance/crm/providers`
- `POST /api/finance/crm/connect`
- `GET /api/finance/crm/status`
- `POST /api/finance/crm/preview`
- `POST /api/finance/crm/sync`

## Импорт CSV/XLSX

Stage 2 добавляет импорт файлов по шаблону.

Файл может содержать строки четырех типов:

- `entry` - доход или расход.
- `service` - агрегат по услуге.
- `staff` - агрегат по мастеру.
- `workplace` - агрегат по креслу, кабинету или рабочему месту.

Перед импортом можно вызвать preview. Он возвращает:

- найденный mapping колонок;
- первые валидные строки;
- ошибки по строкам;
- общее число строк;
- число строк, готовых к импорту.

Stage 9 улучшает import wizard:

- endpoint `GET /api/finance/import-templates` возвращает доступные шаблоны;
- `GET /api/finance/import-template?profile=manual|yclients|workplaces` скачивает нужный CSV;
- preview возвращает найденный mapping;
- UI позволяет вручную поправить сопоставление колонок и повторить проверку;
- ошибки показываются до импорта.

При полном импорте создается `finance_import_batches`. Для каждой строки считается `duplicate_key`.
Повторная загрузка того же файла или той же строки не задваивает данные: строка будет пропущена как дубль.

Антидубли:

- для `entry`: дата + тип + категория + сумма;
- для `service`: период + услуга + выручка + число продаж;
- для `staff`: период + мастер + выручка + визиты;
- для `workplace`: период + рабочее место + доступные и занятые минуты;
- если есть `external_id`, он имеет приоритет.

## CRM Adapter Layer

Stage 3 добавляет общий контракт CRM:

- `fetch_appointments`
- `fetch_payments`
- `fetch_clients`
- `fetch_services`
- `fetch_staff`
- `fetch_workplaces`
- `fetch_schedules`

Каждый адаптер возвращает данные в промежуточный dataset, затем LocalOS нормализует их через тот же finance import pipeline.
Это важно: ручной ввод, CSV/XLSX и CRM-sync попадают в одну модель и считаются одними формулами.

На старте доступен `mock_demo` provider. Он не ходит во внешние сервисы и нужен для проверки потока:

- подключение;
- sync batch;
- external_id;
- duplicate_key;
- запись в finance tables;
- пересчет dashboard.

Stage 10 переводит `yclients` и `altegio` из заглушек в подготовленные API-коннекторы.

- YCLIENTS: базовый URL `https://api.yclients.com/api/v1`.
- Altegio: базовый URL `https://api.alteg.io/api/v1`.
- Для бизнес-данных используется схема `Authorization: Bearer <partner_token>, User <user_token>`.
- UI показывает поля для `location_id`, `partner_token`, `user_token` и ссылку на документацию API.
- Без токенов и ID филиала коннектор не синхронизируется и возвращает понятную ошибку.
- Текущая нормализация покрывает оплаты, услуги, мастеров, рабочие места и расписания/доступные часы.

Важное ограничение: это техническая готовность к подключению, а не договоренность с CRM. Перед боевым запуском нужны права приложения/системного пользователя на стороне YCLIENTS/Altegio и тест на реальном филиале.

Stage 12-13 добавляет безопасную проверку CRM-контракта перед импортом:

- `POST /api/finance/crm/preview` получает данные из подключенной CRM, но не пишет их в финансовые таблицы.
- Preview показывает, сколько CRM отдала записей, оплат, клиентов, услуг, мастеров и рабочих мест.
- Preview показывает, сколько строк LocalOS смог нормализовать в `entry`, `service`, `staff`, `workplace`.
- В ответе есть первые нормализованные строки, ошибки и очищенные raw samples без токенов/секретов.
- При ошибке подключения статус CRM становится `preview_failed`; при успешной проверке - `preview_ok`.
- Реальный `POST /api/finance/crm/sync` остается отдельным действием и только он создает `finance_import_batches` и пишет строки в finance tables.

Stage 14-15 закрепляет CRM-контракт fixtures и расширяет нормализацию записей/клиентов:

- реальные или sandbox payload-примеры кладутся в `tests/fixtures/crm/`;
- fixture должен быть обезличен: без реальных телефонов, токенов, ФИО и медицинских данных;
- `load_crm_contract_fixture` строит preview из fixture и позволяет закрепить mapping тестами;
- appointments теперь агрегируются в `staff` metrics:
  - completed/arrived visits;
  - no-show по `attendance = -1` или no-show статусам;
  - rebooking, если у клиента есть следующий визит/бронь позже текущего;
  - booked minutes;
  - revenue per staff.
- appointments также агрегируются в `service` metrics:
  - service revenue;
  - visits count;
  - avg price;
  - duration.
- appointments и schedules агрегируются в `workplace` metrics:
  - booked minutes из записей;
  - revenue по рабочему месту из завершенных записей;
  - available minutes из расписаний, ресурсов или start/end интервалов;
  - workplace type для кресла, nail-места, кабинета косметологии, массажного кабинета.

Это первый слой клиентско-сервисных KPI из CRM. После первого реального YCLIENTS/Altegio payload mapping нужно уточнить по фактическим полям.

## Связка рекомендаций с LocalOS

Рекомендации теперь не только говорят, что делать, но и дают переход в подходящий раздел:

- слабая маржа или низкая прибыль на час -> услуги и карточка;
- no-show и rebooking -> записи и коммуникации;
- простой рабочих мест -> публикации в карточке и локальные партнерства;
- неполные данные -> вкладка «Финансы».

Это остается управленческой подсказкой, а не автоматическим действием: пользователь сам выбирает, что запускать.

## Проверка на реальном бизнесе

Перед включением боевого CRM-sync для конкретного салона:

1. Запустить CRM preview за последние 7-14 дней.
2. Сверить raw samples с фактическими записями CRM.
3. Проверить, что completed/no-show/rebooking трактуются правильно.
4. Проверить, что рабочие места и доступные часы не задваиваются между schedules и appointments.
5. Только после этого запускать sync на 3 месяца.

## Ограничения этапа 1

На этом этапе не реализованы:

- OAuth/marketplace activation flow для CRM;
- production sync на реальном филиале без выданных ключей;
- cohort analysis;
- CAC;
- retail attachment;
- тяжелый BI;
- прогнозирование выручки;
- автоматические управленческие решения.
