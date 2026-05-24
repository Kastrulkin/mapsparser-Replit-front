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

Paid actions use the credit balance as the primary permission boundary. If the user has enough credits for a paid function, LocalOS may run it and charge credits without asking for a separate payment confirmation each time.

If credits are insufficient, LocalOS must stop, explain that the balance is not enough, and show a link to billing or plan selection. Human approval is still mandatory for external state changes made on behalf of the business, such as publishing, sending, payments, destructive changes, or bulk changes.

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
- checks: action key, estimated credits, user balance, optional per-action/day/month limits, and disabled policy;
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

Sprint 8 adds the execution adapter contract behind the disabled runtime:

- backend service: `services.operator_paid_action_adapter`;
- adapter stages: `estimate`, `reserve`, `execute`, `finalize`;
- runtime mode: `internal_stub`;
- the execute response includes `adapter_plan` and `adapter_result`.

Sprint 8 still runs dry-run adapter stages only. It does not create parsequeue jobs, call Apify, reserve or charge credits, generate AI content, write to providers, or publish externally. The adapter exists so later sprints can replace the internal stub stage by stage without changing the Operator API contract.

Sprint 9 adds the credit reservation ledger contract:

- reservation table: `operatorcreditreservations`;
- migration: `alembic_migrations/versions/20260521_add_operator_credit_reservations.py`;
- backend service: `services.operator_credit_reservation`;
- execute response field: `reservation_plan`;
- adapter `reserve` stage includes the same reservation plan.

Sprint 9 still does not execute paid actions, call Apify, generate content, write to providers, publish externally, or charge credits. The current execute runtime only calculates whether a reservation could be created after existing active reservations are considered. Actual reserve creation exists as a service boundary for the next controlled runtime step and must not be called by the disabled Operator runtime.

Sprint 10 adds the credit reservation finalization contract:

- finalization service: `services.operator_credit_reservation.finalize_reserved_action_credits`;
- dry-run plan: `services.operator_credit_reservation.build_credit_finalization_plan`;
- charge path: subtract actual credits from `users.credits_balance`, write a negative `credit_ledger` entry with reason `operator_paid_action`, mark charged credits, and release unused reserve;
- release path: release the outstanding reservation without writing `credit_ledger`;
- safety checks: reservation exists, is not already final, actual charge does not exceed outstanding reserve, and current balance is still sufficient at finalization.

Sprint 10 still does not connect finalization to the disabled Operator runtime. It does not call Apify, generate content, write to providers, publish externally, or charge credits from user-facing execution. The finalization service is a narrow internal boundary for later controlled runtime rollout.

Sprint 11 adds the stale reservation recovery contract:

- recovery plan: `services.operator_credit_reservation.build_stale_reservation_recovery_plan`;
- recovery mutation boundary: `services.operator_credit_reservation.release_stale_reserved_credits`;
- stale candidates are active `reserved` rows with outstanding credits older than the configured window;
- release marks those reservations as `released` and adds the outstanding amount to `released_credits`;
- recovery never writes `credit_ledger` and never charges credits.

Sprint 11 still does not connect recovery to a cron job, endpoint, or user-facing Operator execution. It is a recovery boundary for later supervised runtime rollout and should be run only by controlled backend jobs or maintenance tooling when that job is explicitly implemented.

Sprint 12 connects real reservation to the paid-action execute flow only behind the existing disabled runtime flag:

- default runtime flag: `services.operator_paid_preflight.EXECUTION_ENABLED = False`;
- when the flag is disabled, execute remains dry-run only and does not create reservations;
- when the flag is enabled in a controlled test/runtime, execute calls `reserve_paid_action_credits`;
- because the adapter is still `internal_stub`, execute immediately rolls the reservation back through `finalize_reserved_action_credits(..., finalization_mode="release")`;
- idempotency uses the adapter/reservation idempotency key and the database unique key `(business_id, action_key, idempotency_key)`;
- no Apify calls, parsequeue jobs, AI generation, external writes, or credit charges are performed in Sprint 12.

Sprint 12 is still not a real paid external execution rollout. It proves the reserve and rollback boundary under the runtime flag while keeping production behavior unchanged by default.

Sprint 13 adds an internal fake execution path behind the same disabled runtime flag:

- default runtime flag remains `services.operator_paid_preflight.EXECUTION_ENABLED = False`;
- when disabled, execute still performs dry-run only and does not create reservations, charges, jobs, provider calls, AI generations, or external writes;
- when enabled in a controlled test/runtime, execute reserves credits, runs `services.operator_paid_action_adapter.run_paid_action_internal_fake`, and finalizes the reservation through `finalize_reserved_action_credits`;
- the fake adapter charges a tiny internal actual credit amount and releases unused reserved credits, so ledger accounting can be tested end to end without Apify or other providers;
- execute response includes `finalization_result`, `credit_charged`, `credit_released`, and `internal_fake_execution_performed`.

Sprint 13 is still not a real paid external execution rollout. It is an accounting and idempotency proof for the future adapter boundary, with no Apify calls, parsequeue jobs, AI generation, external writes, map publication, or third-party execution.

Sprint 14 adds usage-window enforcement to paid action preflight:

- backend service: `services.operator_paid_preflight.build_paid_action_usage_window`;
- preflight now reads `operatorcreditreservations` to count already charged credits plus active outstanding reservations for the same business, user, and action key;
- default paid execution no longer requires a separate `ask_each_time` confirmation when credits are available;
- optional `auto_with_limits` checks `max_credits_per_day` and `max_credits_per_month` against `used + estimated`, not only against the single estimated action;
- if the optional usage window cannot be read while those limits are active, `auto_with_limits` blocks with `usage_window_unavailable` instead of silently allowing execution;
- if credits are insufficient, preflight returns `insufficient_balance`, `next_step: top_up_credits`, and `billing_url: /dashboard/billing`;
- preflight response includes `usage_window` with today and month usage.

Sprint 21 adds the first Operator Inbox:

- backend service: `services.operator_inbox`;
- API endpoint: `GET /api/operator/inbox?business_id=<id>`;
- web surface: `/dashboard/operator` shows a single queue of review actions, ready reply drafts, content work, and partnership work;
- inbox items expose presentation actions such as `open_section`, `copy_reply`, and `mark_manual_published`.

The inbox is still a governed dashboard layer, not a free-form autonomous agent. It reads LocalOS state, points to the next local workflow, and keeps external publication manual.

Sprint 22 keeps map refresh as a read-only paid-external boundary:

- backend service: `services.operator_map_refresh`;
- default flag: `OPERATOR_APIFY_REFRESH_ENABLED = False`;
- when disabled, map refresh returns a structured blocked plan and creates no jobs;
- when explicitly enabled in a controlled environment, it can enqueue a `parsequeue` job for read-only card parsing;
- it still does not publish, send messages, or write to third-party map providers.

Sprint 23 aligns Telegram with the same Operator core for manual review intake:

- Telegram owner-bot detects the same `manual_review_add_and_reply_generate` intent;
- it calls `services.operator_manual_review.process_operator_chat_message`;
- it records Operator audit events with `channel = telegram`;
- response text repeats that map publication is manual copy/paste.

Sprint 24 exposes paid generation actions through the unified paid-action layer:

- `review_replies_generate`;
- `news_generate`;
- `social_post_generate`;
- `services_optimize`.

These actions are visible as paid generation offers in the Operator Inbox. Generation may charge credits through the configured paid-action path, but external publication remains a separate manual or approval-required action.

Sprint 25 adds the manual publish tracking workflow:

- backend service: `services.operator_manual_publish`;
- API endpoint: `POST /api/operator/review-reply-drafts/<draft_id>/mark-manual-published`;
- web surface: copy the reply, paste it into the provider cabinet manually, then mark the LocalOS draft as `manual_published`;
- audit event: `operator_manual_publish_marked`.

This endpoint updates LocalOS state only. It does not publish to Yandex, Google, 2GIS, or any other third-party system.

Sprint 26 adds paid bulk generation for stored unanswered reviews:

- backend service: `services.operator_review_reply_bulk`;
- API endpoint: `POST /api/operator/review-replies/generate`;
- chat intent: `Подготовь ответы на отзывы`;
- the flow reads already saved `externalbusinessreviews` only;
- it skips reviews that already have an active LocalOS reply draft;
- it reserves and charges credits through the Operator paid-compute path;
- initial pricing is `1` credit per successfully created draft;
- generated drafts are saved in `reviewreplydrafts`;
- the response shows charged credits and keeps map publication manual.

Sprint 26 still does not refresh maps, call Apify, publish to Yandex/Google/2GIS, or send any response on behalf of the business. It only creates LocalOS drafts for manual copy/paste publication.

Sprint 27 turns `news_generate` into a real paid draft action:

- backend service: `services.operator_news_generation`;
- API endpoint: `POST /api/operator/news/generate`;
- chat intent examples: `Подготовь новость: ...`, `Сгенерируй новость про ...`;
- the flow uses preflight -> reserve -> AI generation -> `usernews` draft save -> final credit charge;
- initial pricing is `1` credit per saved news draft;
- if generation fails or returns empty text, the reservation is released and no credit ledger charge is created;
- the response shows charged credits and exposes copy/manual publication UI actions.

Sprint 27 does not publish news to maps, social networks, or other external providers. It only saves a LocalOS `usernews` draft for manual review and copy/paste publication.

Sprint 28 turns `social_post_generate` into a real paid draft action:

- backend service: `services.operator_social_post_generation`;
- API endpoint: `POST /api/operator/social-posts/generate`;
- chat intent examples: `Подготовь пост для соцсетей: ...`, `Сгенерируй пост про ...`;
- the flow uses the same preflight -> reserve -> AI generation -> draft save -> final credit charge boundary;
- initial pricing is `1` credit per saved social post draft;
- if generation fails or returns empty text, the reservation is released and no credit ledger charge is created;
- the web Operator UI can trigger the action from Inbox and copy the generated post.

Sprint 28 does not publish to Telegram, Instagram, VK, maps, or other external channels. It only prepares and saves a LocalOS draft for manual copy/paste publication.

Sprint 29 turns `services_optimize` into a paid suggestion workflow:

- backend service: `services.operator_services_optimization`;
- API endpoint: `POST /api/operator/services/optimize`;
- chat intent examples: `Оптимизируй услуги`, `Улучши SEO описания услуг`;
- the flow reads saved `userservices`, runs preflight -> reserve -> AI suggestion generation -> saved suggestion job -> final credit charge;
- suggestions are saved in `serviceregenerationjobs` and `serviceregenerationjobitems` with status `suggested`;
- initial pricing is `1` credit per saved service suggestion, up to five services per run;
- applying the suggested names/descriptions is not part of this sprint and must be a separate confirmed action.

Sprint 29 does not update `userservices`, publish to providers, or mutate external accounts. It only saves LocalOS suggestions for later review.

Sprint 30 adds Telegram parity for bulk review reply generation:

- Telegram owner-bot detects `Подготовь ответы на отзывы` and similar commands;
- it calls the same `services.operator_review_reply_bulk.generate_review_reply_drafts_for_unanswered_reviews` service used by web Operator;
- the flow keeps the same preflight, reserve, charge/release, audit, and manual-publication behavior;
- Telegram response includes generated drafts and repeats that map publication is manual copy/paste.

Sprint 30 does not bypass credits or publish replies to maps. Telegram is only another transport surface over the same guarded workflow.

Sprint 31 adds Apify actual-cost settlement:

- backend service: `services.operator_apify_settlement`;
- provider actual cost is converted to credits with the configured Apify multiplier x10 and rounded up;
- normal path finalizes the existing Operator reservation with the actual credit amount;
- if actual cost exceeds the reserved amount, the reserved amount is charged through reservation finalization and the overage is written as a separate `credit_ledger` debit;
- zero actual cost releases the reservation;
- invalid cost, missing reservation, action mismatch, or insufficient overage balance blocks settlement.

Sprint 31 does not call Apify or enqueue parsing jobs. It only defines the accounting boundary that a future parser/result handler can call after Apify returns actual cost.

Sprint 32 adds the fresh-review refresh command:

- backend service: `services.operator_fresh_reviews`;
- web chat intent examples: `Проверь новые отзывы`, `Обнови отзывы`;
- the flow captures the latest saved review snapshot, calls the read-only map-refresh enqueue boundary, and returns either queued status or a blocked explanation;
- when the refresh runtime flag is disabled, Operator shows the latest saved review counts instead of pretending fresh data was checked;
- after a queued refresh, Operator suggests the next manual command: `подготовь ответы на отзывы`.

Sprint 32 does not call Apify directly, settle actual provider cost, publish replies, or write to external map providers. It only routes the user command into the existing read-only refresh boundary.

Sprint 33 connects the queued refresh to a result lifecycle:

- backend service: `services.operator_refresh_result`;
- API endpoint: `GET /api/operator/reviews/refresh-results/<queue_id>`;
- web Operator can check a queued refresh result from the chat response;
- while `parsequeue` is pending/processing, Operator tells the user to wait;
- after completion, Operator compares the refresh start time with saved `externalbusinessreviews.created_at`, counts newly saved reviews, and highlights how many still need replies;
- the web UI shows a compact result card, the new review snippets, and a `Подготовить ответы` action when there are unanswered reviews.

Sprint 33 does not call Apify directly, settle actual provider cost, charge credits, publish replies, or write to external map providers. It only makes completed refresh results visible to the user from already saved parser output.

Sprint 34 connects the worker to the Apify actual-cost settlement boundary:

- Apify business parsing now carries `usageTotalUsd`/`usageUsd` from the Actor run metadata into worker debug payload;
- after a successful Apify parse, worker checks for a reserved `map_reviews_refresh` Operator reservation whose metadata contains `parsequeue_id`;
- when both a matching reservation and provider cost exist, worker calls `services.operator_apify_settlement.settle_apify_actual_cost`;
- if cost or reservation metadata is missing, worker logs a skipped settlement and completes the parse normally;
- settlement failures are isolated behind a database savepoint so parser completion is not lost.

Sprint 34 does not create the paid map refresh reservation, enqueue paid refresh from the UI, run Apify from Operator directly, publish replies, or write to external map providers. It only lets future paid refresh jobs be settled when the worker has enough metadata.

Sprint 35 connects the full paid map-refresh chain:

- backend services: `services.operator_fresh_reviews` and `services.operator_map_refresh`;
- chat intent examples: `Проверь новые отзывы`, `Обнови отзывы`;
- the flow uses preflight -> reserve -> enqueue `parsequeue` -> worker Apify parse -> actual-cost settlement -> Operator refresh result;
- the reservation metadata includes `parsequeue_id`, so the worker can match a completed Apify job to the original `map_reviews_refresh` reservation;
- the initial queue response shows reserved estimated credits and explains that final charge is based on the Apify result;
- the result UI uses the Sprint 33 lifecycle to show completed refresh results, new review counts, unanswered counts, and the next `Подготовить ответы` action.

Sprint 35 still does not publish replies, send messages, or write to Yandex, Google, 2GIS, or other external map providers. It performs read-only refresh and billing settlement only.

Sprint 36 adds the Operator UI for refresh jobs:

- API endpoint: `GET /api/operator/reviews/refresh-jobs`;
- backend service: `services.operator_refresh_result.list_refresh_jobs`;
- web surface: `/dashboard/operator` shows recent map-review refresh jobs, statuses `processing`/`completed`/`failed`, new review counts, unanswered counts, and snippets;
- each job exposes `Проверить результат`, `Открыть отзывы`, and, when there are unanswered new reviews, `Подготовить ответы`;
- the UI reuses the Sprint 33 single-result endpoint for explicit checks and the Sprint 26 bulk reply workflow for answer drafts.

Sprint 36 does not add new parser execution, billing behavior, direct Apify calls from Operator, external reply publication, or provider writes. It is a visibility and control surface over the Sprint 35 refresh lifecycle.

Sprint 37 adds Telegram follow-up for refresh jobs:

- Telegram owner-bot recognizes status/result requests such as `статус обновлений отзывов` and `проверить результат обновления`;
- reviews menu includes `Статус обновлений`;
- Telegram uses `services.operator_refresh_result.list_refresh_jobs` through `services.telegram_dashboard.build_refresh_jobs_text`;
- the response shows recent refresh statuses, new review counts, snippets, and the next command `подготовь ответы на отзывы`.

Sprint 37 does not start new map refreshes, bypass credit checks, publish replies, or write to external map providers from Telegram. It is a read-only transport surface over the same Operator refresh history.

Sprint 38 adds confirmed application for saved service optimization suggestions:

- backend service: `services.operator_services_optimization.apply_service_optimization_suggestions`;
- API endpoint: `POST /api/operator/services/optimize/apply`;
- web Operator shows the saved suggestions and a separate `Применить предложения` confirmation action;
- API apply requires explicit `confirm_apply: true`;
- only after that confirmation LocalOS updates `userservices.optimized_name` and `userservices.optimized_description`;
- applied suggestion items move from `suggested` to `fixed`, and the parent `serviceregenerationjobs` status/counts are refreshed.

Sprint 38 does not generate new suggestions, charge additional credits, publish service changes to Yandex, Google, 2GIS, or write to any external provider. It is an internal LocalOS mutation after explicit user approval.

Sprint 39 adds normalized content history for Operator:

- backend service: `services.operator_content_history.list_operator_content_history`;
- API endpoint: `GET /api/operator/content-history`;
- web Operator shows a separate `Черновики и предложения` section;
- content items are separated by kind: `review_reply_draft`, `news_draft`, `social_post_draft`, `service_suggestion`, `service_apply`;
- new social post drafts are saved with `prompt_key = operator_social_post_generate`, so they no longer look identical to news drafts in history.

Sprint 39 does not publish drafts, send social posts, or apply service suggestions automatically. It is a read/history surface over existing LocalOS draft and suggestion tables.

Sprint 40 adds user-facing refresh billing polish:

- refresh result and refresh-job history include `billing_state`;
- `billing_state` shows reservation id/status, estimated credits, outstanding reserved credits, charged credits, released credits, overage credits, provider, provider actual cost, multiplier, and actual credits when available;
- Apify settlement stores provider actual cost and calculated credit metadata back onto the matching reservation for later UI display;
- web Operator shows billing details on the refresh result card and on each recent refresh job.

Sprint 40 does not change pricing, call Apify directly from Operator, publish review replies, or write to external map providers. It makes the already implemented paid refresh lifecycle understandable to the user.

Sprint 41 adds Telegram actual follow-up after paid refresh completion:

- backend service: `services.operator_refresh_telegram_followup`;
- worker calls `dispatch_operator_refresh_telegram_followup` after a successful read-only map parse is marked completed;
- the follow-up is sent through the existing owner-bot transport to the business owner `users.telegram_id`;
- the message includes refresh status, new review count, unanswered count, billing summary, short snippets, and the next manual command `подготовь ответы на отзывы`;
- idempotency is stored on the matching `operatorcreditreservations.metadata` using `telegram_refresh_followup_attempted_at` and `telegram_refresh_followup_delivered_at`;
- if the owner has no Telegram id, the reservation is missing, or the job is still processing, the service returns a structured skipped result.

Sprint 41 does not start new parser jobs, bypass credit checks, publish replies, send customer messages, or write to external map providers. It only sends a one-time owner notification about a refresh job that has already completed in LocalOS.

Sprint 14 still does not call Apify, create parsequeue jobs, generate AI content, write to external providers, publish to maps, or enable production execution. It only tightens the safety gate before future paid runtime rollout.

Sprint 15 adds manual review intake through Operator chat:

- API endpoint: `POST /api/operator/chat`;
- backend service: `services.operator_manual_review.process_operator_chat_message`;
- supported intent: `manual_review_add_and_reply_generate`;
- the review is saved into `externalbusinessreviews` with `source = manual_chat`;
- a reply draft is saved into `reviewreplydrafts`;
- the chat response returns the generated reply and reminds the user that map publication is manual.

Sprint 16 exposes the same flow in the dashboard:

- `/dashboard/operator` includes a chat-command textarea;
- successful intake refreshes the Operator brief and event journal;
- external review list responses include `reply_draft_id`, `reply_draft_text`, and `reply_draft_status`, so the review and draft can appear in the reviews UI.

Sprint 17 charges credits for paid compute in the manual review flow:

- action key: `review_replies_generate`;
- fixed initial estimate: `1` credit;
- flow: preflight balance check -> reserve -> generate reply -> finalize charge;
- if generation fails, the reservation is released and no credit ledger charge is created;
- if balance is insufficient, Operator returns `insufficient_balance` and `/dashboard/billing`.

Sprint 18 connects the same manual review intent to Telegram:

- the existing owner bot classifies review-add/reply messages;
- Telegram uses the same `process_operator_chat_message` backend service;
- no Telegram-specific bypass exists for credit checks or manual publication boundaries.

Sprint 19 adds a gated map refresh enqueue boundary:

- backend service: `services.operator_map_refresh`;
- default flag: `OPERATOR_APIFY_REFRESH_ENABLED = False`;
- when explicitly enabled in a controlled runtime, LocalOS can enqueue a `parsequeue` job with `source = apify_yandex`;
- this boundary does not call Apify directly from chat and does not publish or write to maps;
- provider actual cost settlement is still a later worker-result step and must not be claimed until implemented.

Sprints 15-19 make the first practical chat-control workflow available while keeping external map writes manual. Real Apify refresh remains behind a disabled flag and actual provider-cost charging still requires a result-settlement step.

Sprint 20 improves the manual review workflow UX:

- completed chat results include structured `ui_actions` for `copy_reply` and `open_reviews`;
- insufficient-credit results include an `open_billing` action;
- the web Operator result panel shows execution status, credit charge status, and manual-publication status separately;
- the result panel exposes buttons to copy the generated reply and open the reviews tab;
- the reviews UI labels LocalOS drafts with a manual-publication note and copy feedback.

Sprint 20 still does not publish replies to external map providers, call Apify, or enable provider write support. It only makes the existing manual-copy workflow clearer and safer for users.

Policy modes:

- `ask_each_time`: legacy/default mode; payment consent is covered by available credits, so no extra prompt is required before generation or refresh.
- `auto_with_limits`: optional tighter limits for users who want per-action/day/month caps in addition to balance checks.
- `disabled`: block this paid action class until the user changes settings.

Credits are the access gate. A stored policy is not a separate billing approval ceremony; it is only an optional way to disable or cap a class of paid actions. Runtime checks must always confirm balance, estimated cost, optional action limits, and the external/manual approval boundary.

Recommended limits:

- `max_credits_per_action`;
- `max_credits_per_day`;
- `max_credits_per_month`;
- `low_balance_warning_threshold`;
- optional intent-specific limits, such as review replies, map refresh, news generation, social posts, service optimization, competitor parse.

Insufficient balance copy:

```text
Недостаточно кредитов для этой функции.
Пополните счёт или выберите тариф: /dashboard/billing
```

Optional settings can still show `Настроить лимиты` and `Отключить действие`, but the normal product path should not ask the user to confirm every paid generation while credits are available.

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

Credit reservation rules:

- reservations are scoped by `business_id`, `user_id`, `action_key`, and `idempotency_key`;
- active reservations reduce the available unreserved balance before a new paid action can start;
- reservation creation must be idempotent for the same business/action/idempotency key;
- finalization must either charge actual usage through `credit_ledger` or release the unused reserve;
- finalization must re-check current balance before charging because balance can change after reservation;
- stale reserved rows must have a recovery path that releases outstanding credits without creating a charge;
- runtime-flagged internal fake execution may create a reservation only behind the disabled execution flag in controlled tests;
- optional `auto_with_limits` must account for already charged credits and active reservations in the current day/month window before allowing a new execution;
- insufficient balance should return a top-up path instead of a consent prompt;
- every user-facing execution response must keep the distinction between `reserved`, `charged`, and `released`.

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

If the user has enough credits, Operator may refresh without asking again, then report the charge. If the balance is insufficient, Operator stops and links to billing.

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
Генерирую черновики ответов. После выполнения покажу, сколько кредитов списано.
```

After execution:

```text
Готово. Списано 7 кредитов.
Подготовил 4 ответа как черновики. Публикация в карты выполняется вручную.
```

### Add Manual Review And Reply

User:

```text
Добавь новый отзыв в список и сгенерируй ответ:
Попала в салон случайно - получила сертификат на массаж лица...
```

Operator:

```text
Добавил отзыв в список и подготовил черновик ответа.

Ответ:
Спасибо за такой подробный и тёплый отзыв...

Списано кредитов: 1.
Публикация в карты пока вручную: скопируйте ответ и вставьте его в кабинете карты.
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
