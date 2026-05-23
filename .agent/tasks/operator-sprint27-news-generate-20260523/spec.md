# Task Spec: operator-sprint27-news-generate-20260523

## Metadata
- Task ID: operator-sprint27-news-generate-20260523
- Created: 2026-05-23T19:54:00+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 27: make news_generate a real paid compute Operator action: web chat/Inbox -> preflight -> reserve -> generate news -> save UserNews draft -> charge credits; no autopublish

## Acceptance criteria
- AC1: `news_generate` is a real Operator paid-compute workflow from web chat and Inbox/API.
- AC2: The workflow runs preflight, reserves credits, generates a news draft, saves it into `usernews`, and finalizes a credit charge only after a successful draft.
- AC3: Failure and empty-generation paths release the reservation and do not write credit ledger charges.
- AC4: External publication remains manual: no map, social, or provider write is performed.
- AC5: Web UI can trigger the action and display/copy the saved draft result.
- AC6: Documentation and proof evidence describe the new boundary.

## Constraints
- Do not change production data manually.
- Do not add external provider writes or autopublishing.
- Keep unrelated worktree changes out of the Sprint 27 commit.

## Non-goals
- No Apify execution.
- No social-post generation yet.
- No services optimization yet.
- No Telegram parity for this action in Sprint 27.

## Verification plan
- Build: `python3 -m py_compile src/services/operator_news_generation.py src/api/operator_api.py`; `cd frontend && npm run build`.
- Unit tests: focused Operator pytest suite including `tests/test_operator_news_generation.py`.
- Integration tests: API flow covered by service-level tests with fake cursor; live deploy smoke after commit.
- Lint: `git diff --check`.
- Manual checks: verify runtime imports on production container after deploy.
