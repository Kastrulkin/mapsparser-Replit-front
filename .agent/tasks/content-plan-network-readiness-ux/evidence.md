# Evidence Bundle: content-plan-network-readiness-ux

## Summary
- Overall status: PASS
- Last updated: 2026-05-04T06:12:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `ContentPlanTab` now derives `networkHasSearchPlanFoundation` when network scope has map links and SEO keywords and only `services` is missing.
  - The incomplete-data banner switches from amber warning to emerald "Сеть готова для поискового контент-плана" for that case.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Network copy now says "Нет меню, товаров или услуг" and CTA says "Добавить меню/услуги".
  - Data quality summary says the search foundation is ready and services/products are the next specificity layer.
- Gaps:
  - None.

### AC3
- Status: PASS
- Proof:
  - `cd frontend && npm run build` completed successfully.
  - `30 passed in 0.18s`.
  - `git diff --check` completed successfully.
- Gaps:
  - Existing Browserslist and Rollup third-party warnings remain unrelated to this change.

### AC4
- Status: PASS
- Proof:
  - `scripts/deploy_frontend_dist.sh --build` deployed `frontend/dist` and `public-dist` to production.
  - Production `/` returned `200 OK`.
  - Live chunk `/assets/NewsGenerator-DffR2VUO.js` contains `Сеть готова для поискового контент-плана`, `Для сети уже есть поисковый фундамент`, `Нет меню, товаров или услуг`, `Добавить меню/услуги`.
- Gaps:
  - No write-action UI smoke was performed; this change is display-only.

## Commands run
- `git diff --check`
- `cd frontend && npm run build`
- `source venv/bin/activate && python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`
- `scripts/deploy_frontend_dist.sh --build`
- `curl -ksS https://localos.pro/assets/NewsGenerator-DffR2VUO.js | rg -o ...`

## Raw artifacts
- .agent/tasks/content-plan-network-readiness-ux/raw/build.txt
- .agent/tasks/content-plan-network-readiness-ux/raw/test-unit.txt
- .agent/tasks/content-plan-network-readiness-ux/raw/test-integration.txt
- .agent/tasks/content-plan-network-readiness-ux/raw/lint.txt
- .agent/tasks/content-plan-network-readiness-ux/raw/screenshot-1.png

## Known gaps
- Production services for Lukoil are still not populated; this task only improves the readiness UX around that gap.
