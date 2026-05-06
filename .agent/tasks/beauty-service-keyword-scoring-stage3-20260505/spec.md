# Task Spec: beauty-service-keyword-scoring-stage3-20260505

## Metadata
- Task ID: beauty-service-keyword-scoring-stage3-20260505
- Created: 2026-05-05T15:32:45+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- README.md
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
Показать уровни совпадения SEO-ключей в UI, расширить beauty-синонимы, сделать scoring полезнее, добавить backend-проверку ключей, собрать Organika regression cases и подготовить stage 4 повторной генерации плохих услуг.

## Acceptance criteria
- AC1: UI on `/dashboard/card` shows keyword match levels: точное совпадение, словоформа, близкая формулировка, ключ не найден / не задан.
- AC2: Beauty synonym dictionary includes: перманент / татуаж / пудровое напыление; маникюр / ногти / покрытие; педикюр / стопы / ногти; ботокс / ботулинотерапия; чистка лица / уход / пилинг; ламинирование / долговременная укладка.
- AC3: Scoring reports found count, missing keywords, correctly added keywords, weak close matches, and exact/normalized/close counts.
- AC4: Backend service optimization returns `seo_keyword_score` for generated service suggestions, so API/Telegram/UI can share the same base semantics.
- AC5: Regression tests cover at least 20 Organika-style beauty service cases across ресницы, брови, инъекции, волосы, детские услуги, маникюр/педикюр.
- AC6: Stage 4 behavior is introduced: bulk optimization targets only bad/missing/fallback service suggestions instead of blindly regenerating every service.

## Constraints
- No schema migration.
- No production data cleanup unless separately approved.
- Keep beauty-specific close matching scoped to service keyword scoring.
- Follow local code standard: no typecasts and no new `as` usage.

## Non-goals
- Full NLP/lemmatizer integration.
- Large UI redesign of the whole services table.
- Rewriting the service optimization endpoint.
- Fixing unrelated project-wide TypeScript errors.

## Verification plan
- Backend tests: `./venv/bin/python -m pytest -q tests/test_service_keyword_scoring.py tests/test_beauty_service_optimization.py`
- Backend compile: `python3 -m py_compile src/core/service_keyword_scoring.py src/core/beauty_service_optimization.py src/main.py`
- Frontend targeted test: `cd frontend && ./node_modules/.bin/sucrase-node scripts/test-card-services-logic.ts`
- Frontend production build: `cd frontend && npm run build:all`
- TypeScript informational check: `cd frontend && ./node_modules/.bin/tsc -p tsconfig.app.json --noEmit`
- Production checks after deploy: `docker compose ps`, app logs, `curl -I http://localhost:8000`, backend scoring smoke, frontend bundle grep.
