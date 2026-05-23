# Task Spec: operator-sprint28-social-post-generate-20260523

## Metadata
- Task ID: operator-sprint28-social-post-generate-20260523
- Created: 2026-05-23T20:05:00+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 28: make social_post_generate a real paid compute Operator action: web chat/Inbox -> preflight -> reserve -> generate social post draft -> save draft -> charge credits; copy/manual publish only

## Acceptance criteria
- AC1: `social_post_generate` is a real Operator paid-compute workflow from web chat and Inbox/API.
- AC2: The workflow runs preflight, reserves credits, generates a post draft, saves it, and finalizes charge only after success.
- AC3: Failure and empty-generation paths release reservation and do not charge credits.
- AC4: External publication remains manual.
- AC5: Web UI can trigger and copy the post draft.
- AC6: Documentation and proof evidence describe the boundary.

## Constraints
- Do not add external publishing.
- Do not change production data manually.
- Keep unrelated worktree changes out of the Sprint 28 commit.

## Non-goals
- No Apify execution.
- No services optimization.
- No Telegram parity in Sprint 28.

## Verification plan
- Build: py_compile and frontend build.
- Unit tests: focused Operator pytest suite.
- Lint: git diff --check.
- Deploy smoke after commit.
