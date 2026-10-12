# Outreach from web chat and Telegram — 12 October 2026

## Verified release

LocalOS production base: `29427cfe0a32e7d95f5dd083f1c7c7be1c64f101`.
Production contains additional uncommitted work. This branch includes only outreach changes; the Operator frontend delta is preserved as `releases/any-chat-20261012/operator-live-results.patch` against the existing compact production interface, avoiding unrelated UI changes.

- Existing OpenClaw server is deployed separately. Reuse its installed `web_fetch` via the existing authenticated bridge; do not replace it with a new crawler, connector platform or generator.
- `partners.research_website`: initial URL + up to four same-site linked pages, SSRF/redirect restrictions, no Firecrawl, browser or search fallback. Provider never writes LocalOS records or sends mail. Legacy `partners.enrich_contacts` remains normalization-only.
- Link commands use the reviewed native continuation, business deduplication, enrichment queue, qualification and canonical campaign preparation. Resume no longer requires a search API for explicit URLs.
- Explicitly reviewed source jobs can use the existing Operator worker cycle without waiting behind unrelated maintenance jobs. Paused/cancelled parent tasks are excluded from new claims.
- Outcomes are journaled once and appended to their exact originating conversation. Telegram text is split without truncation and delivery checkpoints do not rerun business actions. Full draft texts come from canonical campaign touches.
- Frontend receives journaled outcomes through its existing group refresh; stale business responses are ignored and earlier messages are retained.
- Tavily activated after the owner explicitly confirmed Pay-as-you-go is OFF. Its null API paygo limit remains unknown, not zero: the separate `TAVILY_PAYGO_DISABLED_VERIFIED` attestation supplements missing data. Positive overage limits and paid plans remain blocked. Exa and Yandex remain disabled, and only confirmed quota exhaustion permits another verified provider. Maps remain explicit-only.

## Evidence

28 focused tests pass. Backend compilation and the first Vite build passed. The full frontend `tsc --noEmit -p tsconfig.app.json` check fails on existing project errors (including incompatible language types); the earlier root-config check did not establish a clean application type check. Final Vite build passed (34.19 seconds). Actual Tavily request returned three candidates, without Apify/maps/photos/reviews. This does not qualify those candidates.

Actual browser link task: `3754b99a-c821-4119-aa89-979a7c486e34`, Riderra.
Existing EWS Holidays company reused; zero search calls. Research ran through OpenClaw; qualification found insufficient evidence of India, Phuket sales and public email. No campaign letter or send was created. One qualification credit charged, distinct from chat command charges. Outcome recorded and delivered to the originating web conversation. This is a verified negative path, not successful pilot acceptance.

The final UI bundle `index-f8oo8zVB.js` was publicly served after deployment, then replaced by another server-side release (`index-BnDORFMQ.js`). Browser acceptance therefore fails: it displays the older Operator. This is an observed deployment conflict, not a browser cache assumption. Preserve the scoped frontend patch and reconcile the concurrent release before another publish.

## Remaining acceptance — do not report complete

1. Genuine Telegram inbound command, review and complete draft delivery; a service call is not Telegram acceptance.
2. Three qualified Riderra companies and three canonical individualized letters without manual result edits.
3. Exact-version send review/confirmation and native provider receipts; reply matching and suppression for those new letters. No mail sent in this release.
4. Two reviewed draft-only schedule runs 15 minutes apart, then pause; no such runs accepted yet.
5. OpenClaw existing read gate has a 24-hour verification freshness limit. Preserve its safeguards; persistent readiness beyond expiry needs an explicit supported re-verification mechanism.
6. Exa free-only guard not confirmed; Yandex intentionally disabled pending separate paid-source approval.

## Rollback

LocalOS source/config/UI backups: `/opt/seo-app/.release/any-chat-20261012/`.
OpenClaw bridge backups: `/root/openclaw_runtime/var/releases/any-chat-20261012/`.
Revert only corresponding release files, preserve unrelated production changes and secret files. Recreate containers after environment changes. UI assets were copied before index and old chunks retained; rollback the saved UI archive rather than a stale Git frontend snapshot.

Secrets are server-side only. No keys in this report or release patches.
