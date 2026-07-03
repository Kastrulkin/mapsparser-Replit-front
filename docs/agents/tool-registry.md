# Agent Tool Registry

Status: `internal`

This page defines how LocalOS should document and govern agent-visible tools and capabilities. It complements the capability map in [Capabilities](capabilities.md).

## Principle

A tool is a contract between the model and the LocalOS harness. The model may request it; the harness validates and decides whether it may run.

Avoid broad generic tools. Prefer narrow domain tools with explicit schemas, risk class, and approval behavior.

## Tool Contract

Each agent-visible tool or capability should define:

- `name`;
- `capability`;
- `purpose`;
- `when_to_use`;
- `when_not_to_use`;
- `input_schema`;
- `output_schema`;
- `risk_class`;
- `side_effect`;
- `resource_scope`;
- `permission_policy`;
- `approval_policy`;
- `timeout_seconds`;
- `result_size_limit`;
- `retry_policy`;
- `audit_policy`;
- `error_format`.

## Risk Classes

Use these classes when adding or reviewing tools:

- `read_only`: reads scoped LocalOS data.
- `search_only`: searches public or configured sources.
- `compute_only`: transforms provided data without side effects.
- `draft_only`: creates a draft, preview, recommendation, or plan.
- `write_local`: writes local artifacts or internal temporary state.
- `write_internal`: changes LocalOS records.
- `write_external`: changes third-party systems.
- `communication`: sends messages to customers, partners, prospects, or staff.
- `financial`: affects money, billing, payments, credits, or tariffs.
- `identity_access`: changes users, keys, credentials, scopes, or access.
- `destructive`: deletes, disables, rolls back, or bulk-mutates data.
- `privileged_admin`: requires superadmin or operator-only authority.

High-risk classes require approval unless a narrow product policy explicitly allows automation.

## Operator Action Classes

LocalOS Operator uses product-level action classes in addition to tool risk classes. See [LocalOS Operator](localos-operator.md) for the full product contract.

| Action class | Meaning | Tool examples | Consent and billing |
| --- | --- | --- | --- |
| `free_cached` | Read already stored LocalOS data | last known reviews, saved audit, pending approvals | no paid charge by default |
| `paid_compute` | Use model/AI compute to create or transform content | `reviews.reply_draft`, `news.generate`, `social.post.generate`, `services.optimize` | charge credits/tokens through ledger; allow auto-with-limits only after consent |
| `paid_external` | Call paid external data providers or parsers | map refresh through Apify, competitor parse, enrichment | charge provider actual cost converted to credits; Apify planning rule is actual cost to credits x10 |
| `manual_external` | Help user perform an external action manually | copy reply draft, open provider console, mark manually published | no external write by LocalOS |
| `approval_required` | Publish, send, pay, delete, change third-party state, or bulk mutate | outreach send, external publish when supported, payment changes, destructive writes | human approval outside prompt text |
| `planned_gap` | Desired but unavailable capability | direct map reply publishing, public MCP endpoint, unsupported provider write | not executable; must be shown as unavailable/planned |

Tool registry entries for Operator-facing tools should include both `risk_class` and `operator_action_class`.

## Paid Action Contract

Tools with `operator_action_class` of `paid_compute` or `paid_external` must define:

- `cost_source`: model tokens, provider actual cost, fixed credit price, or estimate-only.
- `estimate_policy`: whether the tool can estimate before execution.
- `charge_policy`: when credits are charged and how actual usage is recorded.
- `paid_action_mode`: default credit-balance gate, optional `auto_with_limits`, or `disabled`.
- `budget_fields`: max credits per action, day, and month where applicable.
- `ledger_event`: usage/credit ledger record expected after execution.

Paid actions should never be hidden inside a generic chat response. The user must be able to see charges and balance in LocalOS. If credits are insufficient, the tool must stop and link to billing or plan selection.

## Permission Decisions

The permission engine should return one of:

- `allow`;
- `deny`;
- `approval_required`;
- `ask_user`;
- `require_stronger_auth`;
- `draft_only`;
- `sandbox_only`.

Every decision should be recorded with:

- tool or capability;
- risk class;
- argument hash or safe summary;
- tenant and actor;
- policy rule;
- decision;
- approval id, when applicable;
- timestamp.

## Draft And Commit Split

Risky actions must be split into separate draft and commit operations.

Examples:

| Draft/preview | Commit |
| --- | --- |
| `reviews.reply_draft` | `reviews.publish_external` when provider write support exists |
| `news.generate` | `content.publish_external` |
| `partnership.draft_offer` | `partnership.send_batch` |
| `finance.import_preview` | `finance.import_apply` |
| `agent.approval_request` | `execute_approved_action` |

Permission to draft never implies permission to publish, send, pay, delete, or change external systems.

Current LocalOS review-reply flow is draft/manual for map providers. `reviews.publish_external` is a `planned_gap` unless a provider write integration is explicitly implemented, tested, approved, and documented. Operator should present copy/manual-publication actions instead of claiming it published replies to maps.

Current Operator review intake uses these tool boundaries:

| Tool/capability | Operator action class | Risk class | Side effect | Billing |
| --- | --- | --- | --- | --- |
| `operator.manual_review_intake` | `write_internal` plus `paid_compute` when reply generation is requested | `write_internal` | saves a manually provided review with `source = manual_chat` | no charge by itself |
| `reviews.reply_draft.generate` | `paid_compute` | `draft_only` | saves a LocalOS reply draft; no external publication | charges credits through reservation and finalization |
| `reviews.reply_draft.generate_bulk` | `paid_compute` | `draft_only` plus `write_internal` | saves LocalOS reply drafts for stored unanswered reviews; no external publication | charges credits per successfully created draft |
| `news.draft.generate` | `paid_compute` | `draft_only` plus `write_internal` | saves a LocalOS news draft in `usernews`; no external publication | charges credits after successful draft generation |
| `social_post.draft.generate` | `paid_compute` | `draft_only` plus `write_internal` | saves a LocalOS post draft; no external publication | charges credits after successful draft generation |
| `services.optimization_suggest` | `paid_compute` | `draft_only` plus `write_internal` | saves proposed names/descriptions in service-regeneration job tables; does not update active services | charges credits per saved suggestion |
| `services.optimization_apply` | `approval_required` | `write_internal` | applies saved service suggestions to `userservices` after explicit confirmation; no external publication | no extra charge after suggestion generation |
| `services.compression_draft` | `free_cached` or `paid_compute` when AI grouping is used | `draft_only` plus `write_internal` | creates/updates a LocalOS grouping draft; does not change active services | no charge unless AI grouping/generation is used |
| `services.compression_apply` | `approval_required` | `write_internal` | creates confirmed combined LocalOS services and softly archives original rows; no external publication | no extra charge after draft generation |
| `services.compression_rollback` | `approval_required` | `write_internal` | hides created combined services and restores archived source rows in LocalOS | no external provider write |
| `operator.content_history.read` | `free_cached` | `read_only` | lists LocalOS review reply drafts, news drafts, social post drafts, service suggestions, and applied service changes by type | no charge |
| `reviews.reply_draft.copy` | `manual_external` | `read_only` | user copies text manually | no extra charge after draft generation |
| `reviews.reply_draft.mark_manual_published` | `manual_external` | `write_internal` | marks the LocalOS draft as published manually after the user copied and pasted it outside LocalOS | no extra charge after draft generation |
| `operator.inbox.read` | `free_cached` | `read_only` | returns a scoped queue of review/content/partnership actions and UI helpers | no charge |
| `maps.refresh.enqueue_apify_yandex` | `paid_external` | `write_internal` | reserves credits and enqueues a read-only `parsequeue` job; no external provider writes | actual Apify provider cost is settled by the worker when available |
| `maps.refresh.jobs.read` | `free_cached` | `read_only` | lists recent scoped refresh jobs, statuses, saved new-review snippets, and billing state in web Operator or Telegram | no extra charge |
| `maps.refresh.reliability.read` | `free_cached` | `read_only` | explains existing parsequeue reliability state: retrying, captcha, failed, warnings, reason code, and next step; no retry execution | no charge |
| `maps.refresh.retry_request` | `paid_external` | `write_internal` | creates a new paid read-only refresh job from a failed/captcha/warning job URL; does not mutate the old job and does not write to map providers | reserves credits through the same map refresh boundary; actual provider cost is settled by worker when available |
| `maps.refresh.telegram_followup` | `paid_external` result notification | `communication` | sends one owner-bot Telegram summary after a completed paid refresh; idempotency is stored on reservation metadata; no customer messages or provider writes | no extra charge beyond the refresh itself |

The manual review flow is available from web Operator chat and Telegram, but both surfaces must route through the same backend service and credit checks. Publication to Yandex, Google, 2GIS, or other maps remains manual unless a provider write flow is later implemented and approved.

Web UI actions for this flow are presentation helpers, not new execution tools:

- `copy_reply`: copies the saved/generated draft text for manual external publication;
- `copy_news`: copies the saved news draft text for manual external publication;
- `copy_social_post`: copies the saved social post draft text for manual external publication;
- `open_reviews`: opens the LocalOS reviews tab where the saved review and draft can be inspected;
- `open_news_drafts`: opens the LocalOS content area where the saved news draft can be inspected;
- `open_billing`: opens billing when the paid compute preflight blocks on insufficient credits.

## Schema Rules

Schemas should:

- require all mandatory fields;
- reject unknown properties where supported;
- use enums for constrained choices;
- prefer stable IDs over freeform names;
- validate locally before execution;
- return structured errors.

Schema adherence improves reliability, but it is not a security boundary by itself. Permission checks still run after schema validation.

## Retry Rules

Safe to retry:

- read-only calls;
- idempotent search;
- transient network failures;
- model correction after schema validation failure.

Do not automatically retry:

- external sends;
- payments;
- destructive actions;
- credential changes;
- non-idempotent writes.

For writes, require idempotency keys and record the outcome.

## Current Registry Seeds

Initial LocalOS registry entries should be derived from:

- [Capabilities](capabilities.md);
- [Approval policy](approval-policy.md);
- [Agent API security model](security-model.md);
- [Agent Registry v1](../AGENT_REGISTRY_V1.md);
- [LocalOS Operator](localos-operator.md);
- `/localos-agent-policy.json`.
- `/localos-agent-tools.json`.
- `/api/agent-api/openapi.json`.
- `/localos-agent-openapi.json` as a root-level static alias.

## Public Manifest

`/localos-agent-tools.json` is a machine-readable capability map for agents.
It is deliberately narrower than a public MCP server:

- it lists safe read/draft/request tools;
- it labels status and risk class;
- it points to scopes and approval policy;
- it marks unavailable capabilities as gaps.

It must not be described as a live MCP endpoint until a server, auth flow, request schemas, tests and deployment checks exist.

`/api/agent-api/openapi.json` is the minimal machine-readable HTTP contract for the implemented Agent API security endpoints only. It covers policy, clients, onboarding self-test, approvals, ledger, discovery and Telegram binding lookup, but not product-wide automation APIs. `/localos-agent-openapi.json` remains as a static discovery alias.

## Checklist For Adding A Tool

- Purpose and non-purpose are explicit.
- Input and output schemas are documented.
- Risk class is assigned.
- Side effects are declared.
- Approval policy is clear.
- Errors are structured.
- Result size has a limit.
- Timeout is defined.
- Retry behavior is safe.
- Audit event is recorded.
- Tool is hidden unless relevant to the current task and actor.
