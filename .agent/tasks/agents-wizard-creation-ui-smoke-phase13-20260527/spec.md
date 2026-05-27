# Task Spec: agents-wizard-creation-ui-smoke-phase13-20260527

## Metadata
- Task ID: agents-wizard-creation-ui-smoke-phase13-20260527
- Created: 2026-05-27T16:47:36+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Authenticated production UI smoke for creating email, table, and reviews agents through wizard, running them, and seeing review

## Acceptance criteria
- AC1: Production test user can create email, table, and reviews agents through `/dashboard/agents` manual wizard.
- AC2: Each created agent can be launched from its card and reaches a human-readable review/result view.
- AC3: Created generic agents do not execute capabilities or external dispatch; they stop on manual approval.
- AC4: Temporary production smoke data is removed and verified absent.

## Constraints
- Do not modify production data except exact temporary smoke fixtures.
- Do not send email, publish reviews, import tables, start dispatcher, or perform provider writes.
- Do not commit passwords or auth tokens.

## Non-goals
- No product code change unless the UI smoke exposes a real defect.
- No database migration.
- No external provider writes.

## Verification plan
- Create one production smoke user/business fixture.
- Run authenticated browser UI smoke against `https://localos.pro/dashboard/agents`.
- Use manual wizard for email, tables, and reviews.
- Verify production DB safety boundaries and cleanup zero counts.
