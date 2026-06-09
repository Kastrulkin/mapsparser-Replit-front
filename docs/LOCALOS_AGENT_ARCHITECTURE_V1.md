# LocalOS Agent Architecture v1

Дата: 9 июня 2026
Статус: canonical architecture document; этапы 1-5 частично реализованы в backend/frontend

## Цель

Этот документ фиксирует единый канон пользовательских агентов LocalOS. Он нужен,
чтобы новые агенты, старые `AIAgents`, `AgentBlueprints` и OpenClaw/LocalOS
capability runtime развивались как одна архитектура, а не как отдельные куски.

Ключевое правило: **не вводить отдельную сущность `communication agent` рядом с
blueprints**. Коммуникационный агент, агент напоминаний, агент пакетных
предложений, агент отзывов, агент услуг и агент outreach являются категориями
`AgentBlueprint`.

## Базовые определения

| Термин | Каноничное значение | Текущая опора в коде |
| --- | --- | --- |
| `Agent` | Пользовательский продуктовый объект: "агент, который делает работу для бизнеса". Внутри он собирается из persona, blueprint, permissions, run history и approval policy. | Product/UI layer: `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx`; backend layer: `agent_blueprints` плюс optional `AIAgents`; serializer: `src/services/agent_product_layer.py`. |
| `Persona` | Голос, стиль общения, роль, ограничения речи и channel behavior. Persona не является runtime workflow. | `AIAgents`, `AIAgentSettings`, `AIAgentsManagement`, `AIAgentConversations`, `AIAgentMessages`. |
| `Blueprint` | Версионируемый workflow: цель, inputs, источники, шаги, allowed capabilities, approvals, output schema. | `agent_blueprints`, `agent_blueprint_versions`, `src/api/agent_blueprints_api.py`. |
| `Compiled Workflow` | Проверенный исполняемый план, полученный из человеческого описания или диалога. Он отделяет deterministic steps от LLM steps и фиксирует validation/approval boundaries. | Представлен как `version_payload`/`steps_json`; compiler v1 живет в `agent_blueprint_draft_builder.py` как `compile_agent_blueprint()`, а old draft builder name сохранен как compatibility wrapper. |
| `Capability` | Узкое разрешенное действие с контрактом input/output, risk class, side effects, permission policy, timeout/retry и audit event. Модель может предложить capability, но не исполняет side effects напрямую. | `ActionOrchestrator`, `services/agent_blueprint_orchestrator.py`, OpenClaw contract docs. |
| `Run` | Конкретное выполнение blueprint version с input, steps, artifacts, approvals, output и stop reason. | `agent_runs`, `agent_run_steps`, `agent_artifacts`, `AgentBlueprintRunner`. |
| `Approval` | Human gate вне prompt text. Требуется для внешних отправок, публикаций, платежей, destructive changes, массовых изменений и third-party writes. | `agent_approvals`; action-level approvals в `ActionOrchestrator`. |
| `OpenClaw` / `ActionOrchestrator` | Execution boundary: tenant guard, policy, idempotency, billing, ledger, callbacks, retries, DLQ, audit, support export. | `src/core/action_orchestrator.py`, OpenClaw docs/scripts/UI panel. |

## Product Contract

Пользователь видит один объект: **агент LocalOS**.

Внутренне агент состоит из:

1. `Persona`: как агент говорит и каким стилем пользуется.
2. `Blueprint`: что агент делает и в каком порядке.
3. `Compiled Workflow`: проверенный план, который можно запускать повторно.
4. `Capability allowlist`: какие действия агенту разрешены.
5. `Approval policy`: где человек обязан подтвердить действие.
6. `Run history`: что было запущено, что получилось, где остановилось.
7. `Audit / support trail`: почему действие было разрешено, отклонено, отправлено, поставлено в retry или DLQ.

Коммуникационный агент описывается как `AgentBlueprint` с категорией
`communications`, а не как отдельная runtime-сущность. Пример:

```text
Пользователь: "Сделай агента, который напоминает клиентам о записи и сообщает,
что у нас есть пакетное предложение."

Compiler:
  category = communications
  trigger = appointment.reminder.before
  audience = clients_with_upcoming_appointments
  sources = appointments, services, packages, business_profile
  steps =
    collect_audience
    prepare_message
    validate_consent
    approve_message
    send_message
    record_outcome
  capabilities =
    appointments.read
    communications.draft
    communications.send_reminder
  approvals =
    first_run
    template
    external_send
    mass_send
  limits =
    frequency_cap
    daily_cap
  outputs =
    drafts
    delivery_report
    outcomes
```

## Current Backend Contract

Этапы 2-3 не требуют новой таблицы `agents`. Product layer уже доступен как
расширение существующих API-ответов:

- `agent_blueprints` остается физическим product object.
- `agent_blueprint_versions.persona_agent_id` является связью с `AIAgents`.
- `AIAgents` сериализуется как `persona` и `voice` с ролью `agent_voice`.
- API blueprint list/detail возвращает `product_agent`, где явно указаны
  `components.blueprint`, `components.persona` и `components.compiled_workflow`.
- Если `persona_agent_id` пустой, агент остается валидным: persona optional.
- Старые `AIAgents` для Telegram/WhatsApp не удаляются; они становятся голосом
  агента и legacy chat config.

Compiler v1 доступен через `compile_agent_blueprint(description, category)`.
Старое имя `build_agent_blueprint_draft()` сохранено, чтобы не ломать endpoints
и UI. В metadata новое поле `compiler = agent_compiler_v1`, а
`builder = description_builder_v1` оставлено как backward-compatible marker.

Capability map v1 подключена через `build_agent_blueprint_orchestrator()` и
зарегистрированный Flask API:

- user/session surface: `/api/capabilities/*`;
- OpenClaw/M2M surface: `/api/openclaw/capabilities/*`,
  `/api/openclaw/callbacks/*`, `/api/openclaw/audit-timeline*`.

Каноничные capability names:

- `outreach.send_batch`;
- `reviews.reply.draft`;
- `reviews.reply.publish_request`;
- `services.optimize`;
- `news.generate`;
- `appointments.read`;
- `appointments.create_request`;
- `communications.draft`;
- `communications.send_reminder`;
- `communications.send_offer`;
- `support.export`;
- `billing.reserve`;
- `billing.settle`.

Legacy aliases (`reviews.reply`, `appointments.create`,
`appointments.update`, `appointments.cancel`, `reminders.send`,
`communications.send`) остаются подключенными как compatibility wrappers.

## Communication Showcase v1

Этап 5 реализует первые коммуникационные агенты как `AgentBlueprint.category =
communications`. Это не новая таблица и не отдельный runtime. Compiler выбирает
один из canonical templates, а `AgentBlueprintRunner` исполняет те же steps,
approvals и capability boundaries, что и остальные blueprints.

| MVP blueprint | Trigger | Audience rules | Consent rules | Persona/template | Approval | Capability | Journal |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Напоминание о записи | `appointment.reminder.before` | Ближайшие подтвержденные/ожидающие записи, доступный канал, один reminder на запись. | Transactional reminder allowed; marketing block only with marketing consent; opt-out/suppressed channel skipped. | Вежливый администратор, короткое напоминание и мягкий optional package block. | Первый запуск, шаблон, batch/external delivery. | `communications.send_reminder` через approved batch only. | `communications_delivery_outcome`: draft, approval, send request, delivery state, outcome. |
| Сообщение после визита | `visit.completed.after` | Завершенные визиты в follow-up window, без complaint block, один follow-up на визит. | Service follow-up allowed; opt-out skipped; offer excluded without marketing consent. | Заботливый администратор, вопрос "все ли прошло хорошо". | Первый запуск, шаблон, batch/external delivery. | `communications.send_reminder` через approved batch only. | Тот же delivery/outcome journal. |
| Возврат клиента, который давно не был | `client.inactive.since` | Последний визит старше порога, нет будущей записи, нет активной winback sequence. | Marketing consent required; opt-out skipped; promo frequency cap. | Тактичный администратор, без давления. | Шаблон и каждый batch. | `communications.send_offer` через approved batch only. | Тот же delivery/outcome journal. |
| Пакетное предложение после релевантной услуги | `service.completed.relevant` | Завершенная услуга подходит под активный пакет, нет duplicate offer in cooldown. | Marketing consent required; only available packages; opt-out skipped. | Консультирующий администратор, конкретная польза без неподтвержденных скидок. | Шаблон и каждый batch. | `communications.send_offer` через approved batch only. | Тот же delivery/outcome journal. |
| Черновик ответа на входящий запрос | `inbound.message.received` | Открытый входящий запрос, привязан к бизнесу, еще не отвечен. | Reply allowed in active conversation; no promo without marketing consent; sensitive cases escalate to human. | Аккуратный администратор, отмечает неизвестные факты. | Финальный черновик перед использованием. | `communications.draft`; draft only, no send step. | Тот же journal, но dispatch state stays `not_dispatched`. |

Общий safety contract для всех пяти шаблонов:

- `autonomous_send_allowed=false`;
- `external_dispatch_performed=false` в compiler metadata, output schema и journal;
- первые версии работают только как `draft_only` или `approved_batch_only`;
- send-capabilities создают request/queue state под human gate, а не прямую
  внешнюю отправку из prompt/compiler.

## Canonical Runtime Loop

```text
human description
  -> agent builder dialog
  -> compiled workflow proposal
  -> human approves blueprint/version
  -> run starts by trigger/manual/API
  -> deterministic step or constrained LLM step
  -> validation
  -> capability proposal
  -> ActionOrchestrator/OpenClaw policy check
  -> execute, deny, retry, or pending_human
  -> structured observation
  -> artifacts + ledger + audit timeline
  -> next step or final status
```

Модель участвует в создании плана, извлечении смысла, классификации и генерации
черновиков. Модель не публикует, не отправляет, не платит, не удаляет и не меняет
third-party systems напрямую.

## Component Inventory And Decisions

| Блок | Текущее назначение | Решение | Каноничная роль / действие |
| --- | --- | --- | --- |
| `AIAgents` table and `src/ai_agents_api.py` | Старые пользовательские/админские агенты: name/type/description/prompt/workflow/task/identity/speech style/restrictions/tools. | Используется после адаптации. | Становится `Persona` и legacy chat config. Backend serializer уже возвращает `persona`/`voice` для `persona_agent_id`. `workflow` внутри `AIAgents` не должен быть source of truth для runtime после миграции в blueprints. |
| `AIAgentConversations`, `AIAgentMessages`, `src/chats_api.py` | История чатов и sandbox/test для коммуникационных агентов. | Используется после адаптации. | Сохраняем как conversation memory/channel history для persona/chat agents. Run-level side effects должны идти через blueprint + orchestrator. |
| `AIAgentSettings`, `AIAgentsManagement` | Отдельный UI управления чат-агентами и их persona/workflow fields. | Legacy wrapper. | Встроить в `Мои агенты` как вкладку "Голос и стиль". После миграции убрать отдельный параллельный entrypoint. |
| `Businesses.ai_agent_enabled`, `ai_agent_tone`, `ai_agent_restrictions`, `ai_agents_config`, `ai_agent_id` | Legacy business-level settings для включения/настроек агента. | Legacy wrapper. | Использовать как migration source и backward compatibility. После переноса в persona/blueprint пометить deprecated, затем удалить отдельной миграцией. |
| `agent_blueprints` | Product/workflow object. | Используется как есть. | Главная runtime-сущность пользовательского агента. Добавление новых типов агентов идет через `category`, а не через новые параллельные таблицы. |
| `agent_blueprint_versions` | Versioned workflow payload: goal, schemas, steps, persona, allowlist, approvals. | Используется как есть. | Source of truth для compiled workflow. `persona_agent_id` используется как связь с `AIAgents` и декорируется в API как `persona`/`voice`. |
| `agent_runs`, `agent_run_steps`, `agent_artifacts`, `agent_approvals` | Запуски, шаги, результаты, human gates. | Используется как есть. | История выполнения и proof/audit surface для всех blueprint categories, включая communications. |
| `agent_builder_sessions` | Диалоговый сбор требований и preview перед созданием blueprint. | Используется после адаптации. | Agent Studio session. Уже питает compiler v1 и возвращает preview с `compiler`, `trigger`, `audience`, `limits`, `capability_allowlist`. |
| `agent_blueprint_draft_builder.py` | Heuristic draft builder по описанию и категории. | Используется после адаптации. | Первый слой Agent Compiler. Добавлен `compile_agent_blueprint()` и категория `communications` с typed trigger/audience/sources/steps/capabilities/approvals/limits/output schema. |
| `agent_blueprint_workspace.py` | DataHub catalog, source normalization, generic artifacts, review/journal/diff. | Используется как есть. | Рабочее пространство blueprint: sources, result review, used sources, version diff, human journal. |
| `agent_source_ingestion.py`, `agent_datahub.py` | Загрузка файлов/текста и catalog источников. | Используется как есть. | Data sources layer для compiled workflow. |
| `AgentBlueprintRunner` | Выполнение steps, artifact generation, approvals, capability calls. | Используется после адаптации. | Единый runner для blueprint categories. Нужно расширять step types и capability map, но не плодить отдельные runners для communications. |
| `agent_blueprint_orchestrator.py` | Подключает handler map для blueprint capability steps. | Используется как есть. | Bridge к общей capability map OpenClaw/ActionOrchestrator. `outreach.send_batch` и Stage 4 capabilities подключены через `services/agent_capability_handlers.py`. |
| `ActionOrchestrator` | Policy/approval/billing/idempotency/callback/outbox/audit execution boundary. | Используется как есть. | Каноничный execution boundary для side effects из blueprint runs и внешних agent APIs. |
| OpenClaw contract docs and smoke scripts | M2M capabilities, callbacks, health, support export, billing reconciliation. | Используется после адаптации. | Endpoint registration P0 закрыт минимальным registered API в `api/capabilities_api.py`; глубокие ops/export flows расширяются поверх того же `ActionOrchestrator`, без нового runtime. |
| `OpenClawOutboxMetrics` / External Integrations panel | UI диагностики OpenClaw callbacks/actions/support. | Используется после адаптации. | Встроить ключевые части в agent run detail. Отдельная ops panel может остаться для суперадмина/support. |
| `agent_clients`, `agent_action_ledger`, `agent_security_api.py` | Security foundation для внешних агентов/API keys/scopes/self-test/ledger. | Используется как есть. | External Agent API boundary. Не заменяет user-created agents; может запускать approved capabilities/blueprints через тот же orchestrator. |
| `operator_api.py` and operator services | Chat/operator control surface для карточки, отзывов, новостей, услуг, paid actions. | Используется после адаптации. | Operator становится одним из control surfaces для запуска/управления blueprints и approvals. |
| `telegram_bot.py` OpenClaw panel | Telegram owner control surface, approvals, quick actions, support/recovery. | Используется после адаптации. | Telegram control surface для agents/runs/approvals. Не отдельный agent runtime. |
| `admin_prospecting.py` OpenClaw outreach/partnership calls | Prospecting/outreach интеграции, OpenClaw geo/enrich/send bridges. | Используется после адаптации. | Перенести в typed capabilities и вызывать из blueprints через orchestrator. Transitional code remains until capability migration. |
| `prospectingleads` transitional outreach table | Shortlist/contact/draft/send status для supervised outreach. | Используется как есть. | Data source and transitional pipeline table for outreach/partnership/communications until full outreach schema is approved. |
| `frontend/src/pages/dashboard/AgentBlueprintsPage.tsx` | Главный UI для создания/запуска/настройки blueprints. | Используется как есть. | Каноничный экран `Мои агенты`. Расширить communications category и persona tab. |
| `frontend/src/pages/dashboard/ChatsPage.tsx` | Чаты по агентам. | Используется после адаптации. | Channel conversation view tied to persona and/or agent run context. |
| `frontend/public/localos-agent-tools.json`, `localos-agent-policy.json`, `localos-agent-openapi.json`, `localos-agents.txt` | Public/static agent docs and machine-readable policy/tool hints. | Используется после адаптации. | Обновлять только с реально поддерживаемыми capabilities. Не обещать MCP/provider writes/autonomous sends, если нет runtime support. |
| `docs/AGENT_REGISTRY_V1.md` | Реестр доменных агентов и capability rules. | Используется как есть. | Остается registry. Этот документ задает product architecture; registry перечисляет agent roles/capabilities. |
| `docs/agents/harness-architecture.md` | Harness boundary and runtime guide. | Используется как есть. | Подчиненный runtime guide. Этот документ должен ссылаться на него как на подробный boundary. |
| Legacy migration scripts outside Alembic (`src/migrate_add_ai_agents_config.py`, etc.) | Старые one-off migrations/debug. | Legacy wrapper. | Не использовать как runtime source of truth. Новые schema changes только Alembic. Удалять после проверки серверной истории/backup policy. |
| Standalone communication-agent concept | Потенциальная новая сущность рядом с blueprints. | Удалить как продуктовую идею до реализации. | Коммуникация является `AgentBlueprint.category = communications`. |

## Category Canon

Разрешенные категории agent blueprint должны описывать тип workflow, а не отдельный
runtime:

- `communications`: reminders, offers, follow-ups, inbound response drafts.
- `outreach`: supervised lead sourcing, shortlist, drafts, approved queue.
- `partnerships`: partner search/enrich/match/draft.
- `reviews`: reply draft/review/publish request.
- `services`: service optimization suggestions/apply request.
- `documents`: document extraction, risk review, summary/draft.
- `tables`: table analysis, exceptions, report.
- `email`: draft-only email preparation unless send capability is explicitly added.
- `booking`: appointment flow, reminders, change/cancel requests.
- `custom`: draft-only until compiler maps it to typed steps/capabilities.

Adding a new category requires updating:

1. compiler category inference;
2. default version payload;
3. capability allowlist;
4. approval policy;
5. UI labels/scenarios;
6. tests for happy path and safety path;
7. docs/static capability manifests when externally visible.

## Approval And Risk Policy

External side effects require approvals outside prompt text:

- client/partner sends;
- review replies/publications;
- social/map/site publications;
- payments or paid refreshes;
- destructive deletes;
- mass updates;
- credential or integration changes;
- third-party writes.

Draft-only steps can complete without external approval, but the run must show
`external_dispatch_performed=false` and a clear `dispatch_state`.

## Compiled Workflow Requirements

A compiled workflow is ready to run only when it has:

- a category;
- a goal;
- typed input schema;
- ordered steps;
- explicit data sources;
- deterministic validations;
- isolated LLM steps, if any;
- capability allowlist;
- approval policy;
- stop conditions;
- output schema;
- audit fields: `tenant_id`, `actor`, `trace_id`, `idempotency_key`.

If the compiler cannot map a user request to safe typed steps, it must create a
draft-only `custom` blueprint or ask for clarification.

## Cleanup Rule

Every existing agent-related block must end in one of four states:

1. **используется как есть**: сохранить и документировать как каноничный блок;
2. **используется после адаптации**: сохранить с явной целью миграции;
3. **legacy wrapper**: временно сохранить для обратной совместимости;
4. **удалить после миграции**: удалять только после migration script, тестов и доказательства, что UI/API/server flow больше не читает блок.

Ни один блок не должен бессрочно оставаться недокументированным параллельным путем.

## Next Implementation Checkpoints

1. Wire `persona_agent_id` from blueprint versions into UI controls and runner
   context. Backend API decoration is already implemented.
2. Replace safe request/draft handlers for selected capabilities with deeper
   domain integrations only where approval, scopes and audit are already covered.
3. Move OpenClaw diagnostics from integration-only UI into agent run detail.
4. Mark legacy `AIAgents.workflow` and business-level `ai_agent_*` settings as
   migration sources, not future source of truth.
