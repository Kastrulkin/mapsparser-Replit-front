# Universal outreach search — 8 October 2026

Uses the existing continuation task, Operator approvals and campaigns. No schema migration or production data rewrite.

Config adds optional `search_geography: string[]` (1–20 places, each <=120 characters) and `requirements: string[]` (0–10 conditions, each <=300 characters). Legacy config remains unchanged when read. Search conditions adapt country/destination only at read time. Generic checks require sourced evidence for audience, geography and every condition. Explicit generic conditions are bound to any AI send grant; a legacy grant cannot authorize them.

Revision preview returns `creates_new_search: true` and the existing `create_and_start` envelope when audience, geography, requirements or the search queries change. Other supported edits use `revise_and_start` with the previous revision. Existing approval and request-id deduplication remain authoritative. Runtime revision execution rejects envelopes whose conditions now require another search.

Frontend uses the shared Dialog for local opening and focus restoration. Search and generation settings remain secondary; all preview and confirm callbacks discard responses from an earlier business scope.

`outreach_credit_billing.py` is copied unchanged from production: the previously published branch depended on this module but did not contain it. Its addition restores reproducibility rather than changing billing.

## Release gate

The standard frontend deploy script now runs `check_outreach_navigation_release.py` against the staged snapshot before uploading it. The current production snapshot fails the chat/automation menu checks; the new candidate passes.

## Current production divergence

Live frontend entry at inspection: `index-CWgAYutP.js`. Rebuilding the current server source with the available dependency runtime yields `index-DSFfdqcc.js`, not the live bundle. Shared root exports have different definitions; replacing the entire frontend or transplanting a module by alias would risk losing unrelated updates or breaking shared contexts. No fallback to an old bundle is acceptable.

Release preparation resolved the frontend divergence by keeping the entire current live module graph and replacing only the Partnerships and DashboardLayout modules. Their newly built imports are bridged to the existing live root only after all exported definitions pass structural comparison. The React/vendor runtime remains the current live runtime. All 167 JavaScript modules were parsed and 2,654 named-import connections checked. Only 25 previously absent CSS utility rules were appended, preserving the current base styles. The live Operator receives only the scoped schema/description patch, retaining its additional content handlers.

Back up served frontend and the five changed backend services, guard their baseline hashes and the current entry, deploy only these components, restart the affected backend services, and verify the public entry plus container paths `/app/dist` and `/app/frontend/dist`.

Do not claim a real search or email delivery from component fixtures or mocked model tests. Real pilot is search-only and remains a release acceptance step.


## Production verification and follow-up

The first scoped frontend deployment exposed a distinct `LanguageContext.logic` instance in the production source. The frontend was rolled back immediately; the backend remained compatible. The corrected consumers import `useLanguage` through the provider module, which re-exports the same hook in the branch architecture and supplies the existing provider hook in production. Public assets use a fresh `-lo-u20261008c` suffix. The corrected page was verified in the authenticated Yandex browser: existing Riderra data loads, modern chat/automation menu labels appear, edit opens on one click, Escape restores focus, and a plumber search preview accepts two generic requirements through the real API.

A real search-only pilot created task `857b24d6-348f-46ca-bc06-8214619bc671` with target 1, one provider search and up to five checks (estimate 10 credits). The persisted task contains generic geography/requirements and no tourism legacy values. Its Apify run `Fre0Mmm9H9EHL4X0E` returned `TIMED-OUT`: 337 search pages and no matching new places. It produced no leads or emails. Provider resource usage was USD 0.0002; this is provider evidence, not the account credit charge. This pilot does not prove successful lead acquisition or complete outreach. No retry starts another provider run before reconciliation.

The pilot also exposed two presentation issues fixed in the follow-up: confirmed creation selects its returned stable task ID, and a provider run being polled between worker leases displays “Ищем компании” rather than “Ожидает запуска”. Queued jobs without a provider run retain the waiting label.

Final release verification: public entry `index-CWgAYutP-lo-u20261008c.js`, deployment exit 0, backups retained. Pilot reservation readback: 0 charged credits, 5 credits still reserved pending provider cost reconciliation; do not report the reserved amount as spent or start a blind duplicate run. The final browser refresh was blocked because the user's Mac was locked. The prior corrected build had passed the authenticated browser checks; final selection/progress changes passed types, build, 16 UI tests and 16 group-view tests, but the final browser refresh remains outstanding.
