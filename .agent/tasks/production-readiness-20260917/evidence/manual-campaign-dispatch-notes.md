# Generic campaign dispatch identity — 20 September 2026

Parent: `7b41e8a9`. This is a bounded continuation, not whole-project acceptance.
Overall readiness remains FAIL; no push, deployment, production write, native DB
test, image build or cleanup is authorized/executed by this package.

## Authenticated browser observation

The existing user-signed-in IAB tab displayed `/dashboard/today`,
`/dashboard/operator` and `/dashboard/agents`. The operator history and ten
existing automated tasks loaded; the captured browser error/warn list was empty
(bounded most-recent 30 entries, not all requests or backend logs). Returned to
Today and closed navigation. No forms, generation, approvals, sends, settings,
publications or credentials were submitted. Production still shows mixed
Spanish/English/Russian system labels; Russian user content is not classified
as a translation defect. This does not verify the newer local build.

## Narrow causal hypothesis

`docs/OUTREACH_SYSTEM.md` requires changed text to create a new version and
approval. `approve_campaign` hashes the generated touch, sets its approved text,
creates an approved linked draft and the queue row. A separate reachable admin
draft-approve route can update draft approved text without changing that touch.
Before this package, generic preflight hashes touch.generated_text, but provider
input uses separately fetched draft.approved_text. Unlike template lanes, generic
dispatch does not check their equality or bind fresh preflight payload bytes.

OUTREACH-DISPATCH-IDENTITY-01 is locally REPRODUCED: causal RED5fail/1pass
in0.15s (capture513.364ms), including the unchanged positive control. The actual
hash, preflight and dispatcher-binding functions run against synthetic cursor
rows; repeat-contact, generation and research-fingerprint gates are stubbed.
No provider, database or admin mutation endpoint executes in this proof.

The fix compares linked queue/draft/touch identity, approved state, all body
copies against the hash-covered generated text, channel, contact, lead,
workstream and sender. It builds provider arguments from current preflight
rows only after existing generation/source/hash gates. Generic AI provenance
requirements remain unchanged. Automatic channels stay email/Telegram/VK;
manual channels are rejected here, not promoted. The previous Riderra test's
manual passthrough expectation now requires fail-closed missing-payload error.

Original regressions and expanded adjacency pass: initial109 in1.26s
(1787.738ms), final138 in1.27s (1795.702ms), all recorded guard counters0.
Final35 new cases cover body mutations, mismatched queue/draft fields, three
automatic recipients, six manual channels, generation/default AI and existing
permission/contact checks. Scoped Ruff F821/F822/F823 passes79.648ms. Captures
are untruncated and not timed out. Bootstrap is process-local, not OS isolation;
the suite is explicitly selected, not a full backend aggregate. Frontend source
did not change and the prior684-test frontend evidence keeps its original scope.

The direct AgentBlueprint request-only queue has no campaign touch; standard
preflight denies it with `campaign_approval_required`. No provider-send failure
has been demonstrated for that direct legacy path.

## Explicit residuals

The approved campaign hash includes contact ID, not a value snapshot of that
contact row. Binding a fresh preflight recipient removes the earlier claim-row
fallback; it cannot certify that a mutable contact value equals the value seen
at original approval. Contact-value versioning and native concurrent changes
after the preflight transaction need a separate design/test package. No new
schema or historical approval rewrite is performed here.

Denied aggregate-v2 and restore preparation remain denied. Earlier unguarded
reset-test effects remain INCONCLUSIVE. Nine foreign dirty paths are excluded.
