# Task Spec: organika-service-editorial-20260507

## Metadata
- Task ID: organika-service-editorial-20260507
- Created: 2026-05-07T14:18:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Довести все описания услуг Органики до продового уровня: использовать выявленные beauty-паттерны, SEO-ключи и здравый смысл; сохранить факты услуги и проверить качество.

## Acceptance criteria
- AC1: All active Organika services have non-empty, human-readable descriptions that preserve service facts.
- AC2: Service descriptions use relevant beauty-industry patterns without unsafe promises or generic fallback text.
- AC3: SEO keyword scoring for Organika remains clean: 0 needs_review, 0 manual_review, 0 missing_keywords, 0 weak_matches_only.
- AC4: Production data change is backed up before write.

## Constraints
- Do not change schema.
- Do not use global rules that affect other businesses.
- Preserve critical attributes from names: zone, hair length, gender, age, product, dose/volume, number of sessions/zones when present.
- Avoid marketing/medical promises: no "безболезненно", "стойкий результат", "мгновенный эффект", "без вреда".

## Non-goals
- Deduplicate Organika service rows.
- Re-run external parsers or Wordstat.
- Deploy frontend/backend code.

## Verification plan
- Server health: docker compose ps, app/worker logs, curl localhost.
- Data audit: build_services_quality_audit for Organika.
- Manual samples across key categories: waxing, biozavivka, injections, laser, manicure.
