# Evidence Bundle: beauty-service-seo-keyword-stage2-20260505

## Summary
- Overall status: PASS
- Last updated: 2026-05-05T17:42:00+03:00

## Acceptance criteria evidence

### AC1: Frontend keyword matching has exact, normalized, close levels
- Status: PASS
- Proof:
  - Added `KeywordMatchLevel` and `getKeywordMatches` in `frontend/src/components/dashboard/cardServicesLogic.ts`.
  - Matching now returns `exact`, `normalized`, or `close` for detected service SEO keywords.

### AC2: Obvious Russian wordforms and close beauty synonyms are matched
- Status: PASS
- Proof:
  - Added normalization/tokenization for Russian service keywords.
  - Added beauty close groups for examples such as "восковая депиляция" vs "ваксинг", "брови" vs "бровей", "ресницы" vs "ресниц".
  - Targeted frontend regression script passes.

### AC3: Guardrails reject unconfirmed medical claims and added zones
- Status: PASS
- Proof:
  - Added extra risky claim markers and body zone markers in `src/core/beauty_service_optimization.py`.
  - Added `_added_unconfirmed_medical_claim`.
  - Regression covers "Плазмотерапия - 2 пробирки" being incorrectly expanded to zones and medical promises.

### AC4: Scope is limited and production cleanup is targeted/backed up
- Status: PASS
- Proof:
  - Changed only frontend service helper, frontend targeted test script, beauty optimization core, beauty tests, and proof files.
  - No schema migration was added.
  - After deploy, 4 bad generated service suggestions were backed up and cleared only in `optimized_name` / `optimized_description`.
  - Cleanup backup: `/opt/seo-app/backups/clear-bad-service-optimizations-stage2-20260505_173332/userservices_bad_optimizations.csv`.

### AC5: Regression checks cover the intended behavior
- Status: PASS
- Proof:
  - Backend test suite passes: `10 passed`.
  - Frontend targeted keyword script passes.
  - Python compile check passes.

## Commands run
- `./venv/bin/python -m pytest -q tests/test_beauty_service_optimization.py`
- `python3 -m py_compile src/core/beauty_service_optimization.py src/core/service_optimization_verticals.py src/main.py`
- `cd frontend && ./node_modules/.bin/sucrase-node scripts/test-card-services-logic.ts`
- `cd frontend && ./node_modules/.bin/tsc -p tsconfig.app.json --noEmit`
- `rg -n "\\bas\\b|as const" frontend/src/components/dashboard/cardServicesLogic.ts frontend/scripts/test-card-services-logic.ts src/core/beauty_service_optimization.py tests/test_beauty_service_optimization.py`
- `cd frontend && npm run build:all`
- `scripts/deploy_frontend_dist.sh`
- Server: `docker compose restart app worker`
- Server: `docker compose ps`
- Server: `docker compose logs --since 2m app`
- Server: `curl -I http://localhost:8000`
- Server: targeted backend guardrail smoke for "Плазмотерапия - 2 пробирки"
- Server: frontend bundle dictionary grep for "восковая депиляция" and "афрокудри"
- Server: targeted cleanup of 4 bad generated service suggestions with CSV backup

## Known gaps
- Full frontend TypeScript check still fails because of pre-existing unrelated errors in other modules such as i18n, prospecting, network dashboard, and admin audit editor. No errors from the changed service keyword helper were observed in the targeted regression.
