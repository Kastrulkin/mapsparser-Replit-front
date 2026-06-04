# Evidence Bundle: partnership_letters_v1

## Summary
- Overall status: PASS
- Last updated: 2026-06-04T14:07:05+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/api/admin_prospecting.py` accepts `letter_type` values `first_note` and `commercial_offer`.
  - `commercial_offer` uses `partners.draft_commercial_offer(_fallback)` and `commercial_offer_v1`.
- Gaps:
  - GigaChat pair generation is not enabled in this iteration.

### AC2
- Status: PASS
- Proof:
  - Draft metadata stores `letter_type`, `our_business_type`, `partner_business_type`, `pair_pattern`, `package_idea`, `template_policy`, `ai_used`, `cache_hit`, prompt key/version.

### AC3
- Status: PASS
- Proof:
  - Draft approval now merges and preserves existing `learning_note_json` instead of replacing it with only `intent`.
  - Accepted learning events include preserved metadata and edit flag.

### AC4
- Status: PASS
- Proof:
  - Single and bulk lead updates to `pipeline_status=converted` write `ailearningevents` with `event_type=outcome`, `outcome=partner`.

### AC5
- Status: PASS
- Proof:
  - Frontend bulk bar includes `Подготовить КП`.
  - Live frontend bundle contains the new marker.

### AC6
- Status: PASS
- Proof:
  - Backup: `/tmp/localos_backups/partnership_letters_backup_20260604170309.sql`.
  - Mass generation result: `{'success': True, 'leads': 97, 'first_inserted': 0, 'first_updated': 97, 'commercial_inserted': 11, 'commercial_updated': 0, 'commercial_targets': 11}`.
  - Fix pass result: `{'success': True, 'commercial_targets': 11, 'commercial_drafts_updated': 11}`.
  - SQL check: active partnership leads `97`, first-note drafts `98` total including one legacy rejected/no-letter-type draft, commercial-offer drafts `11`.

## Commands run
- `python3 -m py_compile src/api/admin_prospecting.py`
- `PATH=... node_modules/.bin/vite build`
- `PATH=... node_modules/.bin/tsc -p tsconfig.app.json --noEmit`
- `rsync` backend and `frontend/dist`, `docker compose restart app`
- `docker compose ps`
- `docker compose logs --since 5m app`
- `docker compose logs --since 5m worker`
- `curl -I --max-time 15 http://localhost:8000`
- Production SQL count checks for partnership leads/drafts.

## Raw artifacts
- .agent/tasks/partnership_letters_v1/raw/build.txt
- .agent/tasks/partnership_letters_v1/raw/test-unit.txt
- .agent/tasks/partnership_letters_v1/raw/test-integration.txt
- .agent/tasks/partnership_letters_v1/raw/lint.txt
- .agent/tasks/partnership_letters_v1/raw/screenshot-1.png

## Known gaps
- TypeScript check still fails on two pre-existing unrelated issues:
  - `src/components/CardAuditPanel.tsx(570,25)` `help` prop mismatch.
  - `src/pages/dashboard/OperatorPage.tsx(179,41)` `result_summary` union mismatch.
- No dedicated GigaChat pair-pattern generation yet; current implementation is deterministic and metadata-ready.
