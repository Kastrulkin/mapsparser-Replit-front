# Journey action form/request scope — locally verified

Parent544fbe96, UX-JOURNEY-ACTION-SCOPE-08. Previous goal turn made concrete
progress: the shared card locale fix was locally committed and independently
verified with757frontend tests. Whole-project production-readiness stays FAIL.

User task: edit and confirm the current next action without carrying obsolete
form values or a late result from a previous action into the current workspace.
Reachability comes from JourneyWorkspaceFocus's unkeyed nextAction handoff and
TelegramControlWorkspace's same pattern. The supported content cycle clears
draft_text/scheduled_for/publication_url in lead_journey_service before creating
a new review action for the same entity. Existing card local state initializes
only on mount. The initial candidate was then reproduced by root's RED below.

Contract: DESIGN includes scope in every state/request; existing keyed list
callers already reset by action.id, while same-action retry tests retain the
idempotency key. Establish version-refresh semantics before choosing a form key.
Do not claim cross-business leakage or backend writes from mocked UI evidence.

Independent identity trace confirms businessId/action.id as form identity.
Journey actions have a UUID primary key; supported updates do not change
business/entity/flow/action type. ensure_action474–510 can merge payload on the
same action without changing version. Version is an optimistic-concurrency
marker, not a form identity. Same-id payload/version/surface/locale refresh must
not silently discard an edit. New action ID or business resets the form; a
separate request lifetime must invalidate command/clipboard continuations after
unmount. No transport/API change or cancellation of an already-started command
is implied. Parent Focus/Mini detail-load ordering is a separate unfixed path.
Here scope change means the card's business/action props changed or it unmounted;
a parent that still renders old props after a new URL intent needs its own fence.

Root owns component implementation, guarded test execution and evidence/docs.
Worker owns only the new JourneyActionCard.scope.test.tsx; a read-only explorer
checks action identity/version semantics. Source remains unchanged before RED.
Nine foreign paths are preserved/excluded. Latest disk6,893,116KiB (~6.57GiB)
is below the10GiB image floor. No native DB, Docker, cleanup, push/deploy, provider
or production mutation. Aggregate/restore preparation denials and prior unsafe
reset's INCONCLUSIVE effects persist; do not retry them by another route.

Root causal RED4fail/6pass across10cases,8.40s/capture10687.735ms, exit1 with
no timeout/truncation. Failures: new-cycle B retains old form, old success calls
the obsolete callback, old rejection renders its error in B, synthetic reused
ID/business switch retains A. Same-id refresh and5existing controls pass.
Fresh-submit assertions in the two field-reset cases are not reached in RED;
do not claim an observed backend write. Fixtures model source-supported handoff,
not a live backend cycle. Pre-run harness corrections (explicit Promise callback
void types, valid nonempty B submission, settling late requests before asserting)
are not product defects and were not executed as a failing product baseline.

Root source patch: public keyed shell [businessId, action.id] around the form;
useLayoutEffect gives each mount/setup its own active lifetime, cleaned up on
unmount. Execute start/result/error/finally and clipboard continuation are fenced.
Independent actual source review PASS. Started requests remain non-aborted; no
rollback or provider cancellation is claimed. UI/primitives and command payloads
are unchanged. Build passes13.83s/capture15210.221ms, exit0/no timeout/truncation,
only existing Yandex PURE and external-outDir warnings. Integrity199JS passes
242.268ms; nonfatal Darwin temp-dir lookup warning uses/tmp. Artifact is
/private/tmp/localos-journey-scope-build-20260921.Dg5qTe/dist, entry
index-C7EcEDZk.js/CSS index-BM6vOqzw.css; existing dist unchanged.

Expanded105targeted/adjacent checks across6files pass38.12s/capture40349.497ms,
exit0/no timeout/truncation, only2known jsdom scrollTo diagnostics. Scope file
has14cases, plus39existing card/locale and52adjacent page checks. It covers new
action resets, same-ID edit retention with changed payload/version/surface,
pending A/B busy isolation, late success/error/unmount, clipboard continuation
success/rejection and current exact-byte copy, StrictMode current setup,
stale/current upgrade navigation, and details/date/reply/configuration/metrics.
Root added Radix pointer/scroll polyfills and a plain Location facade behind a
read-through Window Proxy before execution; native Location.assign cannot safely
be replaced through a Proxy invariant. These are fixture corrections, not causal
product failures. Original RED assertions stay unchanged.12manifest hashes
captured39.202ms still match after targeted run. App/node TypeScript and full
lint pass48761.169ms, one existing auth_new.ts115 any warning. Independent
targeted/source/evidence review PASS. Full frozen frontend771tests/136files passes
313.22s/capture314627.727ms, exit0/no timeout/truncation. All12hashes match after
completion; full stderr byte-equals preceding journey-locale-full.json known
jsdom/intentional negative fixture diagnostics, not a failed/unhandled test.
All captures succeed except deliberate causal RED. No backend suite changed/run.

Precommit passes1257.505ms, exit0/no timeout/truncation: all12hashes match,
staged diff-check clean, Gitleaks scans188912bytes with no findings and original
overallFAIL/onlyAC10PASS remains. Exact23owned files staged before this capture;
capture is the24th file, nine foreign paths excluded. Metadata is restaged and
scanned again before the local-only commit; no push or deployment.
