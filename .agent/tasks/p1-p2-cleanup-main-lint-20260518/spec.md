# Task Spec: p1-p2-cleanup-main-lint-20260518

## Metadata
- Task ID: p1-p2-cleanup-main-lint-20260518
- Created: 2026-05-18T19:41:00+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Autonomous P1/P2 cleanup: clean old untracked artifacts and git hygiene, start safe main.py decomposition by extracting report routes to a blueprint without behavior changes, and add a small backend lint baseline.

## Acceptance criteria
- AC1: Old untracked `.agent/tasks/...` directories and `tmp_docx_work/` are removed while the current proof bundle remains.
- AC2: Git hygiene prevents `tmp_docx_work/` from returning as untracked noise.
- AC3: Legacy report routes are extracted from `src/main.py` into a blueprint without changing public URLs.
- AC4: A focused backend lint baseline exists for syntax, route ownership, and runtime SQLite placeholder regressions.
- AC5: Local checks and live runtime smoke pass after deployment of the backend slice.

## Constraints
- Do not remove tracked proof bundles.
- Keep route behavior and URLs unchanged.
- Do not refactor unrelated `main.py` areas.
- Server commands must run from `/opt/seo-app`.

## Non-goals
- Do not complete full `main.py` decomposition.
- Do not introduce broad style enforcement across the full repository.
- Do not alter production data.

## Verification plan
- Build: `python3 -m py_compile src/main.py src/api/reports_api.py tests/test_reports_api_routes.py tests/test_security_runtime_config.py`.
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_reports_api_routes.py tests/test_security_runtime_config.py tests/test_query_adapter.py`.
- Integration tests: import `main` and verify report route endpoint ownership.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: deploy backend slice, restart `app worker`, run live route and runtime smoke.
