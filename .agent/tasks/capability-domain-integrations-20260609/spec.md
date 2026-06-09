# Task Spec: capability-domain-integrations-20260609

## Metadata
- Task ID: capability-domain-integrations-20260609
- Created: 2026-06-09T13:33:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
Настоящие domain integrations за capability map: углубить `appointments.read`,
`communications.send_reminder`, `communications.send_offer`,
`reviews.reply.publish_request`, `services.optimize`, `billing.reserve` and
`billing.settle` without expanding autonomy. Approval, audit and limits remain
mandatory.

## Acceptance Criteria
- AC1: `appointments.read` reads real LocalOS appointment records with tenant filters and limits.
- AC2: communication send capabilities create internal LocalOS send requests with caps/consent metadata and do not dispatch externally.
- AC3: review publish requests create local review reply draft/request records and do not publish to providers.
- AC4: service optimization reads real services, stores local optimization requests, and does not apply changes.
- AC5: billing reserve/settle delegate to the existing credit reservation/finalization layer or the ActionOrchestrator ledger.
- AC6: architecture docs make the integration boundary explicit.
- AC7: new domain request tables are represented by Alembic, not only runtime guards.
- AC8: regression tests prove the safe domain integration behavior.

## Constraints
- No direct provider writes from capability handlers.
- No autonomous send/publish/apply/payment expansion.
- Risky effects remain behind ActionOrchestrator/OpenClaw approval, audit, idempotency, limits and ledger.
- No production data mutation during verification.
- Schema source of truth stays in Alembic migrations.

## Non-goals
- External WhatsApp/Telegram/provider send execution.
- Direct Yandex/Google/2GIS review publication.
- Direct service-card apply/publish.
- Production DB schema/data migration in this iteration.

## Verification Plan
- Build: `PYTHONPATH=src python3 -m py_compile src/services/agent_capability_handlers.py`
- Unit/integration: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Billing regression: `PYTHONPATH=src python3 -m pytest -q tests/test_operator_credit_reservation.py`
- Proof validation: `scripts/proof_loop.sh validate capability-domain-integrations-20260609`
