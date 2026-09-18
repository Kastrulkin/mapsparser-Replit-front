# Fresh independent whole-diff review — `272794a4`

## Later evidence addendum — root, after 18 September 14:46 UTC

The independent report below is preserved as a pre-aggregate snapshot. Root
records a subsequent result, separately reviewed by `operator_chat_review`:
`raw/full-backend-272794a4.json` passes4728/7intentional live-provider skips/
6warnings656.63s; capture669.910516s,exit0/not timed out/untruncated. Migration
and tests return0; fresh DB OID5025701 is independently confirmed absent after
successful cleanup. AC4 is now PASS in its local/synthetic contract scope.
No claim is made that the fresh whole-diff reviewer re-read this later result.
The overall FAIL and remaining browser/image/security/demo gates are unchanged.

Further root addendum, after15:18UTC: native current272backend plus verified
unchanged frontend passes117/117 in261.027621s captured; scoped reviewer
independently reconciles raw/cleanup. This excludes3compiled-runner cases and
does not guarantee all console errors were observed. Bounded240read HTTP
checkpoint also passes with64.280315s timed wall; full measurements/limits are
in report04. Neither later result was reviewed by the original fresh reviewer.
Current image/security/demo and final all-DoD gates remain open.

Further root addendum, after15:30UTC: scoped reviewer independently accepts
HTTP240/240 and frontend60/60 counts/quantiles and runtime captures. Frontend
uses historicalf0ccbackend/unchanged204frontend, zero page errors/overflow,
eight byte-matched assets. Root viewed six screenshots. Report04 records full
method and limits; no production/capacity/current-image claim. This is a root
record of a later scoped review, not a revision of the original fresh verdict.

Root addendum after15:49UTC: later exact-criterion scoped review accepts AC3
(critical frontend contracts) and AC10 (current truthful documentation), in
addition to AC4. AC2 retains partial P1 image/reproducibility findings. AC7
retains the original failed auth-baseline/null-quantile issue; a supplemental
working-reference comparison is only prepared. The original matrix below is
historical, unchanged; overallFAIL and remaining release gates are preserved.

## Original independent snapshot

**Verdict: FAIL — not production-ready.** This is a read-only, source-and-
evidence review of
`30262a5bf7b468e0a6f5a0e3d8262dbef119e075..272794a439a76204536480f158e79276ccd7b318`
(179 files, 25,367 additions and 1,504 deletions). It is a new review, not a
restatement of `FRESH_REVIEW_20260918.md`. No production, provider, network,
Docker, database, test, or evidence mutation was performed.

The only write in this review is this report. “No evidence mutation” means that
no captured result, task-bundle record, or existing readiness document was
altered.

## Review result

`git diff --check` is clean. The changed authorization and publication paths
were inspected directly, including `src/core/auth_helpers.py`, operator mobile
confirmation, finance/services write paths, webhook admission, contact egress,
and the social approval/claim/finalization path.

I found **no additional reproduced P0/P1 source regression** in this bounded
review. In particular, the earlier reviewer’s three source candidates have
materially changed:

* social writes load through `_load_post_for_write` and then
  `_require_business_write_access` (`src/services/social_posts/dispatch_reports.py:1352`);
* the business-data GET now authorizes before its reads and contains no
  compatibility DDL (`src/legacy_routes/public_requests.py:962-985`);
* API publication snapshots hash the target binding and strict media descriptor
  (`src/services/social_posts/approval_binding.py:163-205`), and claim/finalize
  preserves an ambiguous provider outcome as `publishing` for reconciliation
  (`src/services/social_posts/publication_lifecycle.py:78-363`).

Those observations are source inspection, not substitutes for an exact-head
aggregate, real provider proof, or an externally verified rollout.

## Coverage boundary

This was a whole-diff **inventory and risk review**, not a line-by-line
reimplementation audit of every changed line. I inventoried all 179 changed
paths and read the following executable/high-risk groups directly:

* all 29 `src/` files: authentication/session helpers; public and operator API
  routes; finance/services writes; webhook authentication/admission; outbound
  network pinning; readiness; and the social approval, media, provider, claim,
  finalization, and dispatch paths;
* 3 Alembic revisions, 8 Docker/Compose/ingress/package-context files, 12 CI,
  staging, restore, performance, and query scripts, and the nightly workflow;
* all 22 frontend paths at the change/test-contract level, with focused reading
  of the content/publication and scope changes; and
* the 71 changed test paths as contracts/coverage inventory, plus the frozen
  task bundle and readiness reports/raw captures relevant to AC1–AC11.

The remaining changed paths were list-level reviewed for category, ownership,
and evidence linkage: 21 documentation files, six task-bundle files, and
top-level README/security/requirements/pytest/configuration material. This
coverage supports the findings below; it does **not** claim exhaustive semantic
verification of all 179 files.

## Acceptance matrix

| AC | Status | Current, evidence-bounded reason |
| --- | --- | --- |
| AC1 | FAIL | Required inventory and reports exist, but the task evidence itself says area-by-area closure is incomplete. |
| AC2 | FAIL | Confirmed findings have focused corrections and causal tests, and the `272794a4` 104-check role/subscription capture is meaningful. The remaining failure is the missing final independent/exact-head reconciliation required by AC11, not a claim that every conceivable future role/tool candidate or provider exactly-once property must be proved. Documented external limitations are permitted by AC2 when owner, impact, and temporary protection are recorded. |
| AC3 | FAIL | Frontend lint/typecheck/unit/build and selected browser evidence are useful, but no complete current real-API desktop/laptop/mobile adverse-state run is recorded. |
| AC4 | FAIL | The last whole backend run is from `3dca5fda`; the `272794a4` capture is a 104-check scope, not the required final main-suite/integration aggregate. |
| AC5 | FAIL | Useful canonical ARM64 image/smoke, migration, and synthetic restore work exists, but an exact-head canonical Docker build/runtime/migration/rollback rehearsal remains pending. AMD64 is a deployment-platform risk to record separately, not an unconditional AC5 requirement. |
| AC6 | FAIL | Historical credential revocation is owner-confirmed work still pending; final current image/log/OS/native/npm/license triage is also unfinished. |
| AC7 | FAIL | `04-performance-report.md` and `journey-measure-serial-8ebec5ca.json` contain five before/after cold-process distributions with 50 measured samples per revision, plus an independently reconciled prepared bounded profile, resource snapshots, and query plans. The remaining gap is frontend and sustained HTTP/server/queue capacity evidence, and that the distribution source predates later head changes—not absence of five-flow measurement. |
| AC8 | FAIL | Release-profile and readiness contracts are not a verified release/rollback/provider-recovery run. CI's real-API job is a contract, not an execution result. |
| AC9 | FAIL | The safe demo plan exists but has not been rendered and rehearsed end-to-end with its fallback. |
| AC10 | PROVISIONALLY MET | All named reports, progress/handoff/decisions/commands/security, residual-risk register, and evidence-backed 0–5 working scorecard exist. They honestly state current limitations. This does not convert the overall release verdict to PASS; their final reconciliation must incorporate the result of the currently pending exact-head aggregate. |
| AC11 | FAIL | This review satisfies the fresh whole-diff review portion only. The required final aggregate rerun and authoritative exact-head evidence reconciliation remain open. |

## Actionable release blockers

1. **P1 / release gate — final exact-head verification is pending.**
   `docs/production-readiness/HANDOFF.md:6-24` identifies `272794a4` as the
   head and says the last full-suite source remains `3dca5fda`; task
   `evidence.json` currently marks AC1–AC11 FAIL. A scoped 104-pass result cannot prove
   AC3/AC4/AC11. Run the prepared isolated final backend aggregate and current
   frontend/browser stages against a frozen `272794a4` archive, retaining raw
   exit status, scope, skips, environment identity, and cleanup result.

2. **P1 / external release gate — secrets and supply-chain closure are not
   owned by code.** `evidence.json` AC6 records unknown historical credential
   revocation and pending image/log/license scans. The owner must attest to
   revocation (without provider-key testing); then complete redacted scans and
   license/image triage for the release artifact.

3. **P1 / operational release gate — deployment/recovery evidence is not yet
   current.** `evidence.json` AC5/AC8 records local-only Docker and synthetic
   restore evidence, with current release/image/rollback/provider recovery
   unproven. Complete the documented disposable release rehearsal before any
   production deployment authority is sought.

## Evidence limitations retained deliberately

The evidence bundle’s authoritative status is `overall_status: FAIL`. Earlier
raw failures, browser gaps, and historical review findings remain useful audit
history; they are not silently converted to passes. The `272794a4` scoped
role/subscription capture is a local check and does not establish a release
verdict. No claim here implies provider credentials, provider delivery,
production data, production schema, or a production deployment was tested.

At review time the exact-head backend aggregate was reported as running, with
the intended output path
`.agent/tasks/production-readiness-20260917/raw/full-backend-272794a4.json`.
It was not read or treated as a result here. The frontend Git tree was reported
as identical to the prior verified `3dca5fda` tree; that narrows source
staleness for frontend checks but does not substitute for the pending
exact-head backend result or final evidence reconciliation.
