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
| Security | 2 | Local authorization, SSRF, session, webhook and publication-lifecycle work has focused evidence; see [03-security-threat-model.md](03-security-threat-model.md). | Historical credential revocation is unknown; final scans, rollout and actual provider-recipient/media approval binding remain open. |
| Data integrity | 2 | Full synthetic restore covers 288 tables/schema/grants/sequences/data; reviewed SEND-AMB lifecycle package passes 237 backend tests. | Broader mutation/approval-target coverage, new browser integration and production-backup recovery remain incomplete. |
| Reliability | 2 | Isolated PG16 storage/restart/restore probe and reviewed duplicate-send/reconciliation tests passed. | Final same-revision full aggregate, browser integration and production recovery proof remain open. |
| Performance | 2 | Image size fell 22.2%; independent review reconciled 50-sample cold-request distributions for five journeys. [04-performance-report.md](04-performance-report.md) preserves baseline errors. | Prepared-target load, query-plan and capacity results remain open; comparable medians nearly unchanged and p99 exploratory. |
| Frontend quality | 3 | Isolated real-API browser checkpoint: 114/114 in 215.263s on `8ebec5ca` frontend over `4a8` backend. | This predates the reconciliation UI; its browser test and broader error/slow-network/large-data coverage are incomplete. |
| UX | 3 | Owner-oriented workflow review and contrast correction are recorded in [05-ux-review.md](05-ux-review.md). | Partner rehearsal and several adverse UI states are still open. |
| Testing | 3 | Native checkpoint: 4,319 passed/117 skipped; separate PG16: 264 passed; separately gated creator: 1 passed; latest social package: 237 backend/19 UI. | Separate scopes, not one aggregate; synthetic provider outcomes/lifecycle pass, live-provider calls remain unexercised, and final same-revision coverage is pending. |
| Observability | 2 | Raw captures, scoped runbooks and evidence handoff exist. | No completed production log/image scan, operational dashboard closure or repeated incident rehearsal. |
| Deployment | 1 | Local image/browser and isolated Compose evidence exist. | No audit deployment, production migration, production backup rehearsal or release verification was authorized. |
| Documentation | 3 | System map, threat model, risk register, runbook, demo and evidence records are present. | This scorecard and reports are working drafts; final DoD reconciliation and demo rehearsal remain. |
| Demo readiness | 1 | A synthetic, approval-aware script exists in [08-partner-demo.md](08-partner-demo.md). | It has not been rehearsed; provider and customer data are deliberately out of scope. |

## Interpretation

The arithmetic mean is intentionally omitted. A moderate local score cannot
offset a P1 release gate: historical credential revocation, production restore
proof, supply-chain closure, SEND-AMB browser/release verification, final scans,
prepared-target load evidence, demo rehearsal and independent whole-diff review
are all still open. See [09-residual-risks.md](09-residual-risks.md) and
[PROGRESS.md](PROGRESS.md) for the authoritative working state.
