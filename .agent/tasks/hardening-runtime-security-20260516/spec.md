# Task Spec: hardening-runtime-security-20260516

## Metadata
- Task ID: hardening-runtime-security-20260516
- Created: 2026-05-16T09:16:01+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Исправить по приоритетному плану: P0 PostgreSQL/SQLite несовместимости runtime; CORS по ALLOWED_ORIGINS; убрать опасные auth/debug логи; P1 точечный rate limiting; prod/test compose разделение без Docker socket в prod; EXTERNAL_AUTH_SECRET_KEY обязательный для production; GigaChat SSL workaround как явная настройка; безопасная первая волна P2 cleanup/lint baseline без разрушительного рефакторинга.

## Acceptance criteria
- AC1: Runtime PostgreSQL compatibility is improved without requiring a broad monolith rewrite.
- AC2: CORS uses configured `ALLOWED_ORIGINS` and no longer allows wildcard origins with credentials.
- AC3: Sensitive auth/debug logs no longer expose password-hash fragments, session payloads, or traceback bodies by default.
- AC4: Rate limiting is enabled only for sensitive endpoints, with no global API blanket limit.
- AC5: Production compose no longer mounts Docker socket; testcontainers configuration is moved to a test override.
- AC6: GigaChat TLS verification defaults to enabled, with explicit env fallback for the known provider SSL workaround.
- AC7: Production external-auth encryption fails closed when `EXTERNAL_AUTH_SECRET_KEY` is missing.
- AC8: Safe cleanup/lint-baseline work is completed without touching unrelated user changes.

## Constraints
- Do not modify production data.
- Do not perform destructive schema operations.
- Preserve existing dirty worktree changes not owned by this task.
- Keep changes incremental because `src/main.py` is a large legacy monolith.

## Non-goals
- Full `src/main.py` domain split.
- Full TypeScript type cleanup.
- Full pytest/testcontainers gate run.
- Deployment to server.

## Verification plan
- Build: Python compile for tracked files; frontend production build.
- Unit tests: focused pytest set covering query adapter, auth normalization, payment/client utilities, URL/review/service/finance helpers.
- Integration tests: import `main`, verify limiter exists and CORS origin list is configured.
- Lint: `npm run lint -- --quiet`.
- Manual checks: static searches for removed tracked artifacts, Docker socket moved out of production compose, no GigaChat silent `verify=False` defaults.
