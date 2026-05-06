# Evidence Bundle: content-plan-p0

## Summary
- Overall status: PASS
- Last updated: 2026-05-03T15:00:36+03:00

## Follow-up slice: UX smoke / polish / bulk maturity
- Status: PASS
- Proof:
  - Проведён code-level UX smoke `frontend/src/components/content-plan/ContentPlanTab.tsx`: первый экран был перегружен настройками генерации и подробными learning-метриками до рабочего плана.
  - Расширенные настройки генерации (`density`, content mix) скрыты за кнопкой `Настроить источники`, чтобы базовый сценарий оставался коротким: scope, horizon, build.
  - Блок `Learning loop` переименован в пользовательский `Качество плана`; подробные метрики скрыты за `Показать метрики`, а по умолчанию показываются короткие operator insights.
  - В `Режим управления сетью` добавлены bulk-действия `Перенести неделю` и `Пропустить срез` рядом с генерацией и созданием новостей.
  - `npm run build` в `frontend/` завершился успешно.
  - `scripts/deploy_frontend_dist.sh --build` выкатил frontend dist на production.
  - Live smoke: `https://localos.pro` отдаёт `200`, live index ссылается на `/assets/index-BHGe2RdX.js`, chunk `/assets/NewsGenerator-4a1pVuZn.js` содержит новые UX-тексты.
  - Server smoke: `cd /opt/seo-app && docker compose ps` показывает `app`, `worker`, `postgres` в состоянии `Up`; `curl -I http://localhost:8000` вернул `200 OK`.
- Notes:
  - `tar: file changed as we read it` проявился во время asset sync, но deploy script дошёл до verification, live bundle обновлён, контейнеры и HTTP checks зелёные.

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Добавлены новые таблицы `contentplans` и `contentplanitems` через миграцию `alembic_migrations/versions/20260430_add_content_plans.py`.
  - Добавлен backend service `src/services/content_plan_service.py` для context aggregation, tariff gating, plan generation, item update, draft generation и `item -> usernews`.
  - Добавлен API blueprint `src/api/content_plans_api.py` и регистрация в `src/main.py`.
  - Добавлен policy helper `get_allowed_content_plan_horizons` в `src/subscription_manager.py`.
  - Добавлен skeleton generator `src/core/content_plan_generator.py`.
  - Во frontend добавлена вкладка `Контент-план` внутри `NewsGenerator` с period/scope/mix controls и действиями по item через `frontend/src/components/content-plan/ContentPlanTab.tsx`.
  - `npm run build` завершился успешно.
  - `python3 -m py_compile src/core/content_plan_generator.py src/services/content_plan_service.py src/api/content_plans_api.py src/subscription_manager.py src/main.py` завершился успешно.
  - `python3 -m pytest -q tests/test_content_plan_policy.py tests/test_content_plan_generation.py` завершился успешно: `5 passed`.
- Gaps:
  - End-to-end ручная проверка через локально поднятый UI/API не выполнялась в этой итерации.
  - Первичный production rollout P0 был выполнен в предыдущих итерациях; текущий follow-up slice был frontend-only и выкатился без миграций.

## Commands run
- `npm run build`
- `python3 -m py_compile src/core/content_plan_generator.py src/services/content_plan_service.py src/api/content_plans_api.py src/subscription_manager.py src/main.py`
- `python3 -m pytest -q tests/test_content_plan_policy.py tests/test_content_plan_generation.py`
- `cd frontend && npm run build`
- `scripts/deploy_frontend_dist.sh --build`
- `curl -ksSI https://localos.pro`
- `curl -ksS https://localos.pro/assets/NewsGenerator-4a1pVuZn.js | rg ...`
- `cd /opt/seo-app && docker compose ps`
- `cd /opt/seo-app && curl -I http://localhost:8000`

## Raw artifacts
- .agent/tasks/content-plan-p0/raw/build.txt
- .agent/tasks/content-plan-p0/raw/test-unit.txt
- .agent/tasks/content-plan-p0/raw/test-integration.txt
- .agent/tasks/content-plan-p0/raw/lint.txt
- .agent/tasks/content-plan-p0/raw/screenshot-1.png

## Known gaps
- Ручной клик-тест под реальным логином в браузере не выполнялся в этой итерации.
- Текущий follow-up не менял backend/schema, поэтому миграции и DB backup не требовались.
