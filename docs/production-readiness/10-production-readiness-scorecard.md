# Production-readiness scorecard — working, not final

Updated 19 September 2026. Scores describe evidence at the stated checkpoint,
not an average that can waive a release gate. The original Definition of Done
and unresolved P1 items remain controlling.

Current frozen6eec full backend aggregate now passes4751tests/7intentional
live-provider skips/6warnings652.30s, capture659.230650s/exit0/no timeout/truncation.
Root postchecks confirm owned nativeDB identity, schema/session/process and
testcontainer cleanup. Later seed/test1e955718 has separate2focused/44overlapping
adjacent passes; it is not in that archive. No score is promoted: current image,
retained demo update/rehearsal and other original release gates remain open.

Latest committed backend7bb9f996 adds bounded callback alert rotation with
29passing tests and independent review. Earlier4f333aa7 closes callback
recovery/smoke defects with25focused and73overlapping API/schema/native checks.
The subsequent6eec aggregate covers these backend changes; current image proof
remains open.
No score is raised and overall readiness remains unproven.

New frontend39aeeff9 removes two raw reset-credential console logs with a causal
synthetic regression,28focused/adjacent passes, typecheck/lint/build/integrity
and before/after built-asset proof. Independent scoped reviewPASS. Full new
frontend units pass616/128files309.65s at the same source; do not extend the earlier browserartifact
identity or claim deployment/currentimage proof. Scores remain unchanged.

Earlier local272794a4 adds104review/mobile-role/subscription tests with scoped
independentPASS;3ac13d87 adds an isolated real-API CI definition (11contract
tests), and a00ac558 adds opt-in release configuration (13render/startup
contracts). The full272aggregate now passes4728/7intentional provider skips/
6warnings656.63s, independently accepted for AC4. Fresh whole-diff review has
no additional reproduced P0/P1 in its bounded coverage; overall verdict FAIL.
That native browser checkpoint passes117/117; hosted CI and current runtime image remain
pending. A bounded240-read HTTP profile and60frontend timing samples have scoped
independent PASS. No score is raised solely by these bounded additions.
Frontend is no longer identical to3dca5fda: current review-copy localization
passes615units before removal of four duplicate identical locale keys, then
TypeScript/4focused tests/lint/both builds and asset integrity after that fix.
The bounded review/copy browser follow-up passes3/3 in5.951s on a separately
built cookie-enabled frontend over historical synthetic backend; it is not
an updated117-case suite or currentimage. Independent criterion review
accepted AC3/AC4/AC10 at the earlier checkpoint; overall release remains FAIL. AC10 is documentation
completeness/current truthfulness, not a higher maturity score or release gate waiver.

## Rubric

| Score | Meaning |
| ---: | --- |
| 0 | No usable evidence, or the category's basic function is unusable. |
| 1 | Initial implementation or narrow checks only; major release gates are open. |
| 2 | Partial evidence and safeguards; important environment, coverage or operational gaps remain. |
| 3 | Substantial isolated evidence; production/release proof is still incomplete. |
| 4 | Release-grade evidence for the intended scope, with only bounded non-blocking follow-up. |
| 5 | Repeated production-equivalent evidence, operational rehearsal and independent closure. |

## Scores

| Category | Score / 5 | Evidence | Why it is not higher |
| --- | ---: | --- | --- |
| Architecture | 3 | [01-system-map.md](01-system-map.md) documents boundaries, execution and approval paths; reviewed isolated compiled profile and fresh272whole-diff review exist. | Large work areas and release startup/migration ownership verification remain. |
| Security | 2 | Local authorization, SSRF, session, webhook, publication binding13c and one real hostile-row24e proof; see [03-security-threat-model.md](03-security-threat-model.md). | Historical credential revocation is unknown; final scans, rollout, broader tool coverage and immutable external media bytes remain open. |
| Data integrity | 2 | Full synthetic restore covers288tables/schema/grants/sequences/data; SEND-AMB lifecycle/receipt and earlier117native browser checks pass; historical120includes compiled runtime. | Broader mutation/approval-target coverage and production-backup recovery remain incomplete. |
| Reliability | 2 | Isolated PG16 storage/restart/restore and reviewed duplicate-send/reconciliation checks passed;272full backend passes4728;4f333aa7 adds reviewed callback quarantine/explicit recovery proof. | Current immutable image and release recovery proof remain open; frozen6eec aggregate4751passes is recorded above. |
| Performance | 2 | Image size fell22.2%; five-flow distributions,240current HTTP reads/64.28s and60frontend observations are captured. GET now9reads0DDL versus9reads3DDL. | Realistic server/queue capacity remains open; tiny fixtures are not capacity, comparable medians nearly unchanged and browser p99 exploratory. |
| Frontend quality | 3 | Checkpoint272backend + unchanged built frontend passes117/117real-API desktop/laptop/mobile scenarios; historical120includes compiled runtime. Six new screenshots and60loads show no pageerror/overflow. TEST-E2E-04 has21pure tests plus6/6 actual owner reviews/finance scenarios at archived641. | Not final immutable image or117-case collector rerun; historical console limitation retained. Broader adverse-state/accessibility coverage remains. |
| UX | 3 | Owner-oriented workflow review and contrast correction are recorded in [05-ux-review.md](05-ux-review.md). | Partner rehearsal and several adverse UI states are still open. |
| Testing | 3 | Clean272794a4 full backend:4,728passed/7live-provider skips, including native/Docker PostgreSQL; frontend591units/72mockbrowser/TS/lint/build stages plus separate exact-source artifact proof;117native real-API cases at that checkpoint. Later4f333aa7 has25focused/73overlapping adjacent passes; current backend7bb9f996 has29focused passes and frontend993349b5 has4exact-current focused plus3browser passes, with615units before duplicate-key removal. | Combined current image/compiled runtime and broader mutation-role coverage remain; later6eec aggregate4751 and current frontend616units pass as recorded above. Original frontend capture retains its helper-postcondition exit1. Live-provider calls deliberately unexercised. |
| Observability | 2 | Raw captures, scoped runbooks and evidence handoff exist. | No completed production log/image scan, operational dashboard closure or repeated incident rehearsal. |
| Deployment | 1 | Local image/browser and isolated Compose evidence exist. | No audit deployment, production migration, production backup rehearsal or release verification was authorized. |
| Documentation | 3 | System map, threat model, risk register, runbook, demo and evidence records are present. | This scorecard and reports are working drafts; final DoD reconciliation and demo rehearsal remain. |
| Demo readiness | 1 | Script08 now has a partial managed-browser pass including actual finance preview/apply/duplicate history. Review-copy debt is locally fixed with scoped3-view browser proof. | Intended partnership reason is absent from retained fixture and a paced full rehearsal remains. Provider and customer data are deliberately out of scope. |

## Interpretation

The arithmetic mean is intentionally omitted. A moderate local score cannot
offset a P1 release gate: historical credential revocation, production restore
proof, supply-chain closure, SEND-AMB browser/release verification, final scans,
server-capacity evidence and demo rehearsal remain open. Fresh whole-diff
review at272794a4 still records incomplete release gates despite no additional
reproduced source P0/P1 in its stated coverage. Later full272 backend passes;
current native browser also passes117; image/compiled runtime and other gates
are not waived by those results.
Tiny query plans alone do not close performance.
See [09-residual-risks.md](09-residual-risks.md) and
[PROGRESS.md](PROGRESS.md) for the authoritative working state.
