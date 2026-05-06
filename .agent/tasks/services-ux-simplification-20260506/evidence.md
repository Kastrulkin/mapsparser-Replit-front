# Evidence: services UX simplification P0/P1

## Scope
- P0 UX cleanup for /dashboard/card services tab.
- P0 list-detail replacement without API contract breakage.
- P0 frontend duplicate grouping.
- P1 safe Wordstat enrichment backend and endpoints without background auto-run.

## Checks
- python3 -m py_compile src/core/service_safe_wordstat.py src/core/service_keyword_enrichment.py src/core/service_duplicate_grouping.py src/api/services_api.py
- python3 -m pytest -q tests/test_service_safe_wordstat.py tests/test_service_keyword_scoring.py tests/test_service_problem_regeneration.py
- npm run build in frontend

## Results
- py_compile: passed
- pytest: 13 passed
- frontend build: passed

## Notes
- Wordstat enrichment is manual/batch endpoint only. No automatic background processing is enabled in this step.
- Frontend grouping is visual/canonical; backend duplicate metadata is attached in services list response.
