# Frontend technical-debt reduction — 17 September 2026

## Scope and result

Baseline: `deafb20e`, clean `codex/content-generation-v2` worktree. Only frontend implementation, related tests, and quality gates changed; backend runtime, production database, migrations, sends and approvals are not part of this release.

The measured baseline was 534 ESLint warnings (the earlier estimate was 532):

| Rule | Before | After |
| --- | ---: | ---: |
| React effect dependencies | 96 | 0 |
| Explicit `any` | 277 | 1 |
| Fast Refresh mixed exports | 150 | 0 |
| Other warnings | 11 | 0 |
| Total | 534 | 1 |

The remaining warning is the return type of `NewAuth.makeRequest` in `frontend/src/lib/auth_new.ts`. It is the shared legacy transport boundary, with hundreds of callers and several unrelated response shapes. Replacing it safely requires endpoint-specific contracts and caller migration. It remains visible; no source lint rules were disabled. `npm run lint` now limits warnings to one. Implicitly untyped legacy code is not claimed to be eliminated; the existing TypeScript strictness settings are unchanged.

## Changes

- Corrected effect dependencies and stable event callbacks while preserving explicit business/selection reload boundaries. Scope cancellation prevents old API results from overwriting a newer view.
- Introduced `usePolling` and `useMobileJobPolling`: one request at a time, cancellation on scope change/unmount, no late state updates.
- Extracted Telegram Cards, Content and Finance into `frontend/src/features/telegram/`. The control workspace decreased from 1850 to 1007 lines.
- Extracted agent run polling, recovery/tracking and animation into `frontend/src/pages/dashboard/agents/`. The main workspace decreased from 2312 to 2087 lines. It is still substantial and is not claimed to be fully decomposed.
- Separated context hooks, style variants and utility functions from React component modules; updated imports and test mocks. Existing approval and manual-publication boundaries remain intact.
- Added explicit shared business, news, partnership, agent-settings and API-input types; error values are narrowed from `unknown`.
- Typed translation dictionaries against the English fallback and corrected invalid dictionary paths. Added missing English/Russian network-overview copy.
- Added the real full-project `npm run typecheck` (both app and Node configs). CI now runs it instead of permitting a historical scoped TypeScript baseline, and runs the lint ratchet.
- Lowered module-size ratchets after extraction and covered the new Telegram feature directory.

## Reproduced correctness fixes

1. News transaction selector: its callback variable shadowed the translation dictionary. A transaction without services threw `Cannot read properties of undefined (reading 'card')`. The regression test failed with the original expression and passed with the corrected variable.
2. API data/polling: delayed results from a previous business or an unmounted screen are ignored. Tests cover cancellation, non-overlapping requests and stable polling callbacks.
3. Agent animation: completion of an older run cannot finish the animation of a newer run. Recovered-run finish delays are cancellable.

## Verification

- Full app and Node TypeScript checks: passed.
- ESLint: zero errors, one documented legacy warning.
- Full Vitest suite: 557 tests passed in 121 files (`npx vitest run --maxWorkers=3`). This includes API scope isolation, HTTP cancellation, polling and the news-selector regression.
- Playwright: 72 mocked browser scenarios passed across desktop, Android and Telegram-sized viewports. Coverage includes compiled-agent approvals/results, card growth, partnerships, finance voice, request history and work journal. These checks do not prove external-provider delivery.
- Related backend/source contracts: 88 passed (`test_large_module_size_ratchet`, `test_agent_blueprint_async_contracts`, `test_agent_blueprint_api_generic_runs`). The initial host-Python attempt had an architecture mismatch; the successful run used arm64 Python and an isolated temporary `defusedxml` dependency.
- Agent UI-copy guard: passed.
- Concurrent unrestricted unit/browser runs exposed load-sensitive UI-wait timeouts. Verification was repeated sequentially with bounded worker counts, without changing assertions, test coverage or timeouts. Prefer separate test stages on resource-constrained workstations.
- App and public production builds: passed. Deployment outcome is recorded separately after verification; a local test pass alone is not deployment proof.

## Remaining work

1. Type `makeRequest`/`api` per endpoint and progressively enable stricter TypeScript checks. Start with authentication and the agent-run read endpoints; keep API success/error payload contracts explicit.
2. Further divide the agent workspace by setup, connection management and run actions. Keep current run ownership, business isolation and manual-approval behavior covered.
3. Production capacity remains constrained: preflight reported about 2 GB free (95% used). This release does not remove database files, retained assets or backups to address it.
