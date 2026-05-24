# Task Spec: operator-sprint40-refresh-billing-polish-20260524

## Metadata
- Task ID: operator-sprint40-refresh-billing-polish-20260524
- Created: 2026-05-24T15:12:57+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 40: show understandable refresh lifecycle billing state including reserved, charged actual, released, overage, and provider cost

## Acceptance criteria
- AC1: Refresh result and refresh job list include billing state.
- AC2: Billing state includes reserved, charged, released, overage, provider actual cost, multiplier, and actual credits when available.
- AC3: Apify settlement stores actual-cost metadata on the reservation for UI display.
- AC4: Web Operator renders refresh billing details clearly.

## Constraints
- Do not change refresh pricing.
- Do not add new external provider writes.
- Do not call Apify directly from Operator UI.

## Non-goals
- Billing export/reporting.
- Retry or reliability panel.
- Telegram proactive refresh completion follow-up.

## Verification plan
- Build: frontend production build.
- Unit tests: refresh result and Apify settlement.
- Integration tests: route import and diff whitespace checks.
- Lint: backend baseline.
- Manual checks: review Operator refresh UI diff.
