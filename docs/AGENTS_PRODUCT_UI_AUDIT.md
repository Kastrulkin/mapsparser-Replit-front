# Agents Product UI Audit

## Purpose

This document is the working audit for `/dashboard/agents`.

It translates the product canon from `PRODUCT.md` and the design process from
`DESIGN.md` into concrete checks for the agents screen. The goal is to keep
the screen moving toward a product cockpit instead of drifting back into a
workflow/debugger UI.

## Screen Job

The agents screen helps a business user understand which agents exist, what
needs attention now, and what the next safe action is.

It is not primarily a raw blueprint editor, migration console, OpenClaw panel,
or action ledger.

## Current Information Architecture

- `Cockpit`: header actions, summary cards, agent list, selected agent overview.
- `Create`: natural-language dialog, clarification questions, future-agent
  review, approximate cost, safe creation.
- `Manage`: logic, runs, learning/versioning, connections, voice and style.
- `Advanced`: runtime trace, raw versions, action ledger, billing/support
  details, visible only to superadmin/debug users.

## Required First-Layer Answers

The first layer must answer:

- What agents exist?
- Which agent is selected?
- What does the selected agent do?
- What is the next step?
- Is anything waiting for a human decision?
- What data/connections are missing?
- What happened in the last run?

The first layer must not require understanding blueprint JSON, OpenClaw,
capability names, provider executors, migration states, or raw runtime traces.

## Audit Table

| Requirement | Status | Evidence |
| --- | --- | --- |
| Product canon exists | done | `PRODUCT.md` defines Agent, Persona, Blueprint, Run, Approval, OpenClaw boundary. |
| Design process exists | done | `DESIGN.md` defines `audit -> distill -> shape -> implement -> harden -> polish`. |
| Agent screen defaults to overview | done | `workspaceMode` defaults to `overview`; selecting an agent returns to overview. |
| First-layer technical debug hidden | done | `Advanced` and migration/support tools are gated behind `is_superadmin`. |
| Small-screen tab overflow controlled | done | selected-agent tabs use horizontal scroll and fixed shrink behavior. |
| Long agent lists do not push detail infinitely | done | agent list has bounded height and internal scroll. |
| Create flow names the safety review clearly | done | copy uses "Проверка будущего агента" and "Создать после проверки". |
| Approval explained in user language | done | overview and approval cards explain what waits and why. |
| Voice/persona no longer a separate product world | done | `AIAgents` are shown as "Голос и стиль". |
| Learning loop is versioned and inspectable | done | learning history, diff activation, rollback, and version events are central in the agent card. |
| First-layer copy guard exists | done | `scripts/ci_gate_product_ui.sh` runs the agents copy guard and syntax check. |
| Visual authenticated cockpit smoke | done | `python3 scripts/smoke_agents_product_ui_mock.py --screenshot /tmp/localos-agents-cockpit-mock-full.png` renders a non-superadmin cockpit with mocked auth/API data. |

## First-Layer Copy Guard

Avoid these terms in the ordinary user layer:

- `capability`
- `runtime truth`
- `OpenClaw`
- `ActionOrchestrator`
- `provider executor`
- `credentials required`
- `approved external write`
- `Preview run`
- `workflow debugger`
- `legacy workflow`
- `candidate version`

Allowed places:

- `Advanced`
- support export
- raw trace/details
- source code, type names, API fields, and docs intended for developers

Run this gate before shipping changes to the agents screen:

```bash
scripts/ci_gate_product_ui.sh
```

For an explicit visual artifact while local Vite is running:

```bash
python3 scripts/smoke_agents_product_ui_mock.py --screenshot /tmp/localos-agents-cockpit-mock-full.png
```

## Next Hardening Checks

- Verify `/dashboard/agents` with a superadmin user and ensure Advanced does
  not dominate the normal flow.
- Check long Russian agent names, long descriptions, no-agent empty state, and
  many-agent list behavior.
- Check the create dialog at small laptop width: the future-agent review must
  be readable without a permanent right rail feeling like the main product.
