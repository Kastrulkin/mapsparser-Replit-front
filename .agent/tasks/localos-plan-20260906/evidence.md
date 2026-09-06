# Evidence: localos-plan-20260906

Дата: 2026-09-06. Полный план: **IN_PROGRESS**. Первый локальный пакет: **CONDITIONAL_PASS** по независимой read-only проверке [/root/final_package_verdict](raw/review-package-final.md). Root сохранил её вывод. Ниже сохранён локальный срез до production-выпуска; это не приёмка всего R0–R7. Первый пакет впоследствии выпущен после отдельного разрешения: [production evidence](../../../outputs/localos-release-20260906/production-evidence.json). Авторизованный production API smoke завершён после отдельного согласия: 12 read-only GET прошли, приёмка ограниченного выпущенного пакета — PASS; весь план остаётся IN_PROGRESS.

## Проверенный результат

| Проверка | Результат | Доказательство |
| --- | --- | --- |
| Backend с реальными PostgreSQL сценариями | 310 passed, EXIT=0 | [backend](raw/backend-final.txt) |
| TypeScript, целевые frontend tests, app/public build | 53 passed, полный typecheck и обе сборки | [frontend](raw/frontend-gate.txt) |
| Compiled browser RU/EN, mock API | 14 passed | [mock browser](raw/compiled-agent-e2e-final.txt) |
| Today, настоящие staging API, cookie-вход | 3 passed | [cookie](raw/staging-today-browser.txt) |
| Today, настоящие staging API, production bearer-режим | 3 passed | [bearer](raw/staging-today-bearer.txt) |
| Compiled browser, фактический выбранный run/report/CSV | 3 passed: desktop, Android 360, Telegram 393 | [compiled UI](raw/staging-compiled-browser-table-final.txt) |
| Compiled API и изолированный runner | 10 preview, 5 runs, runtime_ai_calls=0 | [compiled API](raw/staging-compiled-api.txt) |
| Docker runner: исполнение и ограничения | PASS | [runner](raw/runner-docker.txt) |
| Alembic 20260906_012, DML-only helpers | 13 helpers, savepoint сохранён | [DML](raw/staging-dml-role.json) |
| Старый backend на расширенной схеме | health/login/Today 200 | [rollback](raw/staging-rollback.txt) |
| Startup scripts после recreate старого image | PASS | [startup](raw/startup-mount-docker.txt) |
| Compose migration mode и mounts | 2 passed после red | [Compose](raw/compose-startup-green.txt) |
| CRM delivered → waiting_reply | 2 passed после red | [migration regression](raw/review-migrations-pg.txt) |
| Production UI flags и hashes | Обе сборки EXIT=0; неизменность source во время build | [build proof](raw/frontend-production-build-proof.json) |

Compiled staging использует синтетические данные и явный internal manual source. Это подтверждает выполнение утверждённого скрипта без модели, но не качество model-backed генерации и не успех пользовательского пилота. Ни одна проверка не отправляла сообщения и не меняла production.

## Воспроизводимость и выпуск

Точные команды и вывод находятся в логах. Backend gate — scripts/ci_gate_localos_plan.sh; требуется отдельная тестовая PostgreSQL БД. scripts/test_compiled_table_staging.py запускается только на заранее настроенном изолированном synthetic staging с включённым internal pilot. В конце проверки staging возвращён к флагам выпуска: bearer-вход, compiled preview/execute и персонализация выключены.

Состав исходников — [owned-files.json](owned-files.json), контракты — [spec.md](spec.md), результаты и source SHA-256 — [evidence.json](evidence.json). Посторонние изменения исключены; Compose включается частично без Google Cloud hunks. Production UI собирается build_production_ui.py; package_release.py после commit проверяет соответствие исходников Git и проверенной сборке. Артефакты: outputs/localos-release-20260906/payload.tar.gz, compose.patch, release-manifest.json. Manifest фиксирует commit и SHA-256; архив не заменяет push или deployment.

Read-only production preflight: Alembic 20260905_004, 48 live source/startup/migration hashes без неожиданного дрейфа. Наблюдения повторяются перед выпуском. Пакет содержит 12 миграций, seeds и согласование legacy CRM-статусов; нужны отдельное разрешение и свежий backup. [Порядок выпуска и отката](../../../docs/LOCALOS_RELEASE_2026-09-06.md).

## Остаток плана

- **R0 — FAIL:** Полная сравнительная база latency/SQL/queue/connections отсутствует.
- **R1 — PASS:** Текущие backend, frontend и staging evidence подтверждают пакет исправлений доступа, предпочтений, поздних ответов и повторов.
- **R2 — FAIL:** Нет обязательного наблюдения 4 из 5 реальных пользователей.
- **R3 — FAIL:** Legacy provider transactions и worker split/cutover не завершены.
- **R4 — FAIL:** Нет настоящей model-backed генерации, зарегистрированного read-only источника и реального пользовательского пилота.
- **R5 — FAIL:** Нет 14-дневного реального цикла наблюдения.
- **R6 — FAIL:** Остаются runtime DDL callers, доменные переносы и глобальный DML-only cutover.
- **R7 — FAIL:** Effect proposals, второй пилот и legacy migration не реализованы.

Следующие шаги — [problems.md](problems.md) и [отчёт реализации](../../../docs/LOCALOS_IMPLEMENTATION_STATUS_2026-09-06.md). Промежуточные красные логи сохранены как история; raw/review-package.md не является финальным verdict.
