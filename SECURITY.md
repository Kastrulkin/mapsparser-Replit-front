# LocalOS security contract

This document describes required boundaries, not a claim that all controls have passed audit. Current evidence and unresolved findings: `docs/production-readiness/02-audit-backlog.md`. Product and architecture sources: `README.md`, `PRODUCT.md`, `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`, `docs/agents/tool-registry.md`.

## Assets and untrusted inputs

Protect session/password material, provider credentials, business/network membership, finances, private knowledge, customer/partner contacts, uploads, messages, approvals, billing and audit history. Treat all HTTP bodies/IDs/query strings, webhook payloads, uploaded files, retrieved websites, provider responses and model output as untrusted. Never put live secrets or customer records into fixtures, reports or demo data.

## Required invariants

- Authentication must reject expired, missing and revoked/inactive sessions before business effects. Diagnostic account-status responses must not expose private payloads.
- Object access must verify the requested business/network scope server-side. Membership is not automatically permission for every mutation; role-specific semantics must be tested. Foreign IDs must not disclose or mutate another tenant's objects.
- Provider callbacks authenticate before parsing/processing side effects. Source signatures do not replace replay protection or action approval.
- AI prompts and retrieved content cannot grant tools, change tenant identity, bypass budget/policy or approve dangerous actions. Tool execution enforces scope and human approval outside model text.
- Publishing, external sends, payments, access changes, destructive/bulk mutations and actions for a business in third-party systems require the documented approval boundary and durable audit.
- Use parameterized SQL, bounded requests/uploads, timeouts and validated outbound destinations. Retries of non-idempotent effects must reconcile uncertain provider outcomes before resending.
- Secrets stay in protected runtime configuration; redact credentials, tokens, private message bodies and personal data from ordinary logs/errors.
- PostgreSQL is the runtime source of truth. Production schema changes use Alembic with backup and explicit approval. Never test destructive paths on production.

## Safe testing and scans

Use synthetic tenant-separated fixtures, disposable PostgreSQL and mocked/stubbed providers. No real emails, messages, payments, key rotations or production data mutations during a local audit. Test both allowed controls and denials before side effects, plus concurrent/replayed/stale inputs. Do not weaken tests or hide confirmed failures to obtain green.

Scan tracked current content and Git history separately; inspect dependency locks/images and redacted runtime logs. Generated dependencies/build artifacts may be excluded from source scanning only with documented scope and separate dependency/image coverage. Do not allowlist a secret finding without checking it; absence from a scan is not proof that every secret is absent. Store sensitive raw findings outside tracked artifacts with restricted access; report only location/classification, never the secret value.

## Severity and disclosure

P0: demonstrated critical authorization compromise, cross-tenant exposure, broad compromise/data loss or complete outage with supported reachability. P1: serious scoped vulnerability, key-flow failure or material integrity/reliability risk. Track evidence, impact, likelihood and fix risk; distinguish candidates from reproductions. Report suspected vulnerabilities privately to the repository owner through the existing private project channel; do not publish exploit details or credentials in public issues. No unverified disclosure email or response guarantee is advertised.

## Current audit limits

Inactive-session denial, authenticated webhook ingress, Telegram/WhatsApp replay admission and Telegram log redaction fixes are locally tested, independently reviewed and committed, but not deployed by this audit. Provider rebind is a rollout prerequisite. Scoped Operator, service and content mutation role tests pass; the full platform tenant/role matrix remains incomplete. Historical privileged credential exposure is confirmed offline, with revocation status unknown; no live key testing or rotation has been performed. Current-image/log/resolved-dependency scans remain incomplete. The synthetic PostgreSQL 16 restore rehearsal verified data and full schema, including indexes, triggers, views, routines, sequences, owners and grants; it does not prove production recovery. Current272794a4 native real-API browser verification passes117scenarios; historical120includes three compiled-runner cases on the earlierf0ccimage. Final current immutable-image execution remains unverified. See the maintained progress file before relying on any readiness claim.
