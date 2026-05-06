# Evidence Bundle: content-plan-network-context

## Summary
- Overall status: PASS
- Last updated: 2026-05-04T06:03:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Added network scope expansion in `src/services/content_plan_service.py`: parent network context now resolves parent + child business ids before loading map links, services, SEO, sales signals and news.
- Gaps:
  - None.

### AC2
- Status: PASS
- Proof:
  - Live read-only API check for Lukoil network parent returned `success=True`, `map_links_count=93`, `network_locations=93`, `seo=15`.
  - First SEO keywords are fuel/AZS-focused: `лукойл`, `лукойл азс`, `лукойл заправка`, `азс рядом`, `заправка рядом`, `заправка на карте`, `круглосуточная азс`, `бензин 95`.
  - `missing_inputs` contains only `services`, matching production data absence.
- Gaps:
  - Services are still empty because production `userservices` has no records for this network.

### AC3
- Status: PASS
- Proof:
  - `30 passed in 0.17s`.
- Gaps:
  - None.

## Commands run
- `source venv/bin/activate && python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`
- `git diff --check`
- `rsync -az --delete --exclude '__pycache__' --exclude '*.pyc' -e 'ssh -i ~/.ssh/localos_prod' src/ root@80.78.242.105:/opt/seo-app/src/`
- `ssh -i ~/.ssh/localos_prod root@80.78.242.105 'cd /opt/seo-app && docker compose restart app worker && docker compose ps && sleep 5 && curl -I http://localhost:8000'`
- `curl -ksS -H 'Authorization: Bearer <token>' 'https://localos.pro/api/content-plans/context?business_id=f3e4f2fb-38b4-40b8-a438-a5921c6e105c&scope_type=network_parent&scope_target_id=f3e4f2fb-38b4-40b8-a438-a5921c6e105c'`

## Raw artifacts
- .agent/tasks/content-plan-network-context/raw/build.txt
- .agent/tasks/content-plan-network-context/raw/test-unit.txt
- .agent/tasks/content-plan-network-context/raw/test-integration.txt
- .agent/tasks/content-plan-network-context/raw/lint.txt
- .agent/tasks/content-plan-network-context/raw/screenshot-1.png

## Known gaps
- Production services for Lukoil are not populated, so readiness still reports `services` as missing.
