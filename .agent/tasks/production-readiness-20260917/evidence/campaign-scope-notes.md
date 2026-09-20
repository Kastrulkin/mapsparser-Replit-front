# Campaign editor async scope — bounded local correction

Parent03ef38f6. UX-CAMPAIGN-SCOPE-02. The preceding goal turn was progress:
verified recipient projection/display was committed, without deployment.
Original full production-readiness objective remains unchanged and overallFAIL.

Owner/operator task: review and act on the currently opened partner lead only.
DESIGN.md requires private state to belong to the current user/business/scope;
the drawer reuses Builder with selectedLead's workstream and current business
(`PartnershipLeadDetailDrawer.tsx:690`). Its current campaign/preview loaders
capture old props and update state unconditionally after requests settle.

Initial guarded `campaign-scope-red.json` on unchanged application source:
4failed/1passed,5.01s/capture7340.171ms, exit1, no timeout/truncation. Campaign
load, preview and saved-preview responses overwrite the newer B recipient;
old preview busy state also disables B controls. This first capture proves
state/busy contamination, not a real provider action. The first test stops at
the missing B text before its approval-URL assertion. The combined error/busy
test stops at busy before rejecting its promise; no separate error-path proof
is claimed from that run. Its passing preview-then-approval control is being
replaced with an unambiguous saved-campaign control, not adopted as a product
contract for approving unsaved previews.

All requests are synthetic newAuth mocks. Node22/env-i, existing no-egress
preload chain, envDir:false and frontend child cwd; named tmux. No test server,
DB connection, production browser action or external dispatch.

Implemented bounded repair after the causal RED: keyed private editor for the
existing workstream/business/segment state inputs, plus a distinct lifetime
token per effect setup. Immediate replacement prevents stale controls during
B loading; token checks after every await/catch/finally prevent obsolete
follow-up reloads/callbacks and survive A→B→A/StrictMode/unmount. Already-started
authorized server operations are not cancelled or rolled back by this fence.
No backend/API/approval policy change or new dependency.

The first expanded run passes 24 tests in 11.75s/capture 13502.221ms.
The final frozen tests add both old-resolution/old-rejection while B stays busy
and a post-reload callback assertion: 26 tests pass in 13.00s/capture
14464.038ms, exit0, no timeout/truncation, empty stderr. Twenty scope cases cover
campaign/preview/save, correct approval URL, error/busy state, immediate pending
UI clearing, A→B→A, business/segment independently, unmount and chained reload,
StrictMode first-setup lifetime, unchanged-key unsaved preview and recommendations.
Six existing recipient/review tests also pass. Original failing assertions remain;
the old passing ambiguous approval control was replaced as described above.

The unchanged guarded adjacent backend selection passes 288 tests in
1.51s/capture 2214.813ms, all network/database/dotenv/child-process counters zero.
Initial TypeScript/lint passes 55320.814ms with one existing auth_new.ts:115
no-explicit-any warning. This first quality run preceded the final test additions;
final quality and full frontend captures are separate. App source was frozen.
App build passes in 14.41s/capture 15917.933ms; integrity passes 176.578ms for
199 reachable JS assets. Artifact is
`/private/tmp/localos-campaign-scope-build-20260920.9x30pD/dist`, entry
`index-D2EAyMYE.js`, CSS `index-BM6vOqzw.css`. Upstream Yandex PURE comments and
the external outDir warning are retained; no existing dist was emptied.

Independent read-only actual source review by draft_approval_regression is
bounded PASS: key inputs match existing state inputs, every await/catch/finally
and chained callback is fenced, same-key editor state is retained. The static
same-workstream localStorage contract at test_founder_outreach_campaigns.py:4452
belongs to AdminLeadRegistry, not this Builder. Independent bounded evidence
review also PASS: final26, backend288/zero guards, types/lint/build/integrity
and all nine manifest hashes match. Final types/lint pass61243.355ms; one
existing warning. Full frozen frontend709tests/133files now passes330.49s/
capture331940.084ms, exit0/no timeout/truncation. All nine manifest hashes still
match. Full stderr retains known jsdom and negative error-boundary/auth/network
fixture diagnostics, not an empty-stderr claim. No unhandled-error result.
No new-build browser, native SQL, full backend, Docker image or live effect proof.
Same-lifetime request ordering is outside this fence. Separately, preview B can
remain visible while approval targets saved A in the same scope; this is a
source-traced candidate for its own causal regression, not fixed here.

The user-confirmed IAB login was read-only rechecked on /dashboard/today:
authenticated business cabinet with SuperAdmin label is visible. Russian,
Spanish and English UI text coexist on the deployed page. No form/action was
submitted, no console or deployed-revision certification in this observation.
It does not prove these local changes are deployed.

Nine foreign paths remain excluded; aggregate/restore denials and prior
unsafe-reset INCONCLUSIVE effects persist. Latest read-only disk 4,828,188KiB
(~4.60GiB), below10GiB Docker floor. No push/deploy/data deletion/schema/
production/provider authority is expanded. Original overall acceptance FAIL.

Precommit capture1544.671ms passes all nine hashes, staged whitespace and
Gitleaks (~211139 bytes, no findings), and checks overallFAIL. The initial exact
staged set has25 owned files and0 foreign paths. The capture itself and observed
report metadata are then included; app/test source remains unchanged.
