# Evidence Bundle: shansik-partner-search

## Summary
- Overall status: PASS
- Last updated: 2026-07-02T11:10:44Z

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Ran partnership geo-search for the Shansik Engelsa 154 location (`0efe3f0d-d32c-5ea9-84e8-e9387418cec1`) with Yandex Maps queries around TRK Grand Canyon.
  - Imported 17 partnership candidates and merged 1 duplicate candidate.
  - Live UI smoke showed the Shansik Engelsa 154 location selected, `Кандидаты: 17`, candidates visible in the candidate step, and source labels rendered as `Яндекс Карты`.
  - Production API smoke after deploy: `/api/partnership/health?business_id=0efe3f0d-d32c-5ea9-84e8-e9387418cec1` returned HTTP 200 with `leads_total=17`.
  - Production API lead check returned 17 leads and all loaded leads had `source_provider=yandex_maps`.
- Gaps:
  - One obvious noisy candidate remains in the list (`Клуб 154`, night club). It is visible and can be filtered by the user with the `Неактуален` action; I did not auto-disqualify it because the current task was to run search and validate the flow, not to make business-selection decisions.

## Commands run
- `scripts/proof_loop.sh init shansik-partner-search "..."`
- `venv/bin/python -m py_compile src/api/admin_prospecting.py`
- `venv/bin/python -m pytest tests/test_partnership_leads_routes_contract.py tests/test_admin_prospecting_audit_payload.py`
- `npm --prefix frontend run build`
- `git diff --check -- src/api/admin_prospecting.py frontend/src/components/prospecting/PartnershipPipelineSections.tsx frontend/src/pages/dashboard/PartnershipSearchPage.tsx`
- `scripts/deploy_backend_src.sh`
- `scripts/deploy_frontend_dist.sh`
- Production API smoke for `/api/partnership/health` and `/api/partnership/leads` on the Shansik Engelsa 154 business.

## Raw artifacts
- .agent/tasks/shansik-partner-search/raw/build.txt
- .agent/tasks/shansik-partner-search/raw/test-unit.txt
- .agent/tasks/shansik-partner-search/raw/test-integration.txt
- .agent/tasks/shansik-partner-search/raw/lint.txt
- .agent/tasks/shansik-partner-search/raw/screenshot-1.png
- .agent/tasks/shansik-partner-search/raw/geo_search_requests.jsonl
- .agent/tasks/shansik-partner-search/raw/shansik_engelsa_leads_after_search.txt
- .agent/tasks/shansik-partner-search/raw/source_provider_correction.txt

## Known gaps
- The browser runtime reset during the final post-backend reload, but an earlier live UI smoke verified the user flow after frontend deploy, and the final server/API smoke verified backend health and lead data after the last backend deploy.
