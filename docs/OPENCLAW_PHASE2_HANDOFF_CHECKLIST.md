# OpenClaw Phase 2 Handoff Checklist

## Scope

Phase 2 closes production operations for LocalOS ↔ OpenClaw:
- health/trend snapshots
- callback outbox delivery + retries + DLQ
- billing reconciliation alerts
- reproducible deploy + acceptance scripts
- support recovery flow

## Runtime Prerequisites

Run all server commands from:

```bash
cd /opt/seo-app
```

Required env on LocalOS (`.env`):
- `OPENCLAW_LOCALOS_TOKEN`
- `OPENCLAW_CALLBACK_SIGNING_SECRET`
- `OPENCLAW_CALLBACK_DISPATCH_ENABLED=true`

Required OpenClaw receiver state:
- callback endpoint reachable from LocalOS runtime
- identical `OPENCLAW_CALLBACK_SIGNING_SECRET`
- replay/dedupe enabled on OpenClaw side

## Acceptance Gate

Mandatory check for release candidate:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/acceptance_openclaw_phase2.sh
```

Expected:
- `HEAD /` -> `200`
- capabilities smoke -> pass
- outbox smoke -> pass
- reconciliation smoke -> pass
- outbox alerts check -> pass

## CI Gate

Canonical pipeline script:

```bash
./scripts/ci_gate_openclaw_phase2.sh
```

Legacy alias (kept for compatibility):

```bash
./scripts/ci_gate_openclaw_phase1.sh
```

## One-Click Ops Recovery

From UI (`Настройки -> Integrations -> Связь ИИ-агентов с системой`):
- button: `Восстановить доставку`
- backend flow:
  1) `POST /api/capabilities/callbacks/outbox/replay` (`include_retry=true`)
  2) `POST /api/capabilities/callbacks/dispatch` (tenant-scoped)
  3) refresh health + trend + billing reconciliation

From CLI:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/openclaw_ops_smoke_recover.sh
```

## Incident Triage (Support)

1. Health degraded in UI
- open Integration panel and inspect:
  - `Retry`, `DLQ`, `Stuck`, `Success %`
  - `Billing issues`

2. Run diagnose bundle:

```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ./scripts/diagnose_openclaw_integration.sh
```

Optional deep action diagnostics:
```bash
OPENCLAW_TOKEN='<token>' TENANT_ID='<business_id>' ACTION_ID='<action_id>' ./scripts/diagnose_openclaw_integration.sh
```

3. If callback delivery stalled:
- replay `dlq/retry` to pending
- dispatch outbox
- recheck metrics and trend

4. If reconcile reports issue:
- run `billing/reconcile` endpoint
- if needed run `scripts/repair_openclaw_missing_settle.py` (dry-run first)

## Ownership & Escalation

- LocalOS owner: capability API, ledger, outbox, alerts, UI integration.
- OpenClaw owner: signed callback receiver, dedupe/replay protection, metrics.
- Cross-team escalation:
  - signature mismatch
  - callback timeout/connectivity
  - persistent DLQ after replay+dispatch

## Done Criteria for Phase 2

- [x] Health/trend endpoints and history snapshots
- [x] Outbox metrics + alerts + replay/cleanup
- [x] Billing reconciliation endpoint + smoke
- [x] Acceptance script for one-shot release gate
- [x] UI integration block in Integrations tab
- [x] UI recovery action (replay + tenant-scoped dispatch)
- [x] Runbook and handoff docs updated
