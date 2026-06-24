# Evidence Bundle: agents-custom-create-reviews-telegram-20260616

## Summary
- Overall status: PASS
- Last updated: 2026-06-16T15:36:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Created a custom Riderra agent from the browser for: check new company reviews, draft a polite reply, send the review plus draft to Telegram, do not publish automatically.
  - Ran a safe test; the result created a pending human decision and did not execute an external send.
  - Final browser check: `hasCreatedAgent=true`, `hasPendingDecision=true`, `consoleErrors=0`.
- Gaps:
  - The preview created a real pending decision; it was intentionally not accepted.

### AC2
- Status: PASS
- Proof:
  - Required provider/connection choices now render inline in the main builder flow when missing.
  - Re-ran the browser flow and completed provider choices without digging into collapsed technical details.
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - Final browser check found no visible old technical terms: `OpenClaw`, `Boundary`, `provider route`, `preflight`, `Preview run`, `Production run`, `Последний run`, `маршрут`.
  - Visible overview now shows `отзывы компании, Telegram, профиль бизнеса`, `Последний запуск`, `Выбрать способ подключения`, and credit-only billing.
- Gaps:
  - Technical details remain available under the separate “Техническое” tab by design.

## Commands run
- `npm run build:all` from `frontend/`
- `scripts/deploy_frontend_dist.sh`
- Production checks: `docker compose ps`, `curl -I http://localhost:8000`, live asset check on `https://localos.pro/`
- Browser checks on `https://localos.pro/dashboard/agents`

## Iteration 1 - browser user flow
- Started custom agent creation in `/dashboard/agents` as Riderra user.
- Scenario: check new company reviews, draft reply, send review plus draft to Telegram, no auto-publish.
- Found blocker: after answering clarifications, UI asks to choose provider routes but route choices are hidden inside collapsed details; visible CTA says "Выбрать ниже" with no visible choices.
- Found UX issue: data summary shows `Telegram, Telegram, профиль бизнеса` instead of review source.
- Change: moved required connection/route choice panels into the main builder flow when required; dedupe/augment data source labels with `отзывы компании` when task mentions reviews.

## Raw artifacts
- .agent/tasks/agents-custom-create-reviews-telegram-20260616/raw/build.txt
- .agent/tasks/agents-custom-create-reviews-telegram-20260616/raw/test-unit.txt
- .agent/tasks/agents-custom-create-reviews-telegram-20260616/raw/test-integration.txt
- .agent/tasks/agents-custom-create-reviews-telegram-20260616/raw/lint.txt
- .agent/tasks/agents-custom-create-reviews-telegram-20260616/raw/screenshot-1.png

## Known gaps
- The preview/pending decision was not accepted, to avoid an external side effect without explicit user approval.

## Iteration 3 - final production verification
- Deployed frontend asset `/assets/index-Unkn8UT8.js` to production.
- Production checks: app and worker containers running, HTTP 200 from app, live index references the fresh asset.
- Final browser checks:
  - `hasCreatedAgent: true`
  - `hasPendingDecision: true`
  - `hasReviewsData: true`
  - `hasOldTechTerms: []`
  - `hasAwkwardApprovalPhrase: false`
  - `consoleErrors: 0`

## Iteration 2 - create and preview
- Re-ran browser flow after inline route chooser fix.
- Successfully created a custom agent for Riderra: checks new company reviews, drafts a reply, sends review plus draft to Telegram, no auto-publish.
- Started safe preview via the normal `Запустить` button.
- Preview created a pending human decision; no external send was executed.
- Browser console errors: 0.
- Found polish issues after creation: technical terms leaked in overview (`OpenClaw`, `Boundary`, `provider route`, `needs_connection`, `Preview run`).
- Change: added user-facing text mapping for route/action labels, activation summary, billing rows and next-step status.
