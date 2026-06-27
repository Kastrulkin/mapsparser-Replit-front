# Agents Product UI Audit

## Purpose

This is the working audit for `/dashboard/agents`.

The current target is no longer "make the cockpit clearer". The canonical
interface model is now defined in
`docs/AGENTS_INTERFACE_MODEL_COMPILED_AI.md`: agents are AI employees, not
workflows.

This audit is intentionally strict. The current implementation has useful
pieces, but the information architecture is still partially inherited from the
old workflow/debugger model.

## Current Status

Status: `partially done`

What is already moving in the right direction:

- the page has user-facing blocks such as today, attention, agents, overview,
  history, scenario, and settings;
- the first layer has some business-language copy;
- approvals are explained as human decisions;
- technical execution is mostly behind secondary surfaces;
- Google Sheets can be used as the reference proof scenario;
- the copy guard exists and should remain part of CI.

What is not done:

- the page is still structurally a selected blueprint/detail interface;
- the user still sees too many equal-weight places to act;
- create-to-running is not yet an automatic guided path;
- the healthy state is still too detailed;
- settings, versions, cost, learning, and diagnostics can still feel like the
  product model instead of a second layer;
- history still risks becoming execution review rather than a business story.

## Screen Job

The agents area helps a business user manage AI employees.

It must answer:

- what needs my attention today;
- which employees exist;
- whether the selected employee works;
- what happened last time;
- what I should do now.

It is not primarily a raw blueprint editor, migration console, OpenClaw panel,
provider console, or action ledger.

## Required First-Layer Answers

Every first-layer agent screen must make these answers obvious:

- what this agent does;
- whether it is working;
- what happened last time;
- what the user should do now.

The first layer must not require understanding blueprint JSON, OpenClaw,
capability names, provider executors, migration states, raw traces, or billing
ledgers.

## Target Information Architecture

The future implementation should follow the canonical model:

- `Главная агентов`: "Что сегодня требует моего внимания?"
- `Мои сотрудники`: "Какие ИИ-сотрудники у меня есть?"
- `Карточка агента`: "Работает ли этот агент?"
- `Проверка результата`: "Согласен ли я использовать результат?"
- `История`: "Что агент делал раньше?"
- `Настройки`: "Что можно изменить, если мне нужно?"

This target replaces the older cockpit/manage/debugger mental model. Current
tabs and blocks may remain during migration, but they must move toward this
structure.

## Audit Table

| Requirement | Status | Evidence |
| --- | --- | --- |
| Canonical employee model exists | done | `docs/AGENTS_INTERFACE_MODEL_COMPILED_AI.md` defines the new product contract. |
| Product design rules reference the employee model | done | `DESIGN.md` includes "Agents Are Employees, Not Workflows". |
| Current screen answers some first-layer questions | partially done | Overview and agent cards expose task, status, last run, and next action, but the surrounding IA still feels like object management. |
| One dominant CTA per state | not done | Multiple buttons remain visible across overview, settings, scenario, history, and cards. |
| Create-to-running path is guided | partially done | Post-create handoff exists, but the user can still fall back to searching and mode switching. |
| Healthy state gets smaller | not done | Healthy agents still show confidence, activation, management, cost, and secondary controls in the ordinary layer. |
| History is a business story | partially done | Business history exists, but technical run review and preview details still compete with it. |
| Internal terms hidden from ordinary layer | partially done | Copy guard exists, but terms and concepts such as preview, version, provider, and advanced execution still leak through secondary ordinary surfaces. |
| Advanced/debug secondary | partially done | Superadmin tools are gated, but diagnostics, versions, learning, and technical details still influence normal IA. |
| Google Sheets proof flow is canonical | partially done | Runtime smoke and docs exist; the user-facing flow still needs the employee-model UI. |

## First-Layer Copy Guard

Avoid these terms in the ordinary user layer:

- `blueprint`
- `runtime`
- `capability`
- `provider`
- `execution`
- `context`
- `DSL`
- `JSON`
- `active version`
- `migration`
- `legacy`
- `credits`
- `raw logs`
- `OpenClaw`
- `ActionOrchestrator`
- `provider executor`
- `Preview run`
- `workflow debugger`

Allowed places:

- advanced;
- support export;
- raw trace/details;
- developer docs;
- source code, API fields, and type names.

Run this gate before shipping changes to the agents screen:

```bash
scripts/ci_gate_product_ui.sh
```

For an explicit visual artifact while local Vite is running:

```bash
python3 scripts/smoke_agents_product_ui_mock.py --screenshot /tmp/localos-agents-cockpit-mock-full.png
```

## Future Implementation Acceptance

The next `/dashboard/agents` implementation should be accepted only if:

- the first layer does not show runtime, blueprint, capability, or provider;
- after creating an agent, the exact agent opens automatically;
- the user never has to find the agent they just created;
- every state has one primary CTA;
- every agent card answers only the four core questions;
- history reads like a story, not an execution log;
- advanced/debug exists but does not dominate;
- a healthy agent is visually simpler than a problematic agent;
- Google Sheets trips is implemented as the first reference proof flow.

## Next Hardening Checks

- Re-audit the real `/dashboard/agents` first viewport against
  `docs/AGENTS_INTERFACE_MODEL_COMPILED_AI.md`.
- Test the create -> connect -> test -> result -> approve -> enable -> running
  path with the Google Sheets trips reference scenario.
- Check long Russian agent names, long descriptions, no-agent empty state, many
  agents, missing connection, failed run, and pending decision states.
- Verify that advanced/debug details are reachable but never the default
  explanation of the product.
