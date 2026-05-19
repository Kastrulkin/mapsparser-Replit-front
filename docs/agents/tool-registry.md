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
| `reviews.reply_draft` | `reviews.google_publish` |
| `news.generate` | `content.publish_external` |
| `partnership.draft_offer` | `partnership.send_batch` |
| `finance.import_preview` | `finance.import_apply` |
| `agent.approval_request` | `execute_approved_action` |

Permission to draft never implies permission to publish, send, pay, delete, or change external systems.

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
- `/localos-agent-policy.json`.
- `/localos-agent-tools.json`.

## Public Manifest

`/localos-agent-tools.json` is a machine-readable capability map for agents.
It is deliberately narrower than a public MCP server:

- it lists safe read/draft/request tools;
- it labels status and risk class;
- it points to scopes and approval policy;
- it marks unavailable capabilities as gaps.

It must not be described as a live MCP endpoint until a server, auth flow, request schemas, tests and deployment checks exist.

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
