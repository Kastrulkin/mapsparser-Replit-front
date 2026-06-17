# Task Spec: client-leads-simplification-20260617

## Metadata
- Task ID: client-leads-simplification-20260617
- Created: 2026-06-17T16:05:37+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Simplify client prospecting Leads tab: reduced lead cards, one primary CTA, room preparation modal, human-readable status, simpler top controls and kanban first layer

## Acceptance criteria
- AC1: Lead cards in the client prospecting Leads tab show only the first-layer essentials: name, category/city, rating/reviews, one human status, one primary CTA, and a secondary actions menu.
- AC2: Room creation mode choice is moved out of every lead card into a compact "Подготовить цифровую комнату" modal with the paid data-preparation warning.
- AC3: The Leads tab header shows search, user-facing quick filters, filters drawer entrypoint, add-leads action, and kanban/list switch; source/channel/audit filters are not first-layer controls.
- AC4: Kanban first layer is reduced to four working columns: "Нужно обработать", "Готовим предложение", "Письмо отправлено", "Ответили".
- AC5: Bulk selection controls are only first-layer in list view, while kanban stays focused on one next action per lead.
- AC6: Frontend build passes and no whitespace errors are introduced.

## Constraints
- Frontend-only change unless a backend gap appears.
- Do not mutate production data.
- Preserve existing lead statuses and drawer/detail workflows.
- Keep detailed filters available through the existing filters drawer.

## Non-goals
- No schema changes.
- No new lead table or outreach backend flow.
- No redesign of search/import candidate intake.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: not targeted; this is a UI composition change.
- Integration tests: not targeted; backend endpoints unchanged.
- Lint: `git diff --check -- frontend/src/components/ProspectingManagement.tsx frontend/src/components/prospecting/ProspectingWorkspaceChrome.tsx`
- Manual checks: inspect changed JSX contracts and deployed frontend bundle.
