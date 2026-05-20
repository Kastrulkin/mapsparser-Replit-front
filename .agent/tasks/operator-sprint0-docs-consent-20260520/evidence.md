# Evidence Bundle: operator-sprint0-docs-consent-20260520

## Summary
- Overall status: PASS
- Last updated: 2026-05-20T10:20:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `docs/agents/localos-operator.md` defines LocalOS Operator as the planned main control layer above the dashboard.
  - The document explicitly models web chat and Telegram as transport adapters to one governed Operator core.
  - `docs/agents/index.md` and `docs/index.md` link to the Operator document.
- Gaps:
  - None for Sprint 0 docs.

### AC2
- Status: PASS
- Proof:
  - `docs/agents/localos-operator.md` defines `free_cached`, `paid_compute`, `paid_external`, `manual_external`, `approval_required`, and `planned_gap`.
  - `docs/agents/tool-registry.md` adds the same Operator action classes and says Operator-facing tools should include `operator_action_class`.
- Gaps:
  - Runtime tool metadata is a future sprint.

### AC3
- Status: PASS
- Proof:
  - `docs/agents/localos-operator.md` defines business-level paid action consent policy with `ask_each_time`, `auto_with_limits`, and `disabled`.
  - It documents max credits per action/day/month, low-balance warning, first-use disclosure, post-execution charge reporting, and budget stop behavior.
  - `docs/agents/approval-policy.md` now distinguishes paid action consent from approval.
- Gaps:
  - Runtime billing/consent implementation is a future sprint.

### AC4
- Status: PASS
- Proof:
  - `docs/agents/localos-operator.md` states that LocalOS may generate review reply drafts and copy/manual assist, but must not claim it publishes replies to map providers.
  - `docs/agents/approval-policy.md` adds a Manual External Publication section.
  - `docs/agents/index.md` adds the same limitation under "What Agents Must Not Assume".
- Gaps:
  - None for docs.

### AC5
- Status: PASS
- Proof:
  - `docs/agents/tool-registry.md` links to LocalOS Operator, defines paid action contract fields, and documents ledger/consent expectations.
  - `docs/agents/approval-policy.md` links paid action consent to Operator and tool registry rules.
  - `docs/agents/harness-architecture.md` adds paid action consent policy to harness ownership and links Operator.
- Gaps:
  - None for Sprint 0 docs.

### AC6
- Status: PASS
- Proof:
  - This evidence bundle lists changed docs and checks.
  - `verdict.json` is set to PASS.
- Gaps:
  - No runtime tests were needed because Sprint 0 is documentation-only.

## Commands run
- `sed -n '1,180p' README.md`
- `sed -n '1,240p' agents/autonomous_development_brief.md`
- `scripts/proof_loop.sh init operator-sprint0-docs-consent-20260520 "..."`
- `rg -n "LocalOS Operator|free_cached|paid_compute|paid_external|manual_external|approval_required|planned_gap|auto_with_limits|ask_each_time|disabled|Apify actual cost|copy|manual|provider write|MCP" docs/agents docs/index.md .agent/tasks/operator-sprint0-docs-consent-20260520/spec.md`
- `rg -n "опубликовал ответ|отправил ответ в карты|autonomously write|public MCP server is confirmed|direct map reply publishing" docs/agents`
- `git diff -- docs/agents/localos-operator.md docs/agents/index.md docs/index.md docs/agents/tool-registry.md docs/agents/approval-policy.md docs/agents/harness-architecture.md .agent/tasks/operator-sprint0-docs-consent-20260520/spec.md`
- `scripts/proof_loop.sh validate operator-sprint0-docs-consent-20260520`
- `scripts/proof_loop.sh status operator-sprint0-docs-consent-20260520`

## Raw artifacts
- `.agent/tasks/operator-sprint0-docs-consent-20260520/spec.md`
- `.agent/tasks/operator-sprint0-docs-consent-20260520/evidence.json`
- `.agent/tasks/operator-sprint0-docs-consent-20260520/verdict.json`
- `.agent/tasks/operator-sprint0-docs-consent-20260520/problems.md`

## Known gaps
- Web chat UI, Telegram Operator runtime, billing tables, Apify credit conversion, and paid action execution are intentionally out of scope for Sprint 0.
