# Task Spec: operator-sprint39-content-history-20260524

## Metadata
- Task ID: operator-sprint39-content-history-20260524
- Created: 2026-05-24T15:12:56+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 39: normalize Operator content draft history by type for news, social posts, review replies, and service suggestions/apply states

## Acceptance criteria
- AC1: Operator exposes a content history endpoint that returns typed history items.
- AC2: History separates review replies, news, social posts, service suggestions, and applied service changes.
- AC3: New social post drafts are stored with a distinct prompt key.
- AC4: Web Operator shows the separated history without external publication.

## Constraints
- Do not publish content to external channels.
- Do not change pricing or credit behavior.
- Do not introduce a new runtime table for this sprint.

## Non-goals
- Editing drafts.
- Telegram content-history parity.
- External social/map publishing.

## Verification plan
- Build: frontend production build.
- Unit tests: content history, news generation, social post generation.
- Integration tests: route import and diff whitespace checks.
- Lint: backend baseline.
- Manual checks: review Operator UI diff.
