# Residual risks — working register

Updated19September2026. These are remaining risks or verification gaps, not
newly demonstrated exploits. Fixed local findings and their evidence remain in
[02-audit-backlog.md](02-audit-backlog.md) and [06-change-log.md](06-change-log.md).
The audit branch has not been deployed; local proof is not production proof.

Latest backend source is7bb9f996: independently reviewed callback alert rotation
passes29focused tests in12.04s, with no residual native test schemas. This does
not recertify the full backend/image. Review-locale frontend work is locally
focused FIX_PROVEN and has a narrow three-viewport RU/EN/EL browser result against
historical synthetic staging, but does not establish all-locale or whole-workflow
runtime coverage. Previous runtime source is4f333aa7, the callback package.
Its final25focused tests and separate73API/schema/native tests pass; the sets
overlap. They do not re-certify the full backend,117browser cases or image.
Earlier additions are locally reviewed272794a4 (104stored-role/subscription
checks),3ac13d87 (11fake-command CI contracts), and a00ac558 (13actual Compose
render/startup contracts). These respectively strengthen mutation admission,
isolated CI definition and opt-in migration/image ownership. Full272backend
passes4728/7intentional provider skips/6warnings656.63s with independentAC4PASS;
that source's native browser passes117/117 and bounded HTTP240/240 plus frontend
60/60 observations have independent scoped PASS. Final image and hosted CI
execution are not proven. Do not treat these packages as a closed release gate.

TEST-E2E-04 removes a two-journey console-filter blind spot with21pure
regressions, scoped strictTS/lint and independent review. Local space is now
about5.5GiB after approved cleanup and bounded verification; the first native6 retry failed in its
process controller before tests. A minimal process-only reproduction confirms
the nested topology limitation. The reviewed sole-owner retry now passes6/6
in22.0s, capture48.938396s, with independent DB/process cleanup verification.
Historical117results retain their original limitation. Docker peak-plus-reserve remains
unmet. No production, image or readiness score is promoted.

New scoped evidence: partial managed-browser demo verifies synthetic finance
preview/apply/duplicate history but not the intended partnership reason or a
paced complete rehearsal. OPS-CALLBACK-01 has causal real-PG RED and reviewed
local finalGREEN25/25, including10 native recovery/race/tenant cases and6shell
cases for no implicit recovery plus incident snapshots. Its remaining
release/image proof is separate; no production callback is claimed recovered.
UX-LOCALE-05 is locally fixed with focused RU/EN/EL proof and all-ten-locale
source keys. Its browser confirmation now passes3/3 only against the historical
synthetic backend/current built frontend; full workflow, all locales, current
backend/image and deployment remain separate. See backlog02.

| Risk / evidence | Priority and impact | Likelihood / temporary protection | Required next step |
| --- | --- | --- | --- |
| Alert scan rotation is process-local |P2 operational limit under frequent restarts; progress is not durable/shared|Lexical-prefix starvation is causally fixed in7bb9f996 and verified by101-tenant test; every worker restart resets its own cursor|Current-image verification, then assess durable/shared scheduling only if restart/topology evidence warrants it; no live incident or global-fairness claim |
| Deployment smoke still has ordinary mutating phases |P2 operational scope; calling it is not a read-only diagnostic|Implicit alert-triggered replay removed and tested; nested capability/outbox smoke still creates actions/dispatches normal pending/retry|Use specific read-only metrics for diagnosis; require separate authority for full smoke, manual replay and deployment |
| Historical privileged credential exposure; offline scan confirmed old provider keys, revocation unconfirmed |P1 before production; former credentials might still authorize access|Current validity unknown. Do not use/test/publish old values; owner confirmation requested|Authorized owner/provider revocation evidence and separately approved history policy; no unilateral rotation/rewrite|
| Reset URL credential is logged by the SetPassword browser component |P2 before production; source/build artifact can disclose a real reset token to local console collection or screen capture|Confirmed source and current cookie-build artifact path only; synthetic unit token is not evidence of a real-secret event or bearer-token exposure|Add no-raw-console regression, remove/redact logging, rebuild and inspect the intended release artifact; do not probe real tokens|
| Reviewed auth/webhook/role/SSRF patches remain local |P1 release gate; intended protections are not certified live|Deployment deliberately not authorized by this audit; retain explicit boundary|Approve an exact release, provider webhook rebind/configuration where required, then verify live flow; no broad dirty-tree sync|
| App version constraints and base pins lack final image proof; apt/artifact hashes and bot/target-runtime closure remain |P1 before production; supply-chain/build drift or untriaged advisories|Exactb43 audit104packages/0skips finds only pip24.0;26.2pin and app101constraints plus3tools. Node/Python base indexes now pinned with ARM64/AMD64 metadata and14static contracts|Build/version/re-audit and OS/native/image/log scan; index availability is not an AMD64 build. PyMuPDF license basis awaits owner confirmation, not a violation claim|
| Production backup recoverability not rehearsed |P1 before production changes; possible recovery failure|Independent local synthetic full-schema/data restore passes; production datasets/backup transport/permissions differ|Under separate authority, verify an actual backup in an isolated restore target before schema change; never overwrite live DB|
| Wider mutation-role coverage incomplete |P1 investigation; potential unauthorized mutation|Several finance/blueprint/Operator chat boundaries reproduced and fixed; remaining candidates are not confirmed bugs|Finish targeted real-DB negative matrices; preserve tenant and stored-role checks|
| SEND-AMB and approval binding are locally fixed but final release proof remains |P1 release gate; deployed old approval can still be insufficiently bound|Reviewed13c1f36a main252pass plus separateviewer9pass cover frozen target/account/media, drift and uncertainty; receipt reconciliation has scoped120browser proof|Final combined image/aggregate, then separately approved rollout. External object/URL byte immutability is not established; no exactly-once claim or blind retry|
| WhatsApp uncertain outcomes need reconciliation |P1 integration limit; admission is not exactly-once delivery|Durable duplicate admission and ambiguous-state visibility fixed locally|Explicit operator reconciliation/provider evidence; do not reset ambiguous admissions to force a resend|
| Local Docker had filesystem I/O incident; old volumes not certified |P2 audit infrastructure; old verification invalid or local state damaged|Approved no-reset restart and fresh PG16 storage/restart/restore/checks pass; old volumes not reused|Do not erase/repair user volumes. Maintain headroom, preserve dumps and stop heavy work on I/O errors|
| Node engine mismatch is fixed locally; broader supply-chain gap remains |FormerP2 reproducibility finding|ba891be4 and cleanf0cc Node22 bothfrontend image builds pass55.386s; actual nonroot/offline smoke passes3.721s|Final image/dependency scan is separate; no broad upgrade or production claim|
| Readiness integration pending; migration startup ownership still coupled |P2 operations; unhealthy app may accept traffic or restart implies DDL|Reviewed52292e6e adds bounded read-only `/ready`,24native/route/CLI/schema tests pass; `/health` unchanged, no image/deployment proof yet|Verify endpoint in frozen image, then separately authorized rollout; preserve deliberate migrator/run modes|
| Final combined image and whole-diff closure incomplete |P2 release gate; selected green evidence may miss integration regression|Current272full backend4728pass/7live-provider skips and native117browser pass; frontend591units/72mockbrowser/TS/lint/build stages plus artifact proof pass without relabeling original exit1. Historical120includes compiled runtime. Fresh272whole-diff review found no additional reproduced P0/P1 in bounded coverage; original verdict remains FAIL|Final combined image/compiled-runtime proof, remaining scoped coverage and independent closure; do not sum overlapping suites|
| Production-capacity evidence incomplete |P2 capacity; bounded synthetic latency is not capacity|50-sample before/after distributions retain baseline errors; current272HTTP240/240 over64.28s includes10resource snapshots. Frontend60/60 observations use historicalf0ccbackend/unchangedfrontend. All have scoped review;8user earlier run retains login429 failures|Realistic server/queue capacity remains; low-load/tiny fixtures and10browser samples per group cannot establish production limits or speedup|
| Demo and broader error/large-data/slow-network accessibility coverage not rehearsed |P2 demo; presentation may encounter unsupported/incomplete paths|Synthetic10–15min script clearly separates seeded outcomes from real runner; no live provider data|Rehearse and capture expected outcomes/fallbacks; keep confidential and unimplemented areas out of claims|
| Large workspaces and remaining structural debt |P3 after correctness; maintainability cost|Scoped fixes preserve existing modules; no architectural rewrite without benefit|Use measured churn/runtime evidence to select the next small module extraction, with existing regression coverage|

The controlling release decision is the original task's Definition of Done,
not the existence of these reports. A documented gap is not automatically an
external blocker or an acceptance-criteria pass.
