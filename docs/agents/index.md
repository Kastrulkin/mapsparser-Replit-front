# LocalOS for AI Agents

LocalOS can be used as a supervised operating layer for AI agents working with local businesses.

The safe pattern is:

1. Read business context.
2. Prepare a draft, audit, recommendation, or preview.
3. Ask for approval when the action affects customers, money, public content, external accounts, or irreversible data.
4. Execute only the approved action.
5. Record outcome and expose it to the business.

## What Agents Can Do Today

- Read and summarize map/card data through existing audit and business APIs.
- Generate service optimization suggestions.
- Draft review replies.
- Draft news/posts and content plans.
- Read finance dashboard, data quality, recommendations, history, import previews, and CRM sync previews.
- Work with partnership leads, matching, drafts, approvals, batches, delivery status, and reactions.
- Route Telegram/WhatsApp messages through configured AI-agent webhooks.
- Help superadmin review industry-pattern proposals.

## LocalOS Operator

[LocalOS Operator](localos-operator.md) is the beta main control layer above the dashboard. It treats web chat and Telegram as two surfaces for the same governed Operator core.

Sprint 1 includes the first cached-data web intent at `/dashboard/operator`: `Что требует моего внимания сегодня?`. Sprint 2 connects the same cached brief to the existing Telegram owner-bot `client_today` flow. Sprint 3 adds proposal-only `paid_action_offers` for paid refresh/generation consent. Sprint 4 persists business-level consent policies and limit settings for those offers. Sprint 5 adds read-only paid action preflight for map refresh. Sprints 6-14 add Operator audit events, a disabled execution boundary, an internal adapter stub, a credit reservation ledger plan, reservation finalization, stale reservation recovery, runtime-flagged reserve/rollback contracts, internal fake execution accounting, and usage-window enforcement for auto limits.

Sprints 15-19 add the first practical chat-control workflow: a user can paste a new review into Operator, LocalOS saves it, generates a paid reply draft when credits are available, shows the draft in chat and in the reviews UI, and exposes the same intent through Telegram. The flow charges `review_replies_generate` as paid compute and keeps map publication manual. Sprint 19 adds only a disabled Apify map-refresh enqueue boundary; real provider execution and actual-cost settlement are still later work.

Sprint 20 improves the web/manual UX for that flow: chat results now expose copy/open/billing actions, credit and publication status are shown separately, and saved LocalOS drafts in the reviews UI make the manual copy-to-map boundary explicit.

Sprints 21-25 add the Operator Inbox and manual completion workflow: the dashboard now has a unified queue for review/content/partnership actions, paid generation offers are shown through one registry, Telegram uses the same manual review intake core, and users can mark a copied review reply as manually published without LocalOS writing to external maps.

Sprint 26 turns the `review_replies_generate` offer into a real paid draft action for already saved unanswered reviews. Operator can prepare up to five LocalOS reply drafts, charge one credit per successfully created draft, show the result in chat, and keep publication to maps as manual copy/paste.

Sprint 27 turns `news_generate` into a real paid compute action. Operator can prepare a news draft from web chat or Inbox, save it into `usernews`, charge one credit after successful generation, and keep publication manual.

Sprint 28 turns `social_post_generate` into the same paid compute/manual-publish pattern for social posts. Operator can prepare a post draft, save it as a LocalOS draft, charge one credit on success, and expose copy/manual publication actions.

Sprint 29 connects `services_optimize` as a paid suggestion workflow. Operator reads saved services, prepares improved names/descriptions, saves suggestions into the existing service-regeneration job tables, charges per saved suggestion, and leaves applying changes to a later confirmed action.

Sprint 30 adds Telegram parity for bulk review reply generation. The owner bot can accept `Подготовь ответы на отзывы`, call the same web Operator service, charge credits through the same path, and return draft answers for manual copy/paste publication.

Sprint 31 adds the Apify actual-cost settlement boundary. When a future parser result includes provider cost, LocalOS can convert it to credits at x10, settle the reservation, and charge any overage through `credit_ledger` without running Apify from Operator itself.

Sprint 32 adds the `Проверь новые отзывы` command. Operator now routes it into the existing read-only map-refresh boundary, reports the latest saved review snapshot when refresh is disabled, and points the user to bulk reply generation after refresh.

Sprint 33 adds the refresh-result lifecycle. After a queued refresh completes and parser output is saved, Operator can check the `parsequeue` job, count newly saved reviews, show `найдено N новых отзывов`, and offer bulk reply generation for unanswered new reviews.

Sprint 34 connects worker-side Apify actual-cost settlement for future paid refresh jobs. When an Apify parse has provider cost and a matching `map_reviews_refresh` reservation tagged with `parsequeue_id`, worker can settle the reservation through the existing accounting service; otherwise it skips settlement and completes parsing normally.

Sprint 35 connects the full paid map-refresh chain. The `Проверь новые отзывы` command now runs preflight, reserves estimated credits, enqueues a read-only `parsequeue` job with the queue id stored in reservation metadata, lets the worker/Apify path settle actual cost, and shows the completed refresh result through Operator. External map publication remains manual and unsupported.

Sprint 36 adds the Operator refresh-jobs UI. The dashboard now shows recent read-only map refresh jobs, statuses, new review snippets, a `Проверить результат` action, and a direct transition to bulk reply draft generation for unanswered new reviews.

Sprint 37 adds Telegram follow-up for the same refresh jobs. The owner bot can show recent refresh statuses/results and point the user to `подготовь ответы на отзывы` without starting new parsing, bypassing credits, or publishing to maps.

Sprint 38 adds the confirmed apply step for service optimization suggestions. Operator can now show saved `services_optimize` suggestions, accept an explicit `Применить предложения` approval, update only LocalOS `userservices`, and mark suggestion items as fixed without extra billing or external provider writes.

Sprint 39 adds normalized Operator content history. The dashboard now separates review reply drafts, news drafts, social post drafts, service suggestions, and applied service changes instead of showing all generated artifacts as the same kind of output.

Sprint 40 polishes paid refresh billing visibility. Refresh results and refresh-job history now show reserved credits, actual charged credits, released credits, overage, provider actual cost, and Apify multiplier when settlement data is available.

Sprint 41 adds the first automatic Telegram follow-up for paid refresh completion. After worker marks a read-only map refresh completed, LocalOS can send the owner a one-time Telegram summary with new-review counts, billing status, and the manual next step. It does not publish replies, send customer messages, or write to map providers.

Sprint 42 adds parse reliability visibility for refresh jobs. Operator now shows retry, captcha, failed, and warning states with user-facing explanations from the existing `parsequeue`/worker status, both in the dashboard and compact Telegram summaries. It does not run new parsing or mutate external providers.

Sprint 43 adds a controlled retry request for failed/captcha/warning refresh jobs. The web Operator can create a new paid read-only refresh job from the previous job URL through the same preflight/reserve/enqueue boundary, while leaving the old failed job unchanged and keeping all map publication manual.

Sprint 44 polishes the retry lifecycle. Retry-created refresh jobs carry `retry_source_queue_id` in reservation metadata, refresh history shows them as a linked attempt, and the web Operator immediately checks the new job after the retry request.

Sprint 45 deepens the parse reliability panel. Refresh jobs now expose technical details such as queue status, retry_after, captcha status, resume flag, warning count, and parsed retry attempt markers, so failed Apify/parse jobs are easier to diagnose before scaling paid refresh.

Sprint 46 adds the worker retry/recovery boundary as backend service code. It does not auto-retry failed jobs; it builds a recovery plan that can ask the user to retry manually, and it can release a failed refresh reservation only through an explicit confirmation and the existing credit finalization boundary.

Sprint 47 adds Telegram retry parity. Owner-bot text commands such as `повтори refresh` route into the same `request_refresh_retry` backend service, reserve credits through the same boundary, and keep publication/manual copy rules unchanged.

Sprint 48 improves user-facing refresh billing clarity. Refresh billing state now includes a plain explanation and a summary of reserved, charged, released, outstanding, overage, provider cost, actual credits, and multiplier; the web Operator renders the explanation near the numbers.

Sprint 49 normalizes the “new reviews found” flow. Completed refresh results now include `result_summary` with the count of new reviews, unanswered reviews, and the primary next action; both web Operator and Telegram render this result before offering reply generation.

The next Operator hardening layer connects the GigaChat fallback router to Telegram and exposes the refresh recovery boundary through runtime API. Telegram still runs explicit rules first; only unsupported Operator-like phrases can spend `operator_intent_classify` credits. Refresh recovery can inspect a failed job and, with explicit confirmation, release outstanding reserved credits without retrying silently or writing to map providers.

The Operator model keeps one context, one permission system, one credit/usage ledger, one approval policy, and one audit trail across web and Telegram. Sprint 0 defines the product contract only; it does not imply that the web-chat runtime or Telegram Operator runtime is fully implemented.

## What Agents Must Not Assume

- No public MCP server is confirmed.
- Not every Flask endpoint is a stable public API.
- Not all external providers support write actions.
- Publishing and sending require human approval.
- Review reply publishing to maps is not currently autonomous; LocalOS can prepare drafts, while users copy and publish manually unless a provider write flow is explicitly implemented and approved.
- Billing and payment operations must not be automated by a general agent.

## Related Docs

- Machine-readable tool map: `/localos-agent-tools.json`
- Minimal Agent API OpenAPI contract: `/api/agent-api/openapi.json`
- Static OpenAPI alias: `/localos-agent-openapi.json`
- Sandbox self-test: `POST /api/agent-api/self-test`
- [Capabilities](capabilities.md)
- [LocalOS Operator](localos-operator.md)
- [Harness architecture](harness-architecture.md)
- [Tool registry](tool-registry.md)
- [Planning and goal loops](planning-and-goals.md)
- [Agent use cases](use-cases.md)
- [Approval policy](approval-policy.md)
- [Agent API security model](security-model.md)
- [API endpoints](../api/endpoints.md)
- [API examples](../api/examples.md)
