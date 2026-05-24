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
- AC1: Saved `services_optimize` suggestions can be applied only through a separate confirmed Operator action.
- AC2: Applying suggestions updates internal `userservices` fields and marks suggestion items fixed.
- AC3: The apply action performs no external provider writes and charges no additional credits.
- AC4: Web Operator exposes the confirmation action and shows the applied result.

## Constraints
- Do not publish to Yandex, Google, 2GIS, or other external providers.
- Do not generate new suggestions in the apply step.
- Do not add another credit charge after the paid suggestion generation step.

## Non-goals
- Telegram apply parity.
- External provider service publishing.
- New service optimization pricing.

## Verification plan
- Build: frontend production build.
- Unit tests: Operator services optimization plus nearby Operator tests.
- Integration tests: API route import/compile coverage.
- Lint: whitespace diff check.
- Manual checks: review changed UI/API diff and proof evidence.
