# Repo Task Proof Loop: План безопасного внедрения в LocalOS

## Цель
Взять из `repo-task-proof-loop` то, что усиливает дисциплину автономной разработки, не ломая текущие правила проекта в `AGENTS.md`.

## Что внедряем
- Repo-local артефакты задачи: `.agent/tasks/<TASK_ID>/...`
- Валидацию и статус артефактов (`init/validate/status`)
- Роль свежей независимой верификации (отдельный verifier-проход)
- Явные AC-критерии и доказательства по каждому AC

## Что не внедряем как есть
- Автоматическое перезаписывание `AGENTS.md`/`CLAUDE.md` managed-блоками
- Ожидание, что `freeze/build/verify/fix/run` уже реализованы как CLI (в пакете это сценарии, не полноценные команды)
- Любые шаги, конфликтующие с текущим runbook (Docker/Postgres, hot-sync, проверка через `docker compose ps/logs/curl`)

## Почему это полезно для вас
- Меньше “ложных PASS”: появится жесткая связка `AC -> evidence -> fresh verify`
- Быстрее разбор регрессий: артефакты лежат в репо и видны в истории
- Удобнее автономный режим: можно продолжать задачу после обрыва с четким состоянием

## Риски и как их снять
- Риск: конфликт с текущим `AGENTS.md`
  - Мера: не давать скрипту править `AGENTS.md`, сначала запускать с `--guides none`
- Риск: “бумажная” дисциплина без реальных проверок
  - Мера: для каждого TASK_ID обязательны `validate` + список команд в `evidence.json`
- Риск: шум в репозитории
  - Мера: использовать только для нетривиальных задач (бэкенд-фичи, миграции, парсинг/прокси, очереди)

## План внедрения (3 этапа)

### Этап 1. Пилот без изменения глобальных гайдов
1. Добавить skill в репозиторий в локальную папку инструментов (например, `agents/skills/repo-task-proof-loop`).
2. Прогнать инициализацию на 1 пилотной задаче:
   - `python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py init --task-id parsing-stability-pilot --task-text "..." --guides none --install-subagents codex`
3. Проверить:
   - `python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py validate --task-id parsing-stability-pilot`
   - `python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py status --task-id parsing-stability-pilot`

Критерий выхода:
- `valid=true`, структура `.agent/tasks/parsing-stability-pilot/` создана, текущие project-rules не затронуты.

### Этап 2. Интеграция с вашим автономным брифом
1. В `agents/autonomous_development_brief.md` добавить правило:
   - для задач уровня “крупная/рискованная” сначала создать TASK_ID и артефакты proof-loop.
2. Минимальный обязательный цикл:
   - freeze spec (AC1..ACn)
   - build
   - evidence
   - fresh verify
   - fix (если нужно) -> fresh verify
3. Для серверных задач сохранить ваш текущий порядок проверки:
   - `docker compose ps` -> `docker compose logs` -> `curl -I` -> endpoint smoke.

Критерий выхода:
- На 2-3 задачах подряд есть полный набор артефактов + финальный верификатор PASS.

### Этап 3. Операционализация
1. Ввести правило “DoD только с verifier PASS и валидным bundle”.
2. Добавить метрики в weekly review:
   - доля задач с полным bundle
   - доля задач с повторным fix-циклом
   - доля ложных PASS (пойманных после merge/deploy)
3. При необходимости подключить managed guide-блоки только после ручного ревью.

Критерий выхода:
- Стабильно >=80% крупных задач идут через proof-loop без замедления релизов.

## Рекомендуемый scope для старта
- Включать: парсинг/прокси, очереди, outreach-пайплайн, миграции
- Не включать: мелкие UI-фиксы, текстовые правки, однофайловые косметические изменения

## Операционный шаблон TASK_ID
- Формат: `<area>-<goal>-<yyyymmdd>`
- Примеры:
  - `parsing-validity-20260325`
  - `apify-connector-hardening-20260325`
  - `outreach-send-guardrails-20260325`

## Быстрые команды (копипаст)
```bash
# init (без правки AGENTS/CLAUDE)
python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py init \
  --task-id parsing-validity-20260325 \
  --task-text "Довести качество парсинга и верификации до целевых KPI" \
  --guides none \
  --install-subagents codex

# validate
python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py validate \
  --task-id parsing-validity-20260325

# status
python3 agents/skills/repo-task-proof-loop/scripts/task_loop.py status \
  --task-id parsing-validity-20260325
```

## Решение по внедрению
Рекомендуется внедрять в режиме **“process overlay”**: поверх текущих правил проекта, без их замены.
