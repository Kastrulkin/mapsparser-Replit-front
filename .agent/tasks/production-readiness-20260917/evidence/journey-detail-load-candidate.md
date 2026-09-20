# Journey detail GET ordering — source-only candidate

UX-JOURNEY-DETAIL-LOAD-09, P2, traced read-only by journey_identity_contract
during the card scope package, parent544fbe96. Not causally reproduced or fixed.

JourneyWorkspaceFocus.tsx15/21–35 reads query journey_action and starts a detail
GET for actionId/currentBusinessId. The same mounted dashboard route can change
only query action (App.tsx355–376; generated URLs leadJourney.ts400–403 and the
Focus onUpdated handler54–63). load sets loading/error but retains prior action;
then/catch/finally have no request-generation guard. An old A GET may overwrite
a newer B result while URL remains B. Keying the child form resets fields only
after the parent selects an action; it cannot reject an obsolete detail response.
The resulting stale same-business card could target A, not intended B; no actual
submission or cross-tenant write is proven.

Business switches currently remount the dashboard Outlet (DashboardLayout.tsx
205–215/369), and backend detail loads predicate on action ID/business ID. Do
not infer a cross-tenant leak from the same-route/query race. Telegram's separate
detail-loader path is also unguarded source, but not this bounded candidate.

Next causal check: MemoryRouter + nested Outlet context + useSearchParams button,
mock newAuth.makeRequest with separate deferred GET(A)/GET(B). Navigate A→B;
resolve B first, then A, and require only B to remain rendered/clickable. Test
late old error/finally and withholding mismatched A during B load. Positive:
current B transient failure shows retry; retry success clears error and leaves
B selected even when old A settles afterward. Existing DashboardLayout.scope
test harness supplies router/deferred patterns. No production or DB execution.

Potential fix only after RED: bind detail state/request generation to active
business/action intent, preserve same-intent retry, invalidate on unmount; do not
broaden the current form/command lifetime patch or assume abortion rolls back
already-started commands.
