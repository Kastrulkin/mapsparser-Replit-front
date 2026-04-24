# Evidence Bundle: dashboard-inner-polish-20260423

## Summary
- Overall status: PASS
- Last updated: 2026-04-24T07:25:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `PartnershipSearchPage.tsx` no longer owns the full workspace header/control summary.
  - `PartnershipWorkspaceOverview.tsx` now owns the page header, compact metrics, action panel, and workspace tabs.
  - `PartnershipRawIntakeControls.tsx` now owns the raw import and geo-search control panels.
  - `PartnershipOperationalSections.tsx` now owns drafts, queue, and sent/outcome sections.
  - `PartnershipPipelineSections.tsx` now owns pipeline lead cards, board/list body, and sticky bulk bar.
  - `PartnershipAnalyticsWorkspace.tsx` now owns the analytics workspace body.
  - `partnershipApi.ts` centralizes partnership endpoint paths for leads, drafts, queue, batches, reactions, export, and analytics loading.
  - Direct partnership endpoint calls were removed from `PartnershipSearchPage.tsx` except the existing request callback passed into pilot-flow helpers.
  - The existing workspace routing and counts are passed through unchanged.
- Gaps:
  - Remaining page code is mostly local UI state, derived data, pilot-flow orchestration, export formatting, and drawer wiring.

### AC2
- Status: PASS
- Proof:
  - `CardOverviewPage.tsx` uses `DashboardSection` for competitors, rating summary, and services.
  - `CardServicesTable.tsx` now owns the services table, SEO proposal editing UI, sticky scrollbar, and row actions.
  - `CardServicesControls.tsx` now owns add/edit forms, optimizer panel, service meta strip, and filters.
  - `CardOverviewTabs.tsx` now owns competitors, reviews, news, and keywords tab bodies.
  - `cardOverviewApi.ts` centralizes card overview network calls and parse-policy normalization.
  - `cardServicesLogic.ts` owns service source formatting and SEO-draft comparison helpers.
  - The service tab no longer duplicates the add-service primary CTA in both the section header and body.
  - Existing service, review, news, keyword, and competitor handlers were preserved.
- Gaps:
  - Some service optimization orchestration remains in `CardOverviewPage.tsx` because it mutates several local UI states.

### AC3
- Status: PASS
- Proof:
  - `AIAgentSettings.tsx` has a calmer header, cards, status styling, and save button.
  - `TelegramConnection.tsx`, `WhatsAppConnection.tsx`, and `ExternalIntegrations.tsx` use quieter borders/surfaces.
  - `AdminExternalCabinetSettings.tsx` uses calmer surfaces and more resilient wrapped action rows.
  - `WABACredentials.tsx`, `TelegramBotCredentials.tsx`, and `NetworkManagement.tsx` use calmer card, alert, and nested form surfaces.
  - Loud gradients and iridescent button styling were removed from the nested settings flow.
- Gaps:
  - Some lower-level integration subcomponents still keep their own local styles.

### AC4
- Status: PASS
- Proof:
  - Frontend production build completed successfully.
  - Frontend-only deploy completed successfully.
  - Server verification returned healthy containers, app logs without new fatal errors, and `HTTP/1.1 200 OK`.
  - Live HTML references `/assets/index-DisXlU4x.js` and `/assets/index-CNr4qw6E.css`.
  - Local browser-smoke passed for `/dashboard/profile`, `/dashboard/card-overview`, `/dashboard/progress`, `/dashboard/partnership-search`, and `/dashboard/settings` with no ReferenceError/chunk-load/white-screen errors.
  - `/.git/config` was sanity-checked and returns SPA `index.html`, not a real git config.
- Gaps:
  - Live in-app browser navigation was blocked by the browser runtime allowlist, so live verification used deploy-script curl checks rather than browser clicks.

## Commands run
- `cd frontend && npm run build`
- `./scripts/deploy_frontend_dist.sh --build`
- `cd /opt/seo-app && docker compose ps`
- `cd /opt/seo-app && docker compose logs --since 10m app`
- `cd /opt/seo-app && curl -I http://localhost:8000`

## Raw artifacts
- `.agent/tasks/dashboard-inner-polish-20260423/raw/build.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/build-dashboard-inner-polish-2.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-dashboard-inner-polish-2.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/build-operational-sections.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/build-deeper-sections.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-deeper-sections.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-deeper-final.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-pass3.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-pass4.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/build-pass5-final.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/preview-pass5.txt`
- `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-pass5.txt`

## Known gaps
- `PartnershipSearchPage.tsx` remains a large operational screen, but endpoint calls and major workspace sections are extracted.
- `CardOverviewPage.tsx` still contains service optimization orchestration, but card API calls, service helpers, table, controls, and tab bodies are extracted.

## Pass 6: 2026-04-24
- `frontend/src/components/prospecting/usePartnershipWorkspaceDerivedData.ts` now owns the remaining PartnershipSearchPage derived data: lead visibility, selected lead media, flow summaries, queue flattening, pilot summary, and status counters.
- `frontend/src/components/prospecting/partnershipExport.ts` now owns operator snapshot payload/markdown formatting and CSV template generation.
- `frontend/src/components/dashboard/useCardServiceController.ts` now owns service add/edit/delete, SEO optimization, bulk optimization, and accept/reject proposal state.
- `CardOverviewPage.tsx` no longer keeps service optimization orchestration in page-local functions.
- Settings pass: `TelegramConnection.tsx`, `WhatsAppConnection.tsx`, and `ExternalIntegrations.tsx` use calmer rounded shells; Telegram routine status console logs were removed.
- Verification: `cd frontend && npm run build` passed in `.agent/tasks/dashboard-inner-polish-20260423/raw/build-pass6-final.txt`.
- Verifier note: no separate subagent verifier was spawned because this thread did not explicitly authorize subagent delegation; proof-loop validation was run locally.

## Partnerships UX/UI pass: 2026-04-24
- `/dashboard/partnerships` now uses clearer operator wording: `Поиск партнёров`, `Поиск лидов`, `Воронка`, `Черновики`, `Отправка`, `Отправлено`.
- `PartnershipWorkspaceOverview.tsx` has a calmer header, compact metric strip, clear next-action panel, and folder-like workspace navigation.
- `PartnershipRawIntakeControls.tsx` separates the two entry paths into explicit cards: importing an existing list and finding partners on the map.
- `PartnershipPipelineSections.tsx` has cleaner lead rows/cards, softer board columns, clearer bulk-action area, and secondary technical/source details moved behind disclosure.
- `PartnershipOperationalSections.tsx` now presents drafts, queue, and sent/outcomes as quieter operational sections with less internal/system wording.
- `PartnershipAnalyticsWorkspace.tsx` now uses more human-readable Russian labels for weekly review, source quality, pilot summary, and operator actions.
- Verification: `cd frontend && npm run build` passed in `.agent/tasks/dashboard-inner-polish-20260423/raw/build-partnerships-ux-final.txt`.
- Follow-up polish: visible outcome labels in partnerships queue/sent/analytics were translated to Russian operator labels while preserving API enum values.
- Verification: final build/deploy passed in `.agent/tasks/dashboard-inner-polish-20260423/raw/deploy-partnerships-ux-final.txt`; live HTML now references `/assets/index-2B07cX0O.js`, and `/dashboard/partnerships` returns 200.
