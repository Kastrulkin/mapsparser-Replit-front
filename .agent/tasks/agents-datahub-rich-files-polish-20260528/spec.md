# Task Spec: agents-datahub-rich-files-polish-20260528

## Metadata
- Task ID: agents-datahub-rich-files-polish-20260528
- Created: 2026-05-28T07:23:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Rima-like agents Datahub rich file polish: PDF/DOCX/XLSX ingestion quality, readable errors, API/UI proof, and no external dispatch

## Acceptance criteria
- AC1: PDF, DOCX, and XLSX uploads are extracted into usable agent source text.
- AC2: Unsupported and empty uploads return readable user-facing errors.
- AC3: Rich uploaded files appear in the Datahub-lite catalog as connected ready sources.
- AC4: A document agent run over rich files produces a human-readable review journal and useful output.
- AC5: Generic document agents do not execute capabilities, dispatch, publish, or send externally.
- AC6: Production smoke uses temporary data only and verifies fixture cleanup.

## Constraints
- Do not change existing backend contracts or database schema.
- Do not modify production data except temporary smoke fixtures that are cleaned in the same run.
- Do not start dispatcher or any external provider write path.

## Non-goals
- Full standalone Datahub product.
- Browser-level UI changes in this cycle.
- New external send/publish behavior.

## Verification plan
- Build: not applicable; no frontend runtime changes.
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`.
- Integration tests: production API smoke `scripts/smoke_agent_blueprint_rich_files_api.py`.
- Lint: `scripts/lint_backend_baseline.sh`.
- Manual checks: production health and app logs after smoke.
