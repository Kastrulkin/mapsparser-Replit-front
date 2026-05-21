# LocalOS Operator

Status: `beta`

LocalOS Operator is the planned main control layer above the LocalOS dashboard. Users should be able to manage LocalOS either by clicking through the cabinet or by speaking to the same system through chat.

Operator is not a separate bot product. It is a governed orchestration layer with multiple surfaces:

- web chat inside the LocalOS dashboard;
- Telegram chat through the existing Telegram control surface;
- future surfaces such as WhatsApp, email, or voice, when they are explicitly implemented.

All surfaces must route into one Operator core with the same context, permissions, billing rules, approvals, audit trail, and tool contracts.

## Product Principle

The dashboard remains the detailed manual interface. Operator becomes the goal-oriented control surface.

Users can still open Reviews, Maps, Content, Partnerships, Finance, and Services manually. They can also write:

- `Что требует моего внимания сегодня?`
- `Проверь новые отзывы.`
- `Подготовь ответы на отзывы.`
- `Составь пост для Яндекс Карт.`
- `Найди партнёров рядом.`
- `Почему стало меньше звонков?`

Operator should answer with a short summary, state cards, proposed actions, and explicit buttons such as `Показать`, `Подготовить`, `Скопировать`, `Настроить лимиты`, or `Открыть раздел`.

## Runtime Boundary

Operator follows the same harness rule as other LocalOS agent flows:

```text
user message
  -> intent classification
  -> business context builder
  -> action/tool proposal
  -> schema validation
  -> permission, consent, billing, and approval policy
  -> execute, draft, deny, or pending_human
  -> structured observation
  -> user-facing response
  -> audit and ledger events
```

The model may interpret the request and propose an action. LocalOS code must enforce tenant scope, permissions, consent policy, credit budgets, approval requirements, manual-publication limits, tool execution, and audit records.

## Surfaces

### Web Chat

Web chat can show richer responses:

- action cards;
- tables and compact dashboards;
- copy buttons;
- draft editors;
- links into dashboard sections;
- approval and consent panels.

Recommended first route: `/dashboard/operator`.

### Telegram

Telegram is a transport adapter to the same Operator core. It should use concise messages and inline buttons, but must not bypass permissions, consent, billing, or approval policy.

Telegram responses should prefer:

- short summaries;
- one to three next actions;
- links into the dashboard for detailed review;
- explicit copy/manual-publication flows.

## First MVP Intent

Sprint 1 starts with:

```text
Что требует моего внимания сегодня?
```

The first version is available as a cached-data MVP through:

- web route: `/dashboard/operator`;
- API route: `GET /api/operator/attention-brief?business_id=<id>`;
- Telegram owner-bot route: `client_today` / `Что требует моего внимания сегодня?`;
- shared backend builder: `services.operator_attention.build_attention_brief`.

This version uses cached LocalOS data only:

- reviews known to be unanswered;
- pending approvals;
- card/profile freshness signals;
- content tasks;
- partnership leads;
- finance warnings when already available;
- recent support or audit events.

If the answer needs fresh external data, Operator must ask for paid refresh consent or follow a previously configured consent policy. Sprint 1/Sprint 2 do not execute paid refreshes, AI generation, provider writes, or external publication.

Sprint 2 connects the same cached brief to the existing Telegram owner-bot control surface. The Telegram response is a compact transport-specific formatter over the same Operator core, not a separate data path.

Sprint 3 adds the first code-level paid action offer contract. The attention brief may now include `paid_action_offers` with proposal-only metadata for map refresh and future paid generation actions. This is not execution: Sprint 3 still does not call Apify, generate content, charge credits, persist consent, write to providers, or publish externally.

## Action Taxonomy

Operator actions use these product-level classes. Tool-level risk classes still apply and are documented in [Tool registry](tool-registry.md).

| Class | Meaning | Examples | Cost behavior | Approval behavior |
| --- | --- | --- | --- | --- |
| `free_cached` | Reads data already stored in LocalOS | show last known reviews, pending approvals, saved audit, finance summary | no paid external or AI charge | no approval by default |
| `paid_compute` | Uses AI/model compute or internal paid generation | generate review replies, news, social posts, service optimization, content plan | charge credits/tokens through ledger | generation may be auto-with-limits; external publication is separate |
| `paid_external` | Calls paid external data/API providers | Apify map refresh, competitor parse, external enrichment | provider actual cost converted to credits, with platform multiplier where configured | first-use consent or configured auto-with-limits |
| `manual_external` | Helps user perform an external action manually | copy a review reply, open provider console, mark as published | usually free after draft generation | user performs the third-party action |
| `approval_required` | Changes LocalOS or third-party state, sends messages, publishes, pays, deletes, or bulk-mutates | outreach send batch, payment change, destructive update, external publish when supported | depends on underlying action | human approval required outside prompt text |
| `planned_gap` | Desired capability that is not implemented | direct map reply publishing, public MCP server, unsupported provider write action | not executable | must be described as unavailable/planned |

## Paid Action Consent Policy

Paid actions require a business-level consent policy. The policy is scoped by business because credits are charged to the business balance.

Sprint 3 code source of truth:

- paid action registry: `services.operator_paid_actions.PAID_ACTIONS`;
- Apify planning multiplier: `services.operator_paid_actions.APIFY_CREDIT_MULTIPLIER`;
- attention brief field: `paid_action_offers`;
- proposal status: `proposal_only`.

Sprint 4 code source of truth:

- consent policy table: `operatorconsentpolicies`;
- migration: `alembic_migrations/versions/20260520_add_operator_consent_policies.py`;
- backend service: `services.operator_consent_policy`;
- API read endpoint: `GET /api/operator/consent-policy?business_id=<id>`;
- API update endpoint: `PUT /api/operator/consent-policy/<action_key>`;
- web controls: `/dashboard/operator` paid action cards.

Sprint 4 persists consent policy only. It still does not execute paid actions, call Apify, generate content, charge credits, write to providers, or publish externally.

Sprint 5 adds a paid action preflight gate:

- backend service: `services.operator_paid_preflight`;
- API endpoint: `POST /api/operator/paid-actions/<action_key>/preflight`;
- first supported action: `map_reviews_refresh`;
- checks: action key, estimated credits, user balance, consent mode, per-action/day/month limits, and disabled policy;
- status: `preflight_only`.

Sprint 5 is still read-only. It does not create parsequeue jobs, call Apify, reserve or charge credits, generate AI content, write to providers, or publish externally.

Sprint 6 adds Operator observability over the existing agent action ledger:

- backend service: `services.operator_audit`;
- ledger capability: `localos.operator`;
- API endpoint: `GET /api/operator/events?business_id=<id>`;
- recorded events: `operator_context_built`, `operator_consent_decision`, `operator_paid_action_estimated`;
- web surface: `/dashboard/operator` shows the recent Operator journal.

Sprint 6 still does not execute paid actions, call Apify, reserve or charge credits, generate AI content, write to providers, or publish externally. The Operator journal is an audit trail, not the credit ledger.

Sprint 7 adds a disabled execution boundary:

- backend service: `services.operator_paid_executor`;
- API endpoint: `POST /api/operator/paid-actions/<action_key>/execute`;
- recorded event: `operator_execution_blocked`;
- web surface: `/dashboard/operator` can call execute and show why runtime is blocked.

Sprint 7 still always blocks execution while the runtime flag is disabled. It reuses preflight, returns structured refusal data, and records observability only. It does not create parsequeue jobs, call Apify, reserve or charge credits, generate AI content, write to providers, or publish externally.

Policy modes:

- `ask_each_time`: explain the cost and ask before every paid action.
- `auto_with_limits`: allow paid actions without repeated prompts while configured limits and balance rules hold.
- `disabled`: block this paid action class until the user changes settings.

`auto_with_limits` must not be accepted without explicit positive `max_credits_per_action` and `max_credits_per_day`. A stored policy is permission to skip repeat prompts only when future runtime checks also confirm balance, estimated cost, action limits, and the external/manual approval boundary.

Recommended limits:

- `max_credits_per_action`;
- `max_credits_per_day`;
- `max_credits_per_month`;
- `low_balance_warning_threshold`;
- optional intent-specific limits, such as review replies, map refresh, news generation, social posts, service optimization, competitor parse.

First-use copy:

```text
Чтобы получить актуальные данные или сгенерировать материалы, LocalOS использует платные операции и списывает кредиты.
Сейчас у вас N кредитов; этого хватит примерно на M таких операций.
Разрешить LocalOS выполнять такие действия без повторного вопроса в пределах лимитов?
```

Buttons:

- `Разрешить`;
- `Настроить лимиты`;
- `Спрашивать каждый раз`.

After every paid execution, Operator must show the actual charge:

```text
Готово. Списано 7 кредитов. Остаток: 993.
```

If limits or balance are insufficient, Operator must stop and ask.

## Cost Accounting

Paid external refreshes use actual provider cost when available.

For Apify-backed map parsing:

```text
provider_actual_cost -> internal credits * configured platform multiplier
```

The current product rule for this planning track is:

```text
Apify actual cost -> credits x10
```

The exact conversion rate, rounding, and currency assumptions must be implemented in billing code before runtime rollout. Documentation and UI must not imply exact charges until the runtime exposes estimates or actual ledger entries.

Paid compute uses the same ledger principle as current AI token accounting:

- estimate when possible;
- reserve or warn before execution when policy requires;
- charge actual usage after execution;
- record usage in credit/token ledger;
- show final charged credits to the user.

## Cached Vs Fresh Data

Operator must distinguish cached reads from fresh external refreshes.

Cached answer:

```text
Последние известные данные от 18 мая, 14:20. Нашёл 2 отзыва без ответа.
```

Fresh answer:

```text
Данные по отзывам обновлялись 2 дня назад.
Могу показать последние известные данные бесплатно или обновить карты сейчас за кредиты.
```

If the user previously allowed auto-refresh within limits, Operator may refresh without asking again, then report the charge.

## Review Replies And Manual Publication

Current status: LocalOS may prepare review reply drafts, but must not claim it can publish replies to Yandex, Google, 2GIS, or other map providers unless that provider write flow is explicitly implemented and verified.

Allowed:

- find reviews from stored data;
- refresh reviews through a paid external parse when supported;
- generate reply drafts as `paid_compute`;
- save drafts in LocalOS;
- show copy buttons;
- open the external provider screen when a safe link exists;
- let the user mark a draft as manually published.

Not allowed yet:

- say `я опубликовал ответ`;
- say `отправил ответ в карты`;
- autonomously write to map providers;
- imply provider write support where it is not implemented.

User-facing copy:

```text
Я подготовлю ответы и сохраню их как черновики.
Публикация в карты сейчас выполняется вручную: вы копируете текст и вставляете его в кабинете Яндекс/Google/2ГИС.
```

## Example Flows

### Attention Brief

User:

```text
Что требует моего внимания сегодня?
```

Operator:

```text
Нашёл 4 пункта:
1. 2 отзыва без ответа по последним сохранённым данным.
2. Карточка Яндекс не обновлялась 12 дней.
3. Есть 5 партнёров в shortlist.
4. Один черновик поста ждёт решения.

Данные по отзывам старше 2 дней. Обновить карты сейчас за кредиты или показать старые данные?
```

### Generate Review Replies

User:

```text
Подготовь ответы на отзывы.
```

Operator:

```text
Это платная AI-операция. Баланса хватит примерно на 120 таких задач.
Разрешить генерацию ответов без повторного вопроса в пределах лимитов?
```

After execution:

```text
Готово. Списано 7 кредитов.
Подготовил 4 ответа как черновики. Публикация в карты выполняется вручную.
```

### Refresh Reviews

User:

```text
Проверь новые отзывы сейчас.
```

Operator:

```text
Для актуальной проверки нужно обновить данные из карт. Это платный внешний парсинг.
Ваших кредитов хватит примерно на 100 обновлений такого типа.
Запустить обновление?
```

After Apify result:

```text
Проверка завершена. Списано 10 кредитов.
Найдено 3 новых отзыва, 2 без ответа.
```

## Audit And Ledger Events

Every Operator action should be traceable:

- `operator_message_received`;
- `operator_intent_classified`;
- `operator_context_built`;
- `operator_paid_action_estimated`;
- `operator_consent_decision`;
- `operator_tool_proposed`;
- `operator_tool_executed`;
- `operator_draft_created`;
- `operator_manual_action_presented`;
- `operator_usage_charged`;
- `operator_approval_requested`;
- `operator_approval_result`;
- `operator_final_response`.

Paid action audit records should include:

- business id;
- actor;
- channel: `web` or `telegram`;
- action class;
- tool/capability;
- consent policy used;
- estimate when available;
- actual provider cost when available;
- credits charged;
- ledger id;
- trace id;
- result status.

## Sprint 0 Done Criteria

This document is the Sprint 0 product contract. Runtime implementation should not start until:

- action taxonomy is accepted;
- paid consent policy is accepted;
- manual publication limitations are accepted;
- tool registry and approval docs reference these rules;
- future implementation tickets can be mapped to `free_cached`, `paid_compute`, `paid_external`, `manual_external`, `approval_required`, or `planned_gap`.
