# Task Spec: operator-sprint0-docs-consent-20260520

## Metadata
- Task ID: operator-sprint0-docs-consent-20260520
- Created: 2026-05-20T10:03:20+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Sprint 0: docs + action taxonomy + consent model for LocalOS Operator. Document Operator as main control layer over cabinet with web chat and Telegram transports, paid action taxonomy, consent/budget model, manual external publication limits, and implementation acceptance criteria. No runtime changes.

## Acceptance criteria
- AC1: A canonical Operator document explains LocalOS Operator as the main control layer above the dashboard, with web chat and Telegram as transport adapters to one core.
- AC2: Documentation defines action taxonomy for free cached reads, paid compute, paid external refresh, manual external actions, approval-required actions, and planned gaps.
- AC3: Documentation defines consent and budget policy for paid actions, including first-use disclosure, auto-with-limits, ask-each-time, disabled, per-action/day/month limits, and low-balance warnings.
- AC4: Documentation states that LocalOS currently prepares review replies/posts/news/service optimizations as drafts, but does not publish replies to maps or third-party systems; users copy/paste or publish manually where provider write support is unavailable.
- AC5: Tool registry and approval docs link to the Operator model and include billing/audit/ledger expectations for paid actions.
- AC6: Proof-loop evidence records the files changed and validation checks.

## Constraints
- Documentation-only Sprint 0. Do not change runtime behavior, schema, migrations, production data, or deploy.
- Do not imply public MCP availability, external provider write support, autonomous publishing, autonomous payments, or direct third-party actions.
- Preserve existing dirty worktree changes outside docs/proof artifacts.

## Non-goals
- Implement web-chat UI.
- Implement Telegram Operator runtime.
- Implement billing tables or credit ledger changes.
- Implement Apify parsing or AI-generation charging changes.
- Commit, push, or deploy.

## Verification plan
- Build: documentation-only; no build required.
- Unit tests: documentation-only; no unit tests required.
- Integration tests: documentation-only; no integration tests required.
- Lint: grep/readback checks for required terms and unsupported-claim guards.
- Manual checks: inspect changed docs for consistency with AGENTS product documentation rules.
