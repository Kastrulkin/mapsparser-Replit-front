# Evidence Bundle: beauty-service-keyword-scoring-stage3-20260505

## Summary
- Overall status: PASS
- Last updated: 2026-05-05T18:58:00+03:00

## Acceptance criteria evidence

### AC1: UI shows keyword match levels
- Status: PASS
- Proof:
  - `CardServicesTable` now renders keyword badges with labels `точное`, `словоформа`, `близкое`, plus missing/no-keywords states.

### AC2: Beauty synonym dictionary expanded
- Status: PASS
- Proof:
  - Added groups for permanent/tattoo/powder brows, manicure/nails/covering, pedicure/feet, botox/botulinotherapy, cleaning/care/peeling, lamination/long-term styling.
  - Dictionary exists in frontend helper and backend scoring module.

### AC3: Scoring is more useful
- Status: PASS
- Proof:
  - `KeywordScore` includes total/found/missing, exact/normalized/close counts, missing list, added list, weak list, and coverage.

### AC4: Backend keyword scoring added
- Status: PASS
- Proof:
  - Added `src/core/service_keyword_scoring.py`.
  - `/api/services/optimize` normalization adds `seo_keyword_score` to service suggestions.

### AC5: Organika regression cases
- Status: PASS
- Proof:
  - `tests/test_service_keyword_scoring.py` contains 20 Organika-style beauty cases covering brows, lashes, injections, hair, children, manicure, and pedicure.

### AC6: Stage 4 bad-only bulk regeneration
- Status: PASS
- Proof:
  - `optimizeAllServices` now filters target services through `serviceNeedsRegeneration`.
  - Services with empty suggestions, fallback, guardrail reasons, unchanged drafts, fallback text, or missing SEO keywords are regenerated; good suggestions are skipped.

## Commands run
- `./venv/bin/python -m pytest -q tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py`
- `python3 -m py_compile src/core/service_keyword_scoring.py src/core/beauty_service_optimization.py src/main.py`
- `cd frontend && ./node_modules/.bin/sucrase-node scripts/test-card-services-logic.ts`
- `cd frontend && npm run build:all`
- `cd frontend && ./node_modules/.bin/tsc -p tsconfig.app.json --noEmit`
- `rg -n "\\bas\\b|as const" ...changed files...`
- Server backup: `/opt/seo-app/backups/beauty-keyword-scoring-stage3-20260505_184006`
- Server partial backend deploy: synced `src/main.py` and `src/core/service_keyword_scoring.py`, restarted `app worker`
- `scripts/deploy_frontend_dist.sh`
- Server smoke: backend scoring returns `close` for `ламинирование` / `Долговременная укладка`
- Server frontend bundle grep: `Найдено`, `словоформа`, `близкое`, `потеряно`
- Server runtime checks: `docker compose ps`, `curl -I http://localhost:8000`

## Known gaps
- Full frontend TypeScript check still fails on pre-existing unrelated errors in modules outside this task. Vite production build passes.
