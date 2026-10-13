# Outreach acceptance — 13 October 2026

The full outreach goal is **not accepted**. Do not equate deployed components, old sent campaigns, or successful qualification with a new successful draft/send pilot.

## Sources and release boundaries

Backend fixes are committed on `codex/outreach-acceptance-20261013` (through `ed1d02e41`). The compact Operator/task-picker change is on `codex/operator-task-picker-20261013` (through `77582c3c2`), based on the compact UI release `3616c45a4`.

Production and the main working checkout contain other uncommitted changes. They are not interchangeable release sources. Preserve demo/navigation, ready-email import, manual-text support and the neighbouring free-access UI. Apply scoped changes to current runtime files; do not rebuild the old main checkout and overwrite the current UI. The frontend release script's active dependency-graph check rejects the older Operator/Partnerships/navigation layout.

LocalOS backups for this run: `/opt/seo-app/.release/outreach-acceptance-20261013/`. OpenClaw bridge backup: `/root/openclaw_runtime/var/releases/outreach-acceptance-20261013/`. No database migration, destructive deduplication or mail send was performed.

## Verified fixes

- Installed OpenClaw `web_fetch` is invoked through the existing authenticated bridge. Website readiness is renewed only by a successful real read of the controlled LocalOS robots resource; authorization is checked first. Failure does not extend the verification timestamp. Paid fallback remains disabled.
- Canonical `www`/apex redirects are accepted only for the same website and port. Initial plus four same-site pages remain the maximum. Public contact/company pages and previously sourced same-site pages fit that budget; unknown URLs are not guessed.
- Public source-confirmed contacts are included in qualification evidence. A sourced email is not evidence of mailbox delivery. Collected excerpts remain untrusted evidence.
- The actual Compose `operator-worker` runs `src/operator_worker.py`, not the general worker loop. It now consumes the existing approved website queue in one bounded background thread, leaving pause/chat commands responsive. Jobs created by active approved web searches are also eligible; unrelated historical enrichment is excluded.
- A domain-only historical import does not become a second company when there is exactly one named company for that website. Both records remain. Two named companies require a decision.
- A group's drafts/receipts/replies are scoped to its campaigns, including native batch projections. Reusing a company no longer automatically imports unrelated historical sends into the group's counters.
- Campaign drafting is bound to the exact current reviewed task. A new task cannot reuse an old sent campaign as its new draft. Replays of the same task reuse only its own draft.
- `English` and Russian/English language labels normalize to the existing language codes. Invalid conditions explain the failure rather than returning “Data received”. Validated outreach actions finish without another planning loop. Resume chooses the actual continuation worker unless an existing batch-draft job is present.
- Task picker refreshes on opening and immediately retains newly returned tasks. Temporary refresh failure retains the last list.

## Live evidence

- Telegram link command created task `34301e4b-09b2-47da-8d25-9aa767eadac6`, reused Holiday Advisor and delivered its negative result to the originating Telegram conversation. This is a negative-path test, not successful draft acceptance.
- Web task `a8549889-9e13-4bea-9af0-023496f3a5bc` qualified Holiday Advisor, but reused an old sent campaign. That result is explicitly **not** counted as a fresh draft. The reuse defect was subsequently fixed.
- Current three-company web task `e361ce95-586a-441f-a167-455805fdb5ed` retained its ID through a native reviewed resume. It reused the original EWS Holidays, Holiday Advisor and Kingdom of Holidays records. OpenClaw source jobs completed; Holiday Advisor and Kingdom of Holidays passed the requirements. EWS lacks sourced evidence of Phuket sales. Three qualification credits were charged; zero search calls occurred.
- Initial drafting failed because it selected the oldest historical contract. The exact-task fix then exposed a production-only extra function parameter; the merged signature was corrected and verified through the actual container import. No new letter was sent or manually repaired.
- The next reviewed version permits up to five draft attempts. The owner explicitly approved this exact draft-only version after the initial approval rejection. The start has not yet been verified: LocalOS HTTPS and server SSH currently time out. Do not claim the approved run passed.
- Mobile 390 px and desktop 1366 px: input remained visible and no horizontal overflow was observed. Task picker stale-list defect was reproduced; its regression now passes, including a refresh failure.

## Verification and remaining work

61 focused backend tests pass; changed backend files compile. Task-picker regression passes; three frontend release-guard tests pass. Application type check (`tsc --noEmit -p tsconfig.app.json`) passed with exit 0. Earlier clean root-config checks were not application type checks.

The server UI build initially failed because an already declared/locked `@xyflow/react` dependency was not installed. Dependencies are being restored from the existing lockfile; the previous served bundle remains in place until build and release checks pass.

Remaining acceptance:

1. Start the owner-approved version once connectivity is restored and obtain fresh canonical drafts without manual result editing; find a third actually suitable candidate rather than weakening evidence for EWS.
2. Complete a positive Telegram review → complete draft-text delivery. Desktop user interactions interrupted the attempted follow-up test; coordinate a short uninterrupted window.
3. Review exact new recipients/text/version and obtain separate human send approval before native queue/send tests. Historical receipts and the prior control reply do not establish acceptance for these new letters.
4. Perform two real native scheduled draft-only runs, 15 minutes apart, then pause and reconcile duplicates/expenses. Existing chat schedule accepts daily/weekly schedules; no interval-schedule implementation or substitute Codex automation is claimed.
5. Finish served UI/task-picker/browser checks and business-switch recovery. Do not claim full outreach complete while any of the above remain unresolved.

## Additional scoped fix pending deployment

The live Partnerships draft list showed historical sent letters for the same leads while the new task correctly reported zero new letters. List and send snapshot filters now use exact task/campaign ownership instead of shared lead membership. Empty campaign scope remains empty; business/task access is validated first. Regression tests cover exact campaign ownership, empty groups and another business. This patch has not been deployed or browser-verified because HTTPS/SSH connectivity is unavailable. Merge its hunks with live files, preserving production additions, before release.
