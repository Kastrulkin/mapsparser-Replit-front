# Evidence Bundle: ai_visibility_hotfix

## Summary
- Overall status: PASS
- Last updated: 2026-05-19T09:58:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `python3 -m py_compile src/main.py` passed locally.
  - `npm run build` passed locally in `frontend/`.
  - Flask test client confirmed raw HTML for `/articles/kak-otzyvy-vliyayut-na-potok-klientov` contains `Article` JSON-LD before React runs.
  - Production deploy completed: `scripts/deploy_frontend_dist.sh --build` and `scripts/deploy_backend_src.sh`.
  - Live root HTML contains JSON-LD `Organization`, `WebSite`, `SoftwareApplication`.
  - Live article HTML contains `og:type=article`, canonical URL, `Article` JSON-LD, and `dateModified=2026-05-19`.
  - Live sitemap has `lastmod=2026-05-19` for `/`, `/articles`, and the updated article URLs.
  - Live HTML no longer contains `localhost:8000` for `og:image` or `twitter:image`.
- Gaps:
  - External search/AI indexes may take time to recrawl. This task only verifies what LocalOS currently serves.

## Commands run
- `python3 -m py_compile src/main.py`
- `cd frontend && npm run build`
- Flask test client route checks for `/` and `/articles/kak-otzyvy-vliyayut-na-potok-klientov`
- `scripts/deploy_frontend_dist.sh --build`
- `scripts/deploy_backend_src.sh`
- `curl -s https://localos.pro/ | rg ...`
- `curl -s https://localos.pro/articles/kak-otzyvy-vliyayut-na-potok-klientov | rg ...`
- `curl -s https://localos.pro/sitemap.xml | rg ...`
- `curl -s https://localos.pro/content-seo.json | rg ...`

## Raw artifacts
- .agent/tasks/ai_visibility_hotfix/raw/build.txt
- .agent/tasks/ai_visibility_hotfix/raw/test-unit.txt
- .agent/tasks/ai_visibility_hotfix/raw/test-integration.txt
- .agent/tasks/ai_visibility_hotfix/raw/lint.txt
- .agent/tasks/ai_visibility_hotfix/raw/screenshot-1.png

## Known gaps
- Recrawl latency remains outside the application. Yandex/Google/Alice may show old snippets until their cache updates.
