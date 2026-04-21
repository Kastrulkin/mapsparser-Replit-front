# Evidence Bundle: repo-stability-20260420

## Summary
- Overall status: PASS
- Last updated: 2026-04-21T14:05:45Z

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - critical runtime files `src/core/card_audit_policy.py`, `src/core/card_automation.py`, `src/core/map_url_normalizer.py` are now in tracked state
  - critical alembic revisions `20260416_001`, `20260417_001`, `20260420_001` are now in tracked state
  - `scripts/check_backend_source_of_truth.sh` returns `OK: backend runtime source-of-truth is clean`
- Gaps:
  - server git working tree still contains additional unrelated drift outside this task slice

### AC2
- Status: PASS
- Proof:
  - `frontend/src/components/dashboard/DashboardSections.tsx` now contains `DashboardTabContent` as the extracted tab-content router
  - `frontend/src/pages/Dashboard.tsx` now delegates tab rendering to `DashboardTabContent` instead of holding the inline `activeTab === ...` tree
  - `frontend/src/components/prospecting/OutreachDetailPanes.tsx` now reuses `DetailWarningActions` and `DetailStatusCards`
  - `frontend/src/pages/dashboard/AdminPage.tsx` memoizes filtered users instead of recalculating search filtering inside the render branch
- Gaps:
  - `Dashboard.tsx` still contains substantial action handlers and data-loading logic; only the next orchestration layer was extracted here

### AC3
- Status: PASS
- Proof:
  - `cd frontend && npm run build` succeeded and produced `dist/assets/index-DYspwMqI.js`
  - `bash scripts/deploy_frontend_dist.sh` completed and verified `docker compose ps`, app logs, `curl -I http://localhost:8000`, and targeted frontend checks
  - deploy verification confirmed live HTML references `/assets/index-DYspwMqI.js` and `/assets/index-DS0mDI9T.css`
  - deploy verification recorded `HTTP/1.1 200 OK` for `http://localhost:8000`
- Gaps:
  - deploy log contains expected `tar: file changed as we read it` warnings because old assets are intentionally retained for open tabs

## Commands run
- `scripts/check_backend_source_of_truth.sh`
- `cd frontend && ./node_modules/.bin/eslint src/pages/Dashboard.tsx src/components/dashboard/DashboardSections.tsx src/components/prospecting/OutreachDetailPanes.tsx src/pages/dashboard/AdminPage.tsx`
- `cd frontend && npm run build`
- `python3 -m py_compile src/main.py src/worker.py src/stripe_integration.py src/api/admin_prospecting.py`
- `bash scripts/deploy_frontend_dist.sh`
- `scripts/proof_loop.sh validate repo-stability-20260420`

## Raw artifacts
- `.agent/tasks/repo-stability-20260420/raw/build.txt`
- `.agent/tasks/repo-stability-20260420/raw/lint.txt`
- `.agent/tasks/repo-stability-20260420/raw/test-unit.txt`
- `.agent/tasks/repo-stability-20260420/raw/test-integration.txt`
- `.agent/tasks/repo-stability-20260420/raw/screenshot-1.png`

## Known gaps
- The repository outside this task scope is still broadly dirty; this pass intentionally isolates the critical runtime/admin stability slice.
- Server-side git/source-of-truth cleanup still needs a follow-up pass after these tracked files are committed and propagated through the canonical update path.
