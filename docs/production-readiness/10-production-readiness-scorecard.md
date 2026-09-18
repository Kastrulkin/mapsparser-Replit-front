# Production-readiness scorecard — working, not final

Updated 18 September 2026. Scores describe evidence at the stated checkpoint,
not an average that can waive a release gate. The original Definition of Done
and unresolved P1 items remain controlling.

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
| Architecture | 3 | [01-system-map.md](01-system-map.md) documents boundaries, execution and approval paths; reviewed isolated compiled profile exists. | Large work areas and startup/migration ownership remain; final whole-diff review is open. |
| Security | 2 | Local authorization, SSRF, session, webhook, publication binding13c and one real hostile-row24e proof; see [03-security-threat-model.md](03-security-threat-model.md). | Historical credential revocation is unknown; final scans, rollout, broader tool coverage and immutable external media bytes remain open. |
| Data integrity | 2 | Full synthetic restore covers288tables/schema/grants/sequences/data; SEND-AMB lifecycle/receipt and current120browser checks pass. | Broader mutation/approval-target coverage and production-backup recovery remain incomplete. |
| Reliability | 2 | Isolated PG16 storage/restart/restore and reviewed duplicate-send/reconciliation checks passed; social-role254/0suite retains13critical realPG lifecycle cases. | Final same-revision full aggregate, immutable image and production recovery proof remain open. |
| Performance | 2 | Image size fell22.2%;50-sample distributions/44prepared reads/tinySQL plans captured. GET now9reads0DDL versus9reads3DDL. | Frontend and sustained HTTP/server/queue capacity remain open; tiny plans are not capacity, comparable medians nearly unchanged and p99 exploratory. |
| Frontend quality | 3 | Reviewed20431224 frontend passes120/120real-API scenarios227.301s over isolatedf0ccbackend, including mobile containment/focus/receipt reconciliation. | Separately synced frontend, not final immutable image. Broader adverse-state and same-revision aggregate coverage remains. |
| UX | 3 | Owner-oriented workflow review and contrast correction are recorded in [05-ux-review.md](05-ux-review.md). | Partner rehearsal and several adverse UI states are still open. |
| Testing | 3 | Clean6c96192c full aggregate:4,538passed/7live-provider skips, including native and Docker PostgreSQL; later stored-role package27tests passes independently reviewed. | Final same-revision aggregate and reconciliation browser after later patches remain; live-provider calls deliberately unexercised. |
| Observability | 2 | Raw captures, scoped runbooks and evidence handoff exist. | No completed production log/image scan, operational dashboard closure or repeated incident rehearsal. |
| Deployment | 1 | Local image/browser and isolated Compose evidence exist. | No audit deployment, production migration, production backup rehearsal or release verification was authorized. |
| Documentation | 3 | System map, threat model, risk register, runbook, demo and evidence records are present. | This scorecard and reports are working drafts; final DoD reconciliation and demo rehearsal remain. |
| Demo readiness | 1 | A synthetic, approval-aware script exists in [08-partner-demo.md](08-partner-demo.md). | It has not been rehearsed; provider and customer data are deliberately out of scope. |

## Interpretation

The arithmetic mean is intentionally omitted. A moderate local score cannot
offset a P1 release gate: historical credential revocation, production restore
proof, supply-chain closure, SEND-AMB browser/release verification, final scans,
server-capacity evidence and demo rehearsal remain open. Fresh whole-diff
review at2f224f05 failed; later social-role/approval-binding packages pass scoped
review but require final combined verification and whole-diff re-review.
Tiny query plans alone do not close performance.
See [09-residual-risks.md](09-residual-risks.md) and
[PROGRESS.md](PROGRESS.md) for the authoritative working state.
