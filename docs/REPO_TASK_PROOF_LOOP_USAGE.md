# Repo Task Proof Loop: Как вызывать и как это работает

## Где установлен
- Skill: `agents/skills/repo-task-proof-loop`
- Wrapper: `scripts/proof_loop.sh`

## Как вызывать (практично)

### 1) Инициализировать задачу (рекомендуется для крупных задач)
```bash
scripts/proof_loop.sh init parsing-validity-20260325 "Довести качество парсинга до KPI и стабилизировать retries/proxy flow"
```

### 2) Инициализировать из task-файла
```bash
scripts/proof_loop.sh init-file parsing-validity-20260325 docs/tasks/parsing-validity.md
```

### 3) Проверить bundle
```bash
scripts/proof_loop.sh validate parsing-validity-20260325
```

### 4) Посмотреть статус
```bash
scripts/proof_loop.sh status parsing-validity-20260325
```

## Алиасы в чате
- `Автономная разработка` -> proof-loop режим (init или продолжение текущего TASK_ID)
- `Статус автономной разработки` -> `scripts/proof_loop.sh status <TASK_ID>`
- `Проверка автономной разработки` -> `scripts/proof_loop.sh validate <TASK_ID>`

## Что происходит внутри
После `init` создаётся папка:

`.agent/tasks/<TASK_ID>/`

И в ней:
- `spec.md` (замороженная постановка + AC1..ACn)
- `evidence.md`, `evidence.json` (доказательства по AC)
- `verdict.json` (вердикт верификатора)
- `problems.md` (что чинить при FAIL/UNKNOWN)
- `raw/*` (сырые артефакты: build/test/lint/screenshot)

Также ставятся project subagents для Codex:
- `.codex/agents/task-spec-freezer.toml`
- `.codex/agents/task-builder.toml`
- `.codex/agents/task-verifier.toml`
- `.codex/agents/task-fixer.toml`

## Рабочий цикл
1. `init` задачи.
2. Freeze spec (`spec.md`) с AC.
3. Build.
4. Evidence (заполняем `evidence.*` + `raw/*`).
5. Fresh verify (новый verifier, не тот же исполнитель).
6. Если FAIL/UNKNOWN: минимальный fix -> снова fresh verify.

## Важно по вашему проекту
- Инициализация запускается в безопасном режиме: `--guides none`.
- Это значит, текущий `AGENTS.md` не перезаписывается.
- Tool добавляет процессную дисциплину, но не заменяет ваш deployment/runbook.
