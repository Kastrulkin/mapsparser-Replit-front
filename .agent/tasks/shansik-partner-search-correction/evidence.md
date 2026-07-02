# Evidence Bundle: shansik-partner-search-correction

## Summary
- Overall status: PASS
- Last updated: 2026-07-02T11:55:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Mistaken candidates for Shansik Engelsa 154 were removed: `raw/delete_mistaken_engelsa_leads.json` shows `deleted_count: 17`.
  - Partner search was run for the four non-Engelsa locations. Final production API counts in `raw/final_counts_after_self_cleanup.json`:
    - Engelsa 154: 0 leads.
    - Pushkin Radischeva 22: 47 leads.
    - Pushkin Cerkovnaya 27: 36 leads.
    - Novoizmaylovskiy 101: 33 leads.
    - Pushkin Kedrinskaya 12: 39 leads.
    - Total non-Engelsa: 155 leads.
  - Own-brand/self candidate was cleaned up: `raw/delete_self_leads.json` shows one self lead removed and `remaining_self_names: []`.
  - Backend search now skips candidates that look like the same business/brand at the same address, preventing self-import on future searches.
  - Production health/list endpoints returned HTTP 200 for all five locations in `raw/final_counts_after_self_cleanup.json`.
- Gaps:
  - A few individual Yandex geo queries timed out during search, but each required non-Engelsa location has imported candidates from Yandex Maps. Timeout artifacts are preserved under `raw/geo_*.json`.

## Commands run
- `venv/bin/python -m py_compile src/api/admin_prospecting.py`
- `venv/bin/python -m pytest tests/test_partnership_leads_routes_contract.py tests/test_admin_prospecting_audit_payload.py`
- `git diff --check -- src/api/admin_prospecting.py`
- `scripts/deploy_backend_src.sh`
- Production API verification for `/api/partnership/leads` and `/api/partnership/health` across all five Shansik locations.

## Raw artifacts
- .agent/tasks/shansik-partner-search-correction/raw/build.txt
- .agent/tasks/shansik-partner-search-correction/raw/test-unit.txt
- .agent/tasks/shansik-partner-search-correction/raw/test-integration.txt
- .agent/tasks/shansik-partner-search-correction/raw/lint.txt
- .agent/tasks/shansik-partner-search-correction/raw/delete_mistaken_engelsa_leads.json
- .agent/tasks/shansik-partner-search-correction/raw/delete_self_leads.json
- .agent/tasks/shansik-partner-search-correction/raw/final_counts_after_self_cleanup.json
- .agent/tasks/shansik-partner-search-correction/raw/screenshot-1.png

## Known gaps
- No blocking gaps. Some provider timeouts remain recorded for visibility.
