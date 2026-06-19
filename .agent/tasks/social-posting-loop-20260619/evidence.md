# Evidence Bundle: social-posting-loop-20260619

## Summary
- Overall status: PASS
- Last updated: 2026-06-19T10:18:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/services/social_post_service.py` implements `_publish_vk_post` via `https://api.vk.com/method/wall.post`.
  - Missing VK account/token/group becomes `needs_manual_publish` with provider status metadata.
  - `tests/test_social_post_service.py` covers VK post URL formatting.
- Gaps:
  - Requires real encrypted VK account binding with wall.post permission for live publish.

### AC2
- Status: PASS
- Proof:
  - `src/services/social_post_service.py` implements `_publish_google_business_post` using `GoogleBusinessSyncWorker` behind lazy import.
  - Missing Google dependency/account/failed publish becomes recoverable manual status, not import failure.
- Gaps:
  - Live Google publish depends on OAuth/API approval and connected account.

### AC3
- Status: PASS
- Proof:
  - `record_social_post_attribution_event` now calls `_upsert_manual_attribution_metrics`.
  - `collect_social_post_metrics` folds attribution totals into daily `social_post_metrics`.
- Gaps:
  - API provider metric snapshots beyond manual attribution remain future work.

### AC4
- Status: PASS
- Proof:
  - `ContentPlanTab.tsx` adds channel filter `all/social/maps`.
  - Published social post cards include "Была заявка" and "Было обращение" actions.
  - Yandex/2GIS cards show supervised task instruction and automation task id when present.
- Gaps:
  - Full browser automation launch remains intentionally deferred behind OpenClaw capability verification.

### AC5
- Status: PASS
- Proof:
  - Existing `publish_social_post` approval guard remains in place.
  - Tests include existing safety coverage for social API routes/rate limit and service behavior.
- Gaps:
  - Real provider happy paths still need seeded staging credentials.

## Commands run
- `./venv/bin/python -m py_compile src/services/social_post_service.py src/api/social_posts_api.py src/api/external_accounts_api.py`
- `./venv/bin/python -m pytest -q tests/test_social_post_service.py tests/test_social_posts_api.py tests/test_external_accounts_routes_contract.py` -> 12 passed
- `npm run build` in `frontend` -> passed

## Raw artifacts
- .agent/tasks/social-posting-loop-20260619/raw/build.txt
- .agent/tasks/social-posting-loop-20260619/raw/test-unit.txt
- .agent/tasks/social-posting-loop-20260619/raw/test-integration.txt
- .agent/tasks/social-posting-loop-20260619/raw/lint.txt
- .agent/tasks/social-posting-loop-20260619/raw/screenshot-1.png

## Known gaps
- Meta Graph real publish remains blocked until permissions/account binding are verified.
- Yandex/2GIS browser automation remains supervised/manual; no final external publish click is automated.
- Live VK/Google publish requires real connected credentials and provider permissions.
