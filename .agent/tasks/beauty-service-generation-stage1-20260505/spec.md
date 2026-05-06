# Task Spec: beauty-service-generation-stage1-20260505

## Metadata
- Task ID: beauty-service-generation-stage1-20260505
- Created: 2026-05-05T13:55:10+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 1: Качество генерации SEO-названий и описаний услуг для beauty-профиля: beauty-specific profile, prompt/template update, attribute extraction, guardrails, forbidden words config, deduplication, fallback, regression tests. Не делать правила глобальными для всех бизнесов.

## Acceptance criteria
- AC1: Beauty-specific rules are scoped to beauty/salon services and are not applied globally to every business vertical.
- AC2: Service prompt/template requires short names, one-sentence descriptions, and preservation of beauty-specific attributes.
- AC3: Backend extracts critical beauty attributes before generation and exposes them to the prompt.
- AC4: Backend guardrails reject/fallback generated names or descriptions that lose attributes, add forbidden marketing phrases, add risky promises, or narrow a service to an unconfirmed zone.
- AC5: Duplicate/canonical beauty services reuse consistent generated style during post-processing.
- AC6: Regression tests cover the requested Organika-style cases.

## Constraints
- Do not change production data.
- Do not add schema migrations.
- Do not make beauty rules global for non-beauty businesses.
- Prefer small backend-focused changes.

## Non-goals
- Full SEO keyword detection/scoring improvements; that is stage 2.
- UI redesign for /dashboard/card.
- Production deployment.

## Verification plan
- Build: `python3 -m py_compile src/core/beauty_service_optimization.py src/core/service_optimization_verticals.py src/main.py`
- Unit tests: `./venv/bin/python -m pytest -q tests/test_beauty_service_optimization.py tests/test_checkout_session_service.py tests/test_auth_email_case_insensitive.py`
- Integration tests: not required for stage 1; endpoint behavior is covered through backend post-processing units and existing checkout/auth tests for adjacent regressions.
- Lint: no dedicated lint command found for this backend slice.
- Manual checks: inspect prompt and post-processing diff for beauty scoping and no DB changes.
