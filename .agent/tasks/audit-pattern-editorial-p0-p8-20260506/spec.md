# Task Spec: audit-pattern-editorial-p0-p8-20260506

## Metadata
- Task ID: audit-pattern-editorial-p0-p8-20260506
- Created: 2026-05-06T14:50:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Доработать аудиты P0-P8: убрать шаблонность summary, blacklist/rewrite фразы, подключить industry patterns, улучшить vertical detection, разделить public/whatsapp summary, clean published payload, quality gate, лучшие service patterns в анализ услуг

## Acceptance criteria
- AC1: Public audit summary is concise and no longer uses awkward/template phrases like "за чем сюда идти", "слабый визуальный слой режет доверие", "зоны роста", "без допрекламы".
- AC2: Public audits expose separate public/WhatsApp summary variants and run a quality gate/editorial pass before rendering.
- AC3: Published audit payload is cleaned from internal prompt/AI/debug fields where safe.
- AC4: Medical/beauty vertical detection is stricter and records confidence/reasons/conflicts for mixed cases.
- AC5: Audit generation can use approved industry/service pattern context.
- AC6: Tests cover phrase cleanup, summary rewrite, payload cleanup, and vertical detection regressions.

## Constraints
- Do not change production data or run production regeneration without explicit approval.
- Keep public page contracts backward-compatible where possible.
- Avoid broad unrelated refactors.

## Non-goals
- No production rollout in this step.
- No regeneration of all 224 audits in production in this step.

## Verification plan
- Build: `python3 -m py_compile src/core/audit_editorial.py src/core/public_audit_editor.py src/core/card_audit.py src/api/admin_prospecting.py`
- Unit tests: `python3 -m pytest -q tests/test_public_audit_editor.py tests/test_admin_prospecting_audit_payload.py tests/test_industry_patterns.py`
- Integration tests: not run; production DB access was intentionally not used.
- Lint: `git diff --check`
- Manual checks: targeted grep for forbidden output markers in changed source files.
