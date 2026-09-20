# Campaign preview/consent identity — bounded local verification

Parent191488ba, branch codex/production-readiness-20260917. The previous goal
turn was progress: scope fence committed with709 frontend/288 adjacent backend
passes and independent review. Original full DoD remains unchanged, overallFAIL.

UX-CAMPAIGN-CONSENT-03, P2. Operator job: approve or explicitly launch
the same saved campaign text/recipient that is being reviewed. DESIGN25–30 and
OUTREACH_SYSTEM37,41–43 require a saved new version and fresh approval when text,
sender/order/schedule changes. The Builder renders preview.touches before saved
touches, but its approval/pilot controls act on selectedCampaign.id alone.
Local unsaved schedule/text flags also do not gate those saved-version actions.

Independent read-only contract trace confirms:
- preview save:false returns transient preview and rolls back;
- save:true returns metadata {id,version,status,room}, not a full saved snapshot;
- GET campaigns returns authoritative saved touch/recipient rows;
- approve acts on its URL id; pilot preflight/dispatch do likewise;
- apply-learning creates a new draft and also requires reload/review.
References: outreach_campaign_api.py1182–1238,1417–1437,1592–1649,1764+,1837+,
2827+; outreach_campaign_service persist_preview4825–5015. These are source
traces, not runtime/provider evidence. Backend authorization is not bypassed by
this candidate; the suspected mismatch is between human review and action ID.

Proposed bounded acceptance: no approval/pilot start/resume while preview,
schedule or text changes are unsaved; successful save/apply-learning must show
the returned ID's authoritative saved snapshot before enabling consent. Failed
save/reload or a list missing that ID stays blocked. Explicit return to a saved
version must rebind the review and clear transient state. Preserve scope fence,
normal saved-version approval, server preflight and separate pilot confirmation.
No API/schema/consent-policy changes or real effects are intended.

Root guarded RED on unchanged191488ba:7fail/1pass in6.71s/capture9103.429ms,
exit1/no timeout/truncation. Failures prove active old approval controls for
preview/channel/text changes, stale pilot button, transient instead of canonical
saved B review, and fallback old approval after missing/failed B reload. These
checks fail on UI assertions before an actual mismatched approve/send request;
no provider event or production outcome is claimed.

Root implemented hasUnsavedReview fences, reload-by-exact-saved-ID before review,
explicit saved-version rebind/discard and save/review guidance. Approve, pilot
and resume cannot start under unsaved review. First targeted run32pass/2fail
15.68s/capture17973.136ms, untruncated. Remaining failures are an ambiguous
version Badge/option selector and an old scope positive expecting the transient
POST recipient instead of the authoritative GET recipient. Correct the selector
and expectation without weakening the original scope negative cases. Both
corrections are now applied; final targeted40/3files pass15.74s/capture18257.181ms,
exit0, no timeout/truncation, empty stderr. This includes14consent,20scope and
6existing recipient tests. All seven original negative states now pass.

Independent actual source review PASS by draft_approval_regression: exact saved
ID reload before clearing transient state, explicit version/discard binding,
handler/UI guards for approval/pilot/resume, unchanged backend policy and scope
fence. Requested focused discard/selection/resume/canonical-B pilot tests are
included in the final14cases. Pause/cancel/reply-sync remain outside the
start/consent gate. Independent final targeted evidence review also PASS.
Pilot confirmation false then true proves B-only mocked request routing, not
delivery: the fake dispatch returns no messages_sent success evidence.

Initial adjacent backend capture:287pass/1fail,1.61s/capture2208.642ms, all guard
counters0. The single failure is a static source-string assertion expecting the
old approved-only preflight condition. It is updated to require the stronger
approved AND no-unsaved-review condition, preserving the existing invariant.
Local frozen app build passes16.28s/capture17880.036ms, no truncation/timeout.
Final guarded adjacent backend288pass1.59s/capture2181.95ms; all effect counters0.
Final app/node TypeScript and lint pass54979.441ms, exactly one existing
auth_new.ts115 any warning. Integrity plus scoped Ruff pass351.341ms:199reachable
JS files, entry index-KhDntMj7.js, CSS index-BM6vOqzw.css. Artifact directory:
/private/tmp/localos-campaign-consent-build-20260920.tYTzun/dist. Build warnings
are upstream Yandex PURE annotations and deliberately external outDir; no
existing dist was emptied. Application source stayed unchanged after build;
only test assertion/selector additions followed it. No native-browser proof.

Eleven SHA-256 inputs captured after final targeted checks and before the full
frontend run (42.344ms). Full frozen723frontend/134files pass314.24s/capture
316492.583ms, exit0, no timeout/truncation. Post-run eleven hashes all match.
Known jsdom scroll/navigation and deliberate negative error-boundary/auth/network
fixture diagnostics remain in stderr; no unhandled-error result. Final independent
broader evidence closure is recorded separately in campaign-consent-review.md.

Regression worker owns only new OutreachCampaignBuilder.consent.test.tsx; root
owns source, the one older scope positive correction and the stronger static
assertion in tests/test_founder_outreach_campaigns.py. Tests use established env-i/
no-egress mocked frontend runner; no test DB, provider call or production form.

Nine foreign paths remain excluded. Latest disk6,851,904KiB (~6.53GiB) below
10GiB image floor. Aggregate-v2/restore preparation denials and earlier unguarded
reset-run INCONCLUSIVE effects persist. No push/deploy/production mutation,
cleanup, secret rotation or image build authority is added.

Precommit1426.531ms passes: eleven hashes, staged diff check, Gitleaks no leaks
in~237053bytes and unchanged original acceptance statuses. Scope is this local
package only, not history/image/production logs or credential revocation. Final
bounded independent evidence review PASS; later edits only reconcile report
metadata. Original full production-readiness objective remains active/FAIL.
