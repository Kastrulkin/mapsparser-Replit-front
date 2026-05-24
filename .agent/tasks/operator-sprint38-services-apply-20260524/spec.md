# Task Spec: operator-sprint38-services-apply-20260524

## Metadata
- Task ID: operator-sprint38-services-apply-20260524
- Created: 2026-05-24T14:56:48+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 38: apply service optimization suggestions through explicit approval flow; user reviews saved suggestions and confirms applying selected changes to userservices; no external provider writes

## Acceptance criteria
- AC1: Saved `services_optimize` suggestions can be applied only through a separate confirmed Operator action with explicit `confirm_apply`.
- AC2: Applying suggestions updates internal `userservices` fields and marks suggestion items fixed.
- AC3: The apply action performs no external provider writes and charges no additional credits.
- AC4: Web Operator exposes the confirmation action and shows the applied result.
- AC5: Route ownership, approval-boundary audit, focused tests, frontend build, and UI smoke pass.

## Constraints
- Do not publish to Yandex, Google, 2GIS, or other external providers.
- Do not generate new suggestions in the apply step.
- Do not add another credit charge after the paid suggestion generation step.
- Do not mutate `userservices` unless `confirm_apply` / `explicit_confirmation` is true.

## Non-goals
- Telegram apply parity.
- External provider service publishing.
- New service optimization pricing.

## Verification plan
- Build: backend py_compile and frontend production build.
- Unit tests: Operator services optimization plus nearby Operator/boundary tests.
- Integration tests: local browser render smoke for `/dashboard/operator`.
- Lint: backend lint baseline, including approval-boundary audit.
- Manual checks: review changed UI/API diff and proof evidence.
