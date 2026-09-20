# Draft review admission — 21 September 2026

Parent: `7fd95caaeed88ae1a2480c63afe50b195c5c0086`.
Finding: `UX-DRAFT-REVIEW-ADMISSION-01` (P2, local frontend correctness).

## User task and causal evidence

A business operator reviews draft messages before making an explicit decision.
When the saved snapshot is incomplete, the existing summary says that a new
review is required, yet both detail and employee panels leave confirmation
enabled. The backend rejects the attempt before decision/domain writes; this
is a contradictory interface, not a demonstrated approval bypass.

The independent cumulative frontend review identified this candidate at the
parent above. Root then added actual-panel regressions, without mocking those
panels: five incomplete shapes and a stale/valid/stale rerender per panel fail
at the native disabled-button assertion. RED: 12 failed / 14 passed, exit 1,
6,712.088 ms capture, no timeout/truncation. The failure is not a fixture or
dependency error. The first failing assertion does not by itself prove a real
API request or provider effect.

## Minimal correction

Move the existing completeness condition into `runs.logic.ts` and reuse it in
the summary plus both confirmation controls. The condition remains drafts-only,
version 1, a nonempty item array, and nonblank review text on every record.
Incomplete approval stays visible but disabled; rejection remains enabled when
idle. Both decisions remain disabled while loading. Generic approvals and
complete draft snapshots retain their existing behavior.

No API, backend, DB, schema, package, layout or publication policy changes.
Recipient/count/current-row validation is not duplicated in the browser; the
server remains authoritative for identity and freshness. Rendering current props
directly keeps disabled state current when the snapshot changes. Native button
disabled semantics and the existing visible warning are preserved; no browser
or assistive-technology certification is claimed.

## Verification

All commands use the existing capture helper, named tmux sessions, a cleared
environment, Node 22, the no-egress-compatible guard chain, and `envDir:false`
frontend configs. Only synthetic jsdom test data is used. No authenticated
browser, local API, native DB or Docker runtime was exercised.

- Exact unchanged RED suite after source correction: 26 passed, exit 0,
  5,827.563 ms capture; empty stderr, no timeout/truncation.
- App/node TypeScript and full frontend lint: exit 0, 49,376.496 ms; one existing
  `auth_new.ts:115` explicit-any warning, not a zero-warning result.
- Fresh private Vite build: exit 0, 18,734.316 ms capture / 17.59 s Vite;
  retained third-party PURE annotation and private-outDir warnings. No truncation.
- Build integrity: exit 0, 190.296 ms, 199 reachable JS files; empty stderr.
- Product copy guard: exit 0, 31.706 ms. Its source scans only
  `AgentBlueprintsPage.tsx`, so this is not a new extracted-file copy audit.
- Fourteen source/test/config/lock/guard inputs are hashed in the manifest capture.
- First full unit attempt: TIMEOUT, null exit, 300,002.76 ms, no output
  truncation; 121 file-completion lines, no final suite summary. This was an
  insufficient capture timeout, not a completed PASS or a reproduced product
  failure. A read-only process check found no matching remaining jobs before
  repeating unchanged source/command with a 600-second limit. Initial capture
  remains retained.
- Final full suite: 809 passed in 137 files, exit 0, 317.31 s Vitest /
  318,877.799 ms capture; no timeout/truncation. Stderr is 14,259 characters:
  same line multiset as the previous frozen suite, with the initial four known
  jsdom diagnostics reordered, not byte-identical output. No new diagnostic.
  Fourteen manifest input hashes still match after the completed suite.

Classification: **FIX_PROVEN (bounded local UI)**. Causal checks and the broader
frontend suite pass on the same source; this is not whole-project readiness.

Private build: `/private/tmp/localos-draft-review-build-20260921.5SHhJM/dist`.
Evidence prefix: `draft-review-admission-*-20260921.json` in this directory.
Independent five-file static review is separate from executed root proof in
`draft-review-admission-independent-review-20260921.md`.
Final independent evidence reconciliation is BOUNDED ACCEPTED in
`draft-review-admission-package-review-20260921.md`; it explicitly retains the
whole-tree/release provenance gap and the original whole-project FAIL.
Captured precommit reconciliation exits 0 in 3,838.84 ms: exact 31 owned staged
paths, fourteen matching input hashes, unchanged original status matrix and
historical verdict, nine foreign paths outside the index, and a clean staged
Gitleaks scan of 311,961 bytes. Nonfatal Darwin temp fallback warnings are
retained. The final stage additionally includes that capture and its doc record.

## Cumulative review context

The three `cumulative-*-review-20260921.md` artifacts retain exact coverage of
`30262a5b..7fd95caa`, not the subsequent patch. Root mechanically compared their
explicit path inventories to Git: all 248 changed non-document/evidence paths
are claimed reviewed, plus one legacy README. Frontend/infra/harness report
lists 125; access/test report 90; effects report 34. Coverage capture exits 0
in 1,674.379 ms, with no omissions or truncation. This is inventory proof, not
an automated assertion of semantic correctness. The other 314 documentation/
evidence paths were not all independently reread in this pass.

Reconciliation initially caught a missing release-constraints file and a false
statement that ten social/WhatsApp modules had not changed. Reviewers explicitly
read those frozen diffs and corrected their coverage before closure. No universal
562-file/whole-DoD PASS is inferred.
The network-parent concern was withdrawn after checking the supported writer
and independent readers; no schema/data-repair change was justified.

## Boundaries and remaining work

Original whole-project acceptance remains FAIL. Current full backend aggregate,
authorized synthetic restore, content-path timings, immutable image/native
browser/compiled scenarios, paced partner demo and final all-DoD review remain.
Renewed aggregate/restore preparation permission is still pending; earlier
denials must not be retried through another route. Historical unsafe-reset
effects remain INCONCLUSIVE. Latest Mac headroom 6,654,180 KiB (~6.35 GiB) is
below the 10 GiB image floor. Nine foreign paths are excluded. No cleanup,
production/DB/provider action, Docker, push or deployment occurred.
