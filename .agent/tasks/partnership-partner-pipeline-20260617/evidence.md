# Evidence Bundle: partnership-partner-pipeline-20260617

## Summary
- Overall status: IMPLEMENTED_LOCAL
- Last updated: 2026-06-17T12:00:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added Alembic migration `20260617_add_partnership_partner_cards.py`.
  - Added runtime helper `_ensure_partnership_partner_cards_table`.
  - Partner card fields cover source company, Yandex URL/match state/candidates, parse business, audit URL/slug/status/error, linked lead, raw payload.
- Gaps:
  - Frontend card UI is not implemented in this phase.

### AC2
- Status: PASS
- Proof:
  - `_normalize_partner_kind` and `_is_residential_partner_card` skip residential complexes.
  - Tests cover explicit ЖК detection and avoid false positive on `Дом красоты`.
- Gaps:
  - Classification is heuristic unless caller sends `partner_kind=residential_complex`.

### AC3
- Status: PASS
- Proof:
  - `_sync_partner_card_to_lead` reuses `_insert_partnership_lead_if_new`.
  - Lead metadata includes `partner_source_company_id`, `partner_source_company_name`, `partner_source_partner_id`.
  - Status remains candidate-like: `status=new`, `pipeline_status=unprocessed`, `partnership_stage=imported`.
- Gaps:
  - Not exercised against a live database in this run.

### AC4
- Status: PASS
- Proof:
  - `POST /api/partnership/partners/<partner_id>/parse` uses `_process_partner_card_parse`.
  - Reuses `_ensure_parse_business_for_partnership_lead` and `_enqueue_parse_task_for_business`.
- Gaps:
  - Parse worker execution was not run locally.

### AC5
- Status: PASS
- Proof:
  - `POST /api/partnership/partners/<partner_id>/audit` uses `_process_partner_card_audit`.
  - Public audit is stored in `adminprospectingleadpublicoffers`.
  - Partner card stores `audit_public_url`, `audit_slug`, `audit_generated_at`.
  - Page JSON includes `signup_context.source=partnership_partner`, `partner_id`, `source_company_name`, `maps_url`.
- Gaps:
  - Public page click-through was not browser-tested in this phase.

### AC6
- Status: PASS
- Proof:
  - `POST /api/partnership/partners/bulk-process` returns summary counters for total/skipped/found/ambiguous/not_found/synced/parse/audit/failed.
- Gaps:
  - Provider-backed Yandex search depends on configured `APIFY_TOKEN`.

## Commands run
- `python3 -m py_compile src/api/admin_prospecting.py`
- `python3 -m py_compile alembic_migrations/versions/20260617_add_partnership_partner_cards.py`
- `python3 -m py_compile src/api/admin_prospecting.py alembic_migrations/versions/20260617_add_partnership_partner_cards.py`
- `python3 -m pytest -q tests/test_partnership_partner_cards.py`
- `python3 -m pytest -q tests/test_admin_prospecting_audit_payload.py`
- `python3 -m pytest -q tests/test_partnership_partner_cards.py tests/test_admin_prospecting_audit_payload.py tests/test_prospecting_service_normalize.py`

## Raw artifacts
- .agent/tasks/partnership-partner-pipeline-20260617/raw/build.txt
- .agent/tasks/partnership-partner-pipeline-20260617/raw/test-unit.txt
- .agent/tasks/partnership-partner-pipeline-20260617/raw/test-integration.txt
- .agent/tasks/partnership-partner-pipeline-20260617/raw/lint.txt
- .agent/tasks/partnership-partner-pipeline-20260617/raw/screenshot-1.png

## Known gaps
- Frontend UI for partner-card pipeline is still pending.
- No production data was changed; actual partner enrichment for Весёлая расчёска, Органика, Новамед still requires an approved run.
- Yandex live matching depends on provider credentials and network availability.
