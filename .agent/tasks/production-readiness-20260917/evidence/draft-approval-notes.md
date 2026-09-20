# AI-APPROVAL-DRAFT-IDENTITY-04 — bounded local proof

Date: 20 September 2026. Source parent: `79d7b227`. This is a local
pre-decision draft-approval correction, not production exploitation or release
certification. The broader AI-APPROVAL-BINDING-03 finding remains a candidate.

## User task, causal defect and change

A business operator must see the exact messages/recipients before confirming a
supervised batch. The real runner built a draft artifact without `edited_text`,
stored an approval payload, then approved the current mutable draft text and
the IDs of the *latest* artifact. A normal admin draft save can change the text
while approval waits. The actual API commits even unsuccessful decision results,
so stale validation must precede **all** decision/domain writes.

The new local contract stores `snapshot_version: 1`, business scope and every
item's ID, lead ID, channel, effective `review_text` and `review_recipient`.
Effective text matches the existing edited-or-generated SQL semantics; an older
`approved_text` never overrides the text being reviewed. Before decision the
approval row and selected draft/lead rows are locked, then compared with this
snapshot. Missing, malformed, deleted, foreign or changed items return
`approval_payload_stale` without approving or advancing. A DB lock/query failure
propagates for the API's rollback, rather than masquerading as an empty result.

The draft application uses only validated snapshot IDs. Outreach capability
admission rechecks the stored approved snapshot and sets exactly those IDs,
ignoring mutable input/newer artifacts. Genuine fresh manual re-review of an
already-approved draft remains supported: this is a new decision, not reuse of
another decision as a grant. An independent review initially questioned this
compatibility, then withdrew the finding after checking the original loader and
new explicit-consent boundary; a positive regression preserves it.

The same plain-text snapshot summary is exposed both in the advanced queue and
before the real approval controls in EmployeeTestResultPanel and
AgentApprovalDecisionPanel. All items are available, not just the first three.
The UI neither fetches current draft text nor executes embedded markup. Missing
legacy snapshots show a recreate-review warning. The stale-error instruction
says to reject the old decision, prepare again and review the new text.

## Evidence and limitations

`draft-approval-red.json` is **not causal evidence**: the tmux default launched
x86_64 Python against arm64 psycopg2 and stopped before test collection.
`draft-approval-red2.json` explicitly uses arm64 and reproduces **4 failures,
1 passing unchanged control**, 0.60s / 1093.250ms capture, with zero recorded
network/DB/dotenv/child-process attempts. It exercises actual payload builders
and `approve`; a faithful SQL-projection fake prevents extra test columns from
hiding the missing `edited_text`. Only cursor persistence and downstream
advance/observability/effects are synthetic. No real external message is sent.

`draft-approval-backend-final.json`: **313 passed**, 1.66s / 2149.401ms, zero
guard counters. The 25 focused tests include before/after edits, contact/channel/
lead/tenant changes, malformed/empty/duplicate/missing snapshots, lock errors,
approved-text changes, current recovery admission and fresh re-review. This is
one bounded mocked aggregate, not the entire backend or native PostgreSQL.
Earlier green307 and green2311 captures remain immutable intermediate results.

Final focused frontend16tests/3files pass14.49s/16316.089ms; frozen full
frontend684tests/132files pass308.62s/309982.748ms. TypeScript app/node and
full lint pass68514.283ms with one existing auth warning; scoped Python Ruff
passes87.732ms. Local app build28499.077ms and199JS integrity289.258ms pass.
The final full capture has expected negative-test/jsdom stderr diagnostics but
no failed suites/unhandled-error result; no timeout or truncation. Earlier UI11
and quality captures precede main-panel integrations, while full-ui overlapped
edits; they are not final-source certification. Independent bounded review PASS.

Row-lock SQL is reviewed but has no native concurrency/durability proof in this
lane. The separate request-only queue handler and later external dispatcher do
not share this validation transaction: a later contact/content mutation or
queue race remains outside the claim and needs separate evidence/fencing.
This package does not close generic finance/tool approval identity, all-role
coverage, localization of all agent labels, current image or deployment gates.

## Production observation and safety

The user reported signing in to the in-app browser. A read-only AX observation
of `/dashboard/today` confirmed the authorized SuperAdmin surface and mixed
Spanish/English/Russian system labels. No approval, setting, generation, send,
publish, credential or data mutation was submitted. This live older frontend
observation does not verify the local new artifact.

No push/deploy, schema/data migration, Docker start/build, volume reset, package
installation or deletion. Disk observation: 4,881,460KiB (~4.66GiB), below the
10GiB image floor. Nine unrelated dirty paths remain outside this package.
Denied aggregate-v2 and restore preparation stays denied; earlier unguarded
password-reset effects remain INCONCLUSIVE. Overall goal acceptance stays FAIL.
