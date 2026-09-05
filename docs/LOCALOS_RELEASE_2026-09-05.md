# LocalOS — реализация плана от 5 сентября 2026

Статус: первый этап выпущен в production 5 сентября 2026 с согласия пользователя,
резервной копией и проверкой реальных API. Это первая
проверяемая поставка из [общего плана](LOCALOS_IMPLEMENTATION_PLAN_2026-09-05.md).
Полный план ещё не закрыт: перенос legacy backend и подключение SDK требуют
дальнейших этапов. Четыре согласованные миграции применены до `20260905_004`.

## Что работает в текущем коде

| Область | Результат | Граница готовности |
| --- | --- | --- |
| U1: навигация | Постоянная главная «Сегодня», прямые ссылки на основные направления, «Пути роста» во втором слое | Production; desktop/mobile проверены локально на тестовых API-ответах |
| U2: «Сегодня» | Реальные контентные материалы, коллаборации, запуски; срочность, личный приоритет, сохранение прежних jobs/results, ошибки отдельных источников | Production; существующий общий web/Mini App builder расширен совместимо, real API smoke пройден |
| U3: предпочтения | user × business/network, revision/CAS, ручной выбор, accept/decline/snooze/opt-out/undo; изменение только по согласию | Сбор и предложения выключены по умолчанию; нужен период наблюдения |
| U3: сигналы | Подтверждённые сервером content/journey/collaboration/compiled-команды, dedup; client observations, demo, admin и impersonation не повышают интерес к направлению | Пилотные пороги: 14 дней, минимум 3 активных дня и 5 действий, доля 60%, устойчивость между двумя суточными расчётами |
| B1: транзакции/доступ | AuthContext, явный UnitOfWork, rollback на ошибке, общий доступ Content Voice с network membership | Старый close-commit сохранён для не переведённых callers; это не глобальная миграция |
| B1: схема | Убран runtime DDL average-ticket и analytics read path | Остальной DDL перечислен в [инвентаризации](RUNTIME_DDL_INVENTORY_2026-09-05.md) |
| B2: задания | Operator lease token, heartbeat/recovery и запрет завершения устаревшей попыткой; reclaim agent queue с SKIP LOCKED; фиксированная версия события и связь event → run | Старые agent runs пока удерживают длинную транзакцию; полная унификация владения отложена |
| B2: процессы | Опциональные parser, agent, operator, dispatcher, maintenance workers | Default all совместим; role split требует согласованного включения compose-фрагмента |
| B2: внешние действия | Maton-ветка проходит ActionOrchestrator и стабильный idempotency key | Текущее действие создаёт запрос; автоматическая provider-отправка не заявляется выполненной |
| A1–A3: compiled script | Description → Python source → независимый пользовательский пример → sandbox preview → approval → queued run без LLM | Internal pure-transform пилот. Данные передаются в JSON; tenant-aware чтение через SDK ещё отсутствует |
| U4: рабочие сценарии | Сохранение Operator при временной ошибке, очистка при 403/404; точные ссылки content/influencer/agent; lazy-loading партнёрской аналитики; проверка выбранных черновиков | Пакет подтверждает черновики, а отправитель и время выбираются позже при ручной отправке |

Приоритет не меняет порядок меню и не перенаправляет с `/dashboard`. GET
предпочтений не создаёт записи. Новый контент не переставляет интерфейс до
обновления пользователем. Частичная ошибка источника показывается как ошибка,
а не нулевая очередь. Срочные решения сохраняются выше выбранного направления.

## Контракт compiled scripts

Скрипт — настоящий сохраняемый Python source, а не фиксированная функция вместо
сгенерированной программы. Код, manifest и fixtures входят в hash. Manifest
закрепляет runtime/image и пустой список зависимостей. Модель не выбирает digest
исполнителя и не может назвать свой fixture пользовательским.

Публичное создание обычной версии удаляет присланные клиентом `compiled_*` поля.
Специализированный compile создаёт только проверяемый candidate. Preview
исполняет исходник и сравнивает результаты с ожидаемыми примерами; approval
связан с hash артефакта и evidence. Запуск повторно проверяет approval, hash,
схемы и образ; rollback не возвращает версию несовместимого runtime.

Поддерживается ограниченный JSON Schema subset: type, properties, required,
additionalProperties, items, enum, размеры строк/массивов и числовые границы.
Input проверяется до исполнения; output проверяется runner и повторно host.
Неизвестные schema keywords отклоняются. Новые входные данные запуска не требуют
новой генерации; изменение программы требует новой проверки и утверждения.

Runner — отдельный internal-only контейнер: readonly root, ограниченные CPU,
память, PID, время и stdout, отдельный UID дочернего процесса, без DB/provider
credentials и Docker socket. Import, прямой network/filesystem и runtime AI
недоступны. Запросы защищены timestamp/nonce/HMAC. Digest проверяется как
конфигурационная привязка образа; это не аппаратная remote attestation.

Пилот возвращает результат в существующий журнал agent_runs. Он пока не читает
Google Sheets/LocalOS самостоятельно, не сохраняет доменные изменения через SDK
и не отправляет сообщения. Существующие DSL/AI-агенты не мигрируются автоматически.
Отдельная проверка изоляции требуется до широкой многопользовательской эксплуатации.

## Миграции и совместимость

Одна последовательная ветка Alembic после `20260902_002`:

1. `20260905_001`: lease Operator и индекс running jobs.
2. `20260905_002`: immutable script artifact, preview и approval fields версии.
3. `20260905_003`: today_preferences и происхождение/dedup product events.
4. `20260905_004`: event key, pinned version и отдельные связи события с запусками.

Изменения расширяют существующую схему. Старые blueprint/run/draft сущности
переиспользуются. Изолированный тест прогоняет текущую миграционную цепочку на
чистом PostgreSQL; дополнительные PostgreSQL-тесты проверяют leases и preferences.

У partnership draft approval теперь обязателен `expected_review_digest` из
актуального GET drafts. Backend блокирует устаревший текст, контакт, канал или
revision с `409`; отсутствие review возвращает `400`. Web, bulk, Mini App и
batch helper передают digest. Старому клиенту нужно обновить список/интерфейс.
Это согласование черновика, не разрешение отправки. Частичный bulk-успех
показывает точное количество, неуспешные письма остаются для повторной проверки.

## Проверки

- Backend: обязательный `scripts/ci_gate_localos_plan.sh`, изолированные PostgreSQL,
  фикстуры провайдеров, auth/scope, rollback, queue, approval, schema, dedup.
- Frontend: targeted Vitest, dashboard/public builds, scoped TypeScript gate.
- Browser: Chromium desktop и Android 360px, 4 сценария, замоканные API;
  это не staging-проверка реальных интеграций.
- Docker: реальное исполнение исходника, сравнение fixtures, неверные подпись/hash,
  nonce replay, timeout, import/network, попытка доступа к `/proc`, output limit,
  неправильные type/required/enum/maximum результата и успешная следующая задача.
- Повторяемость: фиксированный hash seed дочернего Python; один исходник и
  одинаковый input дают одинаковую последовательность даже при использовании set.
- Общий TypeScript baseline HEAD: 59 ошибок. Исправлены две ошибки Operator;
  осталось 57 прежних ошибок. CI проверяет затронутые модули полным compiler run,
  а также блокирует любую новую сигнатуру/увеличение числа ошибок в остальных
  файлах относительно проверенного baseline. Это не успешный global typecheck.

Итог: **228 backend tests, 35 frontend tests**, обе production-сборки, scoped
TypeScript gate и `git diff --check` прошли. Chromium: **4 сценария** на desktop
и mobile с тестовыми API-ответами. Дополнительный реальный Docker proof прошёл на
локальном образе `sha256:85c1892c21a8bbeae3d71ea98a723e435f10c227f8e3105ded57733b674d4101`.
Логи и контрольные суммы текущих файлов: `outputs/localos-release-20260905/`.
Этот image ID относится к локальной проверке; production-образ собирается под
свою платформу и закрепляется отдельно до компиляции рабочих артефактов.
Production API smoke пройден; подробности ниже. Метрики queue/UI latency и
визуальная проверка production на реальных клиентах пока не сняты.

## Production-выпуск 5 сентября

Выпуск `20260905-today-134536` применён после явного согласия пользователя.
Резервная копия базы завершена и проверена 13:56:26 UTC: custom-format pg_dump,
проверка списка и полное чтение через pg_restore без восстановления данных.
Размер — 1 712 458 047 байт, SHA-256:
`77ec08a24cc9c9b6b12b532e91c974706093f71d11577e24240c3b81ca6d6d57`.
Копия базы и архив прежних исходников/интерфейса находятся на сервере в
`/opt/seo-app/releases/20260905-today-134536/backup/` с ограниченными правами.

Четыре миграции применены под advisory lock до `20260905_004`.
Обновлены только подготовленные source/migration файлы и frontend; прежние
assets сохранены для открытых вкладок. Перезапущены app, worker и Telegram-бот.
Сбор поведенческих сигналов, предложения приоритета, compiled preview/execute
остаются выключены; ручной приоритет «Сегодня» включён, worker работает в роли all.

Первая проверка выявила `500` вместо `403` для чужого business scope: fallback
SQL получал семь параметров для пяти placeholders. Исправлены параметры и тест,
проверяющий их количество. Дополнительно прошли 25 целевых тестов; исправление
выпущено, HTTP готов с 14:49:08 UTC. После исправления:

- 258 контрольных сумм source/migrations/frontend внутри app совпали с итоговым
  manifest; исправленный модуль проверен также в worker и Telegram-боте.
- Все сервисы работают; в проверенном окне после исправления нет ERROR/Traceback.
- Публичные `/`, `/dashboard`, `/dashboard/content`, `/dashboard/influencers`
  и assets новой сборки отвечают `200`.
- 12 GET-запросов реального API прошли: business/network Today и preferences,
  стабильная revision при повторном чтении, три проверки чужого бизнеса (`403`),
  один существующий blueprint и его legacy-версия. Новые сессии и тестовые
  бизнес-данные для проверки не создавались.

Итоговые доказательства: `outputs/localos-release-20260905/production-evidence.json`,
`production-api-smoke.json` и `production-final-manifest.json`. Исходный manifest
локального тестирования сохраняет состояние до найденного production hotfix.
Проверка браузера на реальном production не завершена: инструмент управления
нативным браузером завис. Desktop/mobile evidence выше относится к локальным
проверкам с тестовыми API, а не к этой production-проверке.

При откате сначала вернуть прежние source/frontend из защищённого архива и
перезапустить затронутые сервисы. Расширяющую схему и новые данные сохранять;
не выполнять downgrade или восстановление базы поверх новых данных автоматически.

## Включение и откат

1. Перед любым production schema/data изменением — согласование и backup по
   [AGENTS.md](../AGENTS.md). Серверные команды выполнять из `/opt/seo-app` в tmux.
2. Подготовить snapshot текущих source/dist, Compose и DB; проверить Alembic head,
   совместимость текущего deploy и применить четыре расширяющих миграции.
3. Выпустить app/worker из одного согласованного исходника и frontend dist.
   `docker-compose.today.yml` включает настройку главной, но оставляет сбор и
   предложения выключенными. Старый экран возвращается отключением
   `LOCALOS_TODAY_PERSONALIZATION_ENABLED`; старое меню — build flag
   `VITE_GROWTH_PATHS_NAVIGATION_ENABLED=false`.
4. Role split включать отдельным `docker-compose.workers.yml`: старый worker
   становится parser, отдельные процессы получают остальные роли. Проверить
   отсутствие дублирования scheduler и обслуживания до включения dispatch.
5. Для script preview дополнительно собрать и закрепить проверенный runner image,
   настроить shared secret и внутренний URL `http://compiled-script-runner:8091`
   для app и выполняющего worker. Использовать вместе base + workers + today +
   `docker/compiled-script-runner/compose.fragment.yml`. Включать preview отдельно
   от `COMPILED_SCRIPT_EXECUTE_ENABLED`; frontend pilot требует
   `VITE_COMPILED_SCRIPT_PREVIEW_ENABLED=true` при сборке.
   Выключение execute блокирует и общий admission, и запуск уже поставленного
   compiled-задания на worker. Такое задание получает явную ошибку отключённого
   исполнения; после включения требуется осознанный повтор.
6. Показ предложений включать после наблюдения и проверки качества сигналов;
   сбор (`LOCALOS_TODAY_ACTIVITY_ENABLED`) и показ
   (`LOCALOS_TODAY_PROPOSALS_ENABLED`) независимы.
7. После выпуска: compose ps → app logs → HTTP health → целевые API →
   desktop/mobile на реальных разрешённых данных. Откат отключает новые admission
   и UI flags, сохраняет журналы/артефакты/предпочтения; не удаляет данные миграций.

## Что остаётся в общем плане

- Продолжить перенос runtime DDL с доказанным schema parity, затем разделить
  migrator/runtime DB roles. Не отключать DDL у runtime роли до завершения переноса.
- Перевести legacy agent queue на короткие транзакции с полным lease/fencing;
  унифицировать admission и восстановление всех внешних действий. Добавить
  provider/business concurrency limits и сверку неоднозначных отправок.
- Продолжить B3-декомпозицию по доменам; устранить обратные импорты/globals по
  одному сценарию. Текущие AuthContext/UnitOfWork не означают завершение этой работы.
- Реализовать tenant-aware compiled SDK/broker для разрешённого чтения и отчётов,
  checkpoints/replay, затем предложений эффектов; добавить второй пилот и
  перенос каждой старой автоматизации с пользовательским утверждением.
- Довести nontechnical конструктор источников, единый lifecycle редактирования,
  пакетное approval с закреплёнными sender/time/limits и все локали/состояния.
- Получить staging evidence, baseline эксплуатационных метрик и ограниченный
  пользовательский пилот для пока выключенных возможностей. Первый production
  этап выпущен; полный план закрывать после оставшихся этапов.
