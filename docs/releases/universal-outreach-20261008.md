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

Release preparation resolved the frontend divergence by keeping the entire current live module graph and replacing only the Partnerships and DashboardLayout modules. Their newly built imports are bridged to the existing live root only after all exported definitions pass structural comparison. The React/vendor runtime remains the current live runtime. All 168 JavaScript modules were parsed and 2,656 named-import connections checked. Only 25 previously absent CSS utility rules were appended, preserving the current base styles. The live Operator receives only the scoped schema/description patch, retaining its additional content handlers.

Back up served frontend and the five changed backend services, guard their baseline hashes and the current entry, deploy only these components, restart the affected backend services, and verify the public entry plus container paths `/app/dist` and `/app/frontend/dist`.

Do not claim a real search or email delivery from component fixtures or mocked model tests. Real pilot is search-only and remains a release acceptance step.
