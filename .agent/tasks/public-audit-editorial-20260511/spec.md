# Task Spec: public-audit-editorial-20260511

## Metadata
- Task ID: public-audit-editorial-20260511
- Created: 2026-05-11T12:31:43+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Улучшить публичную страницу аудита карточки: структура, самопомощь, конкретный язык рекомендаций, CTA без лендингового давления

## Acceptance criteria
- AC1: First screen shows a short diagnosis, strengths, top growth points, and what to fix first.
- AC2: Public page includes a self-help block with description template, photo checklist, post ideas, review reply templates, and today / 7 days / regular plan.
- AC3: Repeated "How LocalOS helps" copy is removed from each problem block and replaced with one shared LocalOS block below practical value.
- AC4: Public-facing problem language avoids abstract marketing phrases and explains photo, description, reviews, and news issues in owner-friendly terms.
- AC5: CTA surface keeps one primary action and one secondary self-help action.
- AC6: Frontend build, targeted backend tests, syntax checks, route smoke, and text regression checks pass.

## Constraints
- Do not change parsing, scoring, calculations, or public route shape.
- Keep i18n-compatible public rendering.
- Do not add unverified facts; use cautious wording when data may be uncertain.
- Keep changes scoped to audit presentation, public copy normalization, and tests.

## Non-goals
- No redesign of the whole public page.
- No production deploy or production data edits.
- No changes to audit scoring formulas.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m pytest -q tests/test_public_audit_editor.py tests/test_admin_prospecting_audit_payload.py`
- Syntax: `python3 -m py_compile src/core/audit_editorial.py src/core/public_audit_editor.py src/core/card_audit.py`
- Diff hygiene: `git diff --check`
- Text regression: grep public-facing page/backend emitters for old abstract phrases.
- Route smoke: preview frontend and request `/evromedservis-pushkin-krasnoselskoe-shosse?lang=ru`.
