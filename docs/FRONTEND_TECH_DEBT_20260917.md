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

News-selector regression status: `FIX_PROVEN` (original failing expression reproduced, regression and broader checks passed).

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

## Storage update

Initial preflight reported about 2 GB free (95% used). The user subsequently added 10 GB. Read-only verification confirmed both `/dev/sda` and its ext4 root partition expanded to 50 GB: about 12 GB free and 76% used. No partition/filesystem command, database cleanup or backup deletion was needed or performed by this release.

## Production verification

- Frontend source commit: `290d1d56067afc06bc03d3489cc1a8555e78251c`, pushed to `gitverse/codex/content-generation-v2`.
- Deployed through `scripts/deploy_frontend_dist.sh` on 17 September 2026. Only built frontend files were copied; no backend source sync, migration or direct database mutation was performed.
- Main entry asset: `/assets/index-BmALpHaF.js`; public entry asset: `/public-audit/assets/index-Cya4w__Q.js`.
- Main HTML SHA-256: `2e1a5037340f451ebe9d94a01fce8c8247350cbecb26d7ae8d92a4f4d1e7e889`. Public HTML SHA-256: `0545e2ea9d3a58f65fe507566e0a4e0a322ae1623ba9bd419c37ca7fe0bcde94`. Local, server and live-container files matched, including the `/app/dist` main fallback.
- All 257 staged frontend/public files matched runtime copies byte-for-byte. Reachable asset checks covered 199 main-app and 12 public-app JS files. Existing hashed assets were retained for open tabs.
- `docker compose ps`, recent app logs, local HTTP and targeted live asset checks completed. The production login form rendered with no captured console errors. The Telegram route outside an authenticated Telegram session displayed its expected entry gate without console errors; private production workflows were not exercised with fabricated authentication.
- Rollback entry-point copies: `/opt/seo-app/release-backups/frontend-lint-20260917.72zIzv/`. Earlier assets remain in place. Server backend Git state was deliberately not reset or pulled.
