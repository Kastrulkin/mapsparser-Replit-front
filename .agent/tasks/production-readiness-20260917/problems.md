# Problems and non-PASS criteria

Updated 18 September 2026, 10:58 UTC. Maintained gap register, not a fresh
independent verifier's verdict. Goal active; audit changes local only.
Production, provider effects and user Docker volumes are out of scope.
Historical failed captures are retained, not rewritten as green.

## Verified checkpoints, not whole-goal acceptance

- Clean6c96192c backend:4538 passed,7 disabled live-provider skips,5 upstream
  SWIG warnings;395.49 seconds pytest /403.727 captured. Includes nativePG15,
  DockerPG16 and Python/browser regressions.
- Same frontend: TypeScript passes, lint0errors/1existingwarning,588 unit tests
  and72 mocked browser scenarios pass;495.068 seconds captured.
- Current real-API checkpoint:120/120browser cases onf0ccbackend/20431224frontend,
  exit0/no timeout,227.301s. Prior116/117overflow and117/120focus-return failures
  are retained. Separately synced dist is not final immutable-image proof.
- Reviewed125900b2 service/content stored-role fix: realPG red and27focusedgreen,
  not yet in a full aggregate.
- Synthetic full-schema/data/ACL PG16 restore and migration guards pass;
  not a production-backup recovery rehearsal.
- Five-journey50-sample and prepared44/44 dashboard-read load results have
  independent reconciliation; limits in report04.

## AC1 / AC2 — Audit coverage and known risks

System map/backlog cover major surfaces and reproduced fixes, not exhaustive
certification. Wider role/object and approval-target coverage remain partial.
Social durable intent fixes the reproduced retry defect locally, but approval
fingerprint does not bind provider recipient/media. Historical privileged
exposure needs owner/provider revocation evidence. No live key testing,
rotation or history rewrite. That item does not block other safe local work.

Fresh review found social-post mutation services use read-role access; guarded
nativePG RED2 now shows direct/network viewers receive200 instead of403 on
prepare, while6controls pass. The first fixture-failure capture is retained.
Reviewed mutation-boundary correction813609cc passes254checks/0skips42.39s,
including13real-PG lifecycle cases. Earlier233/21legacy-fake failures retained.
Approval-binding realPG RED now shows changed fake destination before/after
claim;7fail/1unchanged positive pass. Frozen-descriptor correction remains.
GET business-data causal RED3 independently proves DDL attempts before denied
403 and owner-only rejection of legitimate member/viewer readers. Reviewed
2d875357 removes request-time schema maintenance and preserves canonical read
access;15new/adjacentreal-PG tests pass22.26s. Earlier empty SQL-spy
capture was false-green and is not evidence of no writes.

## AC3 / AC4 — Current aggregate and real API

f0cc includes service/content role and query-harness changes after green6c.
Required: final same-source backend/frontend/image aggregate after remaining
corrections;120real-API cases now pass at the scoped checkpoint. Mocked UI is not stored-role/DB/provider
proof. Wider mutation-role and adversarial AI/tool matrices remain incomplete.

## AC5 — Image, migration and restore

Node22 builder correction ba891be4 now has actual f0cc clean image proof:
bothfrontends build55.386s, ARM64 nonroot/read-only/offlineChromium/pypdf/pipcheck
smoke3.721s passes. First attempt failed before compilation because sanitized
PATH omitted Docker credential helper, not a product defect. Onlyownedstaging
app updated4.533s; HTTP200/health green. Current separately synced frontend
passes120browser cases; final combined image and AMD64 remain.
Populated feature downgrade intentionally fails closed. Production-backup
isolated restore requires separate authority; synthetic full restore passes.

## AC6 — Security and supply chain

Current f0cc tracked-source and post-remediation history delta scans found only
triaged prose false positives. Final image, resolved runtime dependencies,
licenses and redacted logs need scanning/triage. Floating Python resolution/
base tags remain. Source scans cannot prove historical key validity or runtime
advisory closure. AI/tool coverage distinguishes realPG, fake adapters and
mocked cursors; no full attacker-prompt/sandbox attack claim.

## AC7 — Performance

Five-flow measurements retain baseline business-data errors; comparable medians
nearly unchanged. Prepared4user/2pair/5cycle44/44 is in-process Flask/SQL, not
HTTP/Gunicorn throughput. Eight-user run correctly failed the unchanged same-IP
login limiter. Follow-up204SQL proof passes:4authreads, business9reads0DDL
versus9reads3DDL before; tinyfixtureplans and exact disposable DB removal verified.
Frontend/sustainedserver/queue capacity remain open.

## AC8 / AC9 — Operations and demo

Liveness is not dependency readiness. Deliberate migration ownership, immutable
release/rollback, CI, observability and provider recovery remain. Synthetic
10–15minute demo script exists but is not rehearsed end to end. Automated
scenarios support but do not replace that rehearsal.

## AC10 / AC11 — Reports and review

Reports00–10 exist as working documents; final reconciliation/current commands
remain. Fresh-session reviewer (fork_turns=none) completed30262a5b..2f224f05
with FAIL forAC1–AC11 and a new social-role candidate. Earlier thread-limit
obstacle is resolved. Final corrected-revision aggregate/re-review remains.
Placeholder proof files are not acceptance evidence; structural validator
success only confirms file presence. Overall FAIL remains until criteria met.
