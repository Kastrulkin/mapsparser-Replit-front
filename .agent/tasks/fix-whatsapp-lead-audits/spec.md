# Task Spec: fix-whatsapp-lead-audits

## Metadata
- Task ID: fix-whatsapp-lead-audits
- Created: 2026-05-06T14:12:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Исправить все 224 аудита группы Канал - Востапп: backup, formatter, batch regenerate/publish, quality gate, ручная выборка

## Acceptance criteria
- AC1: Production backup exists before modifying lead audit data.
- AC2: All 224 active public audits in group `Канал - Востапп` are regenerated or normalized.
- AC3: Quality gate reports 0 stale/internal bad phrases, 0 missing audits, 0 empty issue blocks, 0 missing action plans.
- AC4: Known mismatch examples (`12 Месяцев`, `Комфорт`) no longer use wrong vertical copy.
- AC5: Representative public audit URLs return HTTP 200 after rollout.

## Constraints
- Preserve existing lead records and audit slugs.
- Do not introduce schema changes.
- Do not overwrite `edited_json`; if a published manual editor snapshot exists, apply it on top of regenerated audit base.

## Non-goals
- Full visual/browser review of every audit page.
- WhatsApp sending.

## Verification plan
- Build: `python3 -m py_compile src/core/card_audit.py src/core/public_audit_editor.py src/api/admin_prospecting.py`
- Production rollout: `docker compose up -d --build app worker`
- Integration checks: DB quality gate over group id `cb88c1fa-637f-41df-bef3-05aeda192f58`
- Manual checks: sample audits for 12 Месяцев, Комфорт, Beauty Lab, 4you, Aml Clinic, КосМед, Культура красоты
- HTTP checks: representative public audit slugs return 200
