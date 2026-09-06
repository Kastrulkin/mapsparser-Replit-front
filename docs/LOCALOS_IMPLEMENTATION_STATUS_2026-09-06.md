# LocalOS: реализация плана 6 сентября

Статус: **первый локальный пакет реализован и проверен; production не изменён**. Весь R0–R7 ещё не завершён. Независимая проверка дала ограниченному пакету `CONDITIONAL_PASS`, полному плану — `INCOMPLETE`: для выпуска остаются отдельное разрешение на новые миграции, свежий backup и повторный live preflight.

Источник требований: [план](LOCALOS_IMPLEMENTATION_PLAN_2026-09-06.md). Исходный выпущенный commit: `ffc54c19122c86b7d8bf2c25aa7d3c8080c754c0`. Результаты первого выпуска не подменяют новую приёмку.

| Этап | Текущий пакет | Что остаётся |
| --- | --- | --- |
| R0 | Заморожены контракты, исходное состояние Git, целевые воспроизведения; staging и production проверены раздельно | Полная сравнительная база latency/SQL/queue/соединений; окончательная приёмка всего плана |
| R1 | Типизированные HTTP-ошибки, очистка отозванного scope, защита поздних ответов, обновление overview после выбора, явный null предложения, идемпотентность компиляции/запуска | Production-выпуск; совместимость отката проверена локально |
| R2 | Стабильная главная; срочное выше предпочтений; выбранное направление доступно даже без задач; прямые переходы и проверка трёх размеров экрана | Пользовательский тест 4/5 за 30 секунд, полные рабочие сценарии целевых пользователей |
| R3 | Admission в UnitOfWork; reservation/run/audit атомарны; lease fencing; compiled claim → закрытие транзакции → runner → fenced finish; реестр worker roles | Legacy provider execution ещё удерживает транзакции; перенос по capabilities и production worker cutover |
| R4 | CSV/TSV/вставка, формальные правила, собственный пример, generated Python, preview/approval, protected approved pointer, входной snapshot и фактический отчёт; проверки current account/cohort/лимитов/retention | Настоящий model-backed пользовательский пилот; зарегистрированный read-only источник; проверенный production image; общий sandbox review |
| R5 | Раздельные флаги сбора и предложений; реальные подтверждённые события; ручной выбор, отказ, отсрочка, opt-out и undo | 14 дней настоящего наблюдения и ручная оценка уместности. Сбор/предложения не включены |
| R6 | 12 последовательных ревизий; перенесены content/learning, actions/billing, growth, часть AI/keywords, reports/Telegram, prospecting/sales-room; migrator/schema-check startup; полный typecheck без baseline-исключений | Дополнительные DDL callers, явные границы остальных доменов, глобальный DML-only cutover только после полного охвата |
| R7 | Зависимость от успешного read-only пилота сохранена | Внешние предложения, второй пилот, поштучный перенос legacy ещё не реализованы |

## Завершённые проверки текущего пакета

- Backend gate: **310 passed**, `raw/backend-final.txt`, EXIT=0; реальные PostgreSQL проверки admission, транзакций, stale lease, snapshot, account revocation, generation/replay, migrations и retention.
- Frontend: полный `tsc -b --force`, **53 целевых теста**, обе app/public сборки, EXIT=0. TypeScript baseline 57 ошибок устранён; прежние красные логи сохранены как история, а не текущий результат.
- Compiled RU/EN mock browser: **14 passed**, включая генерацию/preview/approval, другую таблицу, poll и CSV; восстановление checking/needs_fix/ready_approval, возврат к утверждённой версии и переход от старого deep link к намеренному новому запуску.
- Настоящий staging Today API/UI: **6 passed** — по три размера экрана с cookie-входом и действующим production bearer-входом. Проверены сохранение предпочтения после reload, изоляция чужого бизнеса/сети, отсутствие серьёзных accessibility ошибок и overflow.
- Настоящий staging compiled API: **10 preview / 5 runs**, compile/run replay, protected pointer, actual runner/output, `runtime_ai_calls=0`. Источник для этого smoke задан вручную в internal-only режиме. Он не доказывает качество генерации модели и не считается реальным пользовательским пилотом.
- Настоящий staging compiled UI: **3 passed** (desktop, Android 360, Telegram 393); проверен конкретный выбранный run: 3 строки, 1 принятая, duplicate на строке 2 и required на строке 3. Скачан CSV именно этого отчёта; форма и причины ошибок помещаются в экран. Итоговый лог — `raw/staging-compiled-browser-table-final.txt`.
- Реальный Docker runner: source execution, подпись, nonce, hash, запрет импорта/доступа к `/proc`, ограничения времени/вывода и output schema. Дочернее исполнение не имеет DB/provider credentials; образ закреплён фактическим image ID в изолированной сети.
- Полная staging Alembic-цепочка достигла **20260906_012**. **13 runtime helpers** проверены на ней с запрещёнными CREATE/ALTER/DROP; savepoint вызывающей транзакции сохранён. Узкие pytest fixtures и полный staging-chain proof обозначены отдельно.

- Откат: прежний backend `ffc54c19` на новой схеме `20260906_012` с сохранённым новым schema-check startup — health/login/Today 200, EXIT=0.
- Частичный deploy: реальный Docker startup со скриптами через read-only mounts прошёл в новом и пересозданном контейнере. Compose-контракт проверяет default/override migration mode и наследование отдельными worker.
- Независимый review миграций обнаружил и закрыл неправильный переход `delivered`: теперь `waiting_reply`, как в прежней канонической миграции; реальная PostgreSQL regression дала ожидаемое падение до исправления и 2 успешных теста после.

Доказательства: [evidence](../.agent/tasks/localos-plan-20260906/evidence.md), [финальная независимая оценка](../.agent/tasks/localos-plan-20260906/raw/review-package-final.md). Старый `raw/review-package.md` описывает промежуточную версию и не является текущим verdict. Последние изменения compiled UI проверены повторно сборкой и browser-тестами.

Production frontend собран отдельно с выключенными cookie-auth и compiled preview; хеши исходников и обеих сборок сохранены в `raw/frontend-production-build-proof.json`. Скрипт упаковки проверяет их и соответствие исходников локальному commit. Результат упаковки — `outputs/localos-release-20260906/release-manifest.json`, архив `payload.tar.gz` и отдельный `compose.patch`; manifest фиксирует точный commit и SHA-256. Архив не заменяет push или production-выпуск.

## Ограничения и следующий выпуск

[Compiled-контракт](LOCALOS_COMPILED_TABLE_PILOT.md) описывает версии 1/2, независимые fixtures, 7-дневный online срок рабочих таблиц, отдельное хранение примеров, quotas и lifecycle. Транспортный HMAC/digest не называется аппаратной аттестацией. Registry manifest digest и фактический production-контейнер проверяются отдельно перед включением пилота.

Production read-only preflight: Alembic **20260905_004**, активных/ожидающих agent runs в момент проверки нет, `AGENT_ASYNC_RUNS_ENABLED=true`. Today/compiled/migration-mode env не заданы; это отсутствие переменных, а не измеренное выключение. Host Git checkout `c728015c…` отличается от исходного локального commit: при частичных выпусках источник истины — backup и hashes live файлов, а не один `git rev-parse` на сервере.

[Состав выпуска и порядок отката](LOCALOS_RELEASE_2026-09-06.md) подготовлены. 48 затронутых source/migration/startup путей внутри app сверены без расхождений с ожидаемой исходной версией. Новые production-миграции пока не разрешены отдельным подтверждением для этого пакета. Пакет содержит также одноразовые idempotent seeds и reconciliation `prospectingleads.pipeline_status` для legacy/unprocessed записей; заданные прочие ручные статусы сохраняются. Выпуск требует свежего DB backup, сверки live diff, последовательного обновления app/worker/telegram и проверки отката. Compiled execution/preview, activity/proposals не включаются автоматически; роли worker и DB-права не переключаются глобально.

Список остаточных DDL и границ находится в `raw/ddl-inventory.md`. Глобальная смена legacy `DatabaseManager.close()` не выполнялась. В R3 следующим отдельным переносом проверяется Google Sheets `update_cells`: claim → commit → provider → fenced finish, неоднозначный исход переводится на сверку без слепого повтора. `append_row` нельзя считать идемпотентным после сбоя внешнего POST.
