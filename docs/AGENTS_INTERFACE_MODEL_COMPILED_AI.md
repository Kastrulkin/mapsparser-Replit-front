# Agents Interface Model: Compiled AI

## Purpose

This document is the product contract for the LocalOS agents interface.

LocalOS agents are not workflows, automations, blueprints, provider routes, or
runtime objects in the user interface. For a business owner, they are
AI employees: hired to do a job, checked before external action, and trusted
only after their work is visible.

The backend may still use compiled plans, versions, capabilities, providers,
runs, artifacts, approvals, and observability. Those are implementation
details. The first user-facing layer must be organized around the user's
question and the next safe action.

Current UI changes on `/dashboard/agents` are an intermediate state. They
should not be reverted, but they are not the final model: the page still
inherits too much structure from the old workflow/debugger interface.

## Core Principle

Every agents screen answers one user question and always gives four answers:

- what this agent does;
- whether it is working;
- what happened last time;
- what I should do now.

If a screen cannot answer these four questions without technical terms, the
screen is not ready.

## Information Architecture

### Agents Home

User question: "What needs my attention today?"

First layer:

- work completed today;
- results waiting for a human decision;
- employees that cannot work because something is missing;
- one recommended next action.

This is not a dashboard of runtime metrics. It is an attention surface.

### My Employees

User question: "Which AI employees do I have?"

First layer:

- employee name;
- job in one sentence;
- status in business language;
- last result;
- main action.

The list is not a table of backend objects. It is a staff list.

### Agent Card

User question: "Is this employee working?"

First layer:

- job;
- status;
- last result;
- next run or next expected moment;
- single main CTA.

When the agent is healthy, this screen must be short. More detail appears only
when there is a problem, a result to approve, or the user opens a secondary
layer.

### Result Review

User question: "Do I agree to use this result?"

First layer:

- what the agent prepared;
- why human confirmation is needed;
- what happens if I approve;
- what happens if I reject;
- one approve action and one secondary reject action.

This is not an approval log. It is a decision screen.

### History

User question: "What did the employee do before?"

History is a story, not an execution log.

Good history:

```text
Read rows from the trips table
Prepared one trip result for April 20
Stopped before sending or publishing
Waits for your decision
```

Bad history:

```text
Input
Extract
Planner
Context
Output
```

Technical execution may exist behind "Show technical execution", but it must
not be the default history.

### Settings

User question: "What can I change if I need to?"

Settings is the second layer for:

- connections;
- schedule;
- limits;
- tone and style;
- result format;
- version/history controls;
- diagnostics and advanced tools.

Settings must not be the main way to understand whether the agent works.

## Mandatory Create-To-Running Path

After creating an agent, the user must never have to find it in the general
list.

The required flow is:

1. Create the agent in natural language.
2. Open this exact agent automatically.
3. Show one next step.
4. Connect the missing service if needed.
5. Run a test.
6. Show the prepared result.
7. Ask for confirmation when needed.
8. Enable the agent.
9. Show a simple running state.

Each step automatically moves the user to the next screen or state. If the
system cannot continue, it must say why in business language and show one
primary action.

## Text Wireframes

### My Employees

```text
ИИ-сотрудники
Сегодня: 2 результата подготовлено, 1 ждёт решения

[Нужно решение]
Мария, помощник по поездкам
Читает таблицу поездок и готовит сообщение владельцу
Последний раз: подготовила поездку за 20 апреля
CTA: Проверить результат

[Работает]
Антон, помощник по отзывам
Готовит ответы на новые отзывы
Последний раз: вчера подготовил 3 ответа
Следующий запуск: завтра в 09:00
CTA: Открыть
```

### Agent Working Normally

```text
Мария, помощник по поездкам
Работает

Что делает:
Читает таблицу поездок и готовит одну поездку для проверки.

Последний результат:
Подготовила поездку за 20 апреля.

Следующий запуск:
По вашему запуску или по расписанию, если оно включено.

CTA: Открыть историю
```

The screen ends here unless the user opens details.

### Missing Connection

```text
Мария, помощник по поездкам
Не хватает доступа

Что делает:
Читает Google таблицу с поездками.

Что мешает:
LocalOS не может прочитать таблицу, пока Google Sheets API или доступ к таблице
не готов.

CTA: Подключить Google Sheets
Secondary: Показать техническую причину
```

### Ready For Test

```text
Мария, помощник по поездкам
Готова к тесту

Что произойдёт:
LocalOS прочитает таблицу, выберет подходящую поездку и подготовит результат.
Ничего не будет отправлено наружу.

CTA: Запустить тест
```

### After Test

```text
Тест завершён

Агент прочитал:
Таблицу поездок.

Агент подготовил:
Поездку за 20 апреля.

Что дальше:
Проверьте результат перед использованием.

CTA: Проверить результат
```

### Result Waiting For Confirmation

```text
Нужно ваше решение

Что подготовил агент:
Краткий результат по поездке за 20 апреля.

Если принять:
Результат можно использовать в следующем шаге.

Если отклонить:
Агент остановится, результат не будет использован.

CTA: Принять
Secondary: Отклонить
```

### Error

```text
Мария, помощник по поездкам
Не смогла выполнить задачу

Что произошло:
Google Sheets API выключен в проекте Google Cloud.

Что сделать:
Включить Google Sheets API и снова запустить тест.

CTA: Открыть Google Cloud
Secondary: Показать техническую причину
```

### Settings And Advanced

```text
Настройки Марии

Основное:
- Google таблица
- Когда запускать
- Что считать результатом
- Где просить подтверждение
- Голос и стиль

Advanced:
- версии
- техническое выполнение
- raw payload
- support export
```

## Hidden From The Ordinary Layer

The ordinary user layer must not expose these terms as product structure:

- blueprint;
- runtime;
- capability;
- provider;
- execution;
- context;
- DSL;
- JSON;
- active version;
- migration;
- legacy;
- cost/credits;
- raw logs.

These may appear only in advanced, diagnostics, support export, developer docs,
or source code.

## Status Language

Use statuses that explain the situation:

- `Работает`;
- `Готов к тесту`;
- `Ждёт вашего решения`;
- `Не хватает подключения`;
- `Нужно включить`;
- `Не смог выполнить задачу`;
- `Остановлен`.

Do not use statuses such as:

- `draft`;
- `runtime_error`;
- `waiting_approval`;
- `not runnable`;
- `v2`;
- `0 sources`.

## Reference Proof Flow: Google Sheets Trips

The first reference flow for this interface model is:

```text
ИИ-сотрудник читает таблицу поездок,
выбирает поездку за 20 апреля,
готовит результат,
останавливается перед внешним действием.
```

This flow proves the UI model and the custom-agent runtime without requiring
Telegram or WhatsApp delivery. The user-facing proof is not "provider read
performed"; it is:

- the employee understood the task;
- the employee read the table;
- the employee prepared the trip result;
- the employee stopped before external action;
- the user knows exactly what to do next.

## Future Implementation Acceptance

The future `/dashboard/agents` implementation must satisfy these checks:

- the first layer does not show runtime, blueprint, capability, or provider;
- the newly created agent opens automatically;
- the user never searches for the agent they just created;
- each screen has one primary CTA;
- each agent card answers only the four core questions;
- history reads like a story;
- advanced/debug exists but does not dominate;
- a healthy agent produces a smaller interface than a problematic agent;
- Google Sheets trips becomes the first canonical proof flow.
