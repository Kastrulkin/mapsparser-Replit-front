# Task Spec: p1-operator-blueprint-hardening-20260523

## Metadata
- Task ID: p1-operator-blueprint-hardening-20260523
- Created: 2026-05-23T18:21:11+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Original task statement
P1 Operator bulk review hygiene, Agent Blueprint production hardening, supervised outreach integration, main.py decomposition planning, lint guardrails

## Acceptance criteria
- AC1: Operator bulk review reply changes are committed or removed, with tests proving the paid draft boundary.
- AC2: Agent Blueprint run timeline is more production-visible: recent runs can be opened and artifacts expose useful payload summaries.
- AC3: Supervised outreach blueprint artifacts hydrate from the existing outreach pipeline (`prospectingleads`, `outreachmessagedrafts`, `outreachsendqueue`) without external sends.
- AC4: Backend lint baseline includes guardrails for Operator routes and Agent Blueprint capability boundaries.
- AC5: Focused checks pass: backend tests, backend lint baseline, frontend production build, diff whitespace check.

## Constraints
- Do not mutate production data except repeatable smoke fixtures with cleanup.
- Do not publish/send to external providers from Agent Blueprint or Operator draft flows.
- Do not mix unrelated worktree changes into commits.

## Non-goals
- Full auth/user route decomposition in this cycle.
- Universal Agent Blueprint visual constructor.
- Provider write support for review replies or outreach sends.

## Verification plan
- Build: focused Python `py_compile`; Vite production build.
- Unit tests: Agent Blueprint and Operator focused pytest set.
- Integration tests: existing live Agent Blueprint authenticated smoke after deploy.
- Lint: `scripts/lint_backend_baseline.sh`; `git diff --check`.
- Manual checks: browser/live smoke of `/dashboard/agents` after deploy.
