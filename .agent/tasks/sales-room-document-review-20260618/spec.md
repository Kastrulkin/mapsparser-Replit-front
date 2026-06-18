# Task Spec: sales-room-document-review-20260618

## Metadata
- Task ID: sales-room-document-review-20260618
- Created: 2026-06-18T11:14:10+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Внедрить цифровую комнату LocalOS с предложением как редактируемым документом: правки к выделенному тексту, комментарии, принятие/отклонение и версии внутри LocalOS

## Acceptance criteria
- AC1: Public sales room shows the current proposal as an editable document-like block.
- AC2: Visitors can select proposal text and submit either a replacement suggestion or a comment with author identity.
- AC3: Pending suggestions can be accepted or rejected; accepted replacement suggestions create a new proposal version and update the current proposal text.
- AC4: Review data is persisted in PostgreSQL through Alembic-managed tables and exposed from the public room API.
- AC5: Existing chat and file upload remain available below the proposal.

## Constraints
- Keep the work inside LocalOS; do not depend on Google Docs.
- Do not mutate production room content during verification without explicit approval.
- Preserve the public room's low-key LocalOS branding.

## Non-goals
- Realtime collaborative editing.
- Inline Word-style visual redlines in V1.
- Multi-reviewer permissions or document locking.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `python3 -m py_compile src/api/admin_prospecting.py`
- Integration tests: safe API GET after deploy; write endpoints verified by code path and build only unless test data is approved.
- Lint: `git diff --check -- ...`
- Manual checks: inspect public room UI after deploy.
