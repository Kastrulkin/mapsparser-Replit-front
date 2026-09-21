# Cumulative source review — 21 September 2026

Status: PARTIAL REVIEW / overall FAIL. This frozen review is not runtime proof.
Frozen range: `30262a5bf7b468e0a6f5a0e3d8262dbef119e075` to
`8be8e45a5a2930607311becebf05a3d456d100b0`.

The adjacent `cumulative-review-inventory-20260921.json` binds all 793 changed
paths to base/head Git blob IDs. They are not 793 runtime files. The original
specification, verdict and problems files retain their previous SHA-256 values.
Thirteen unrelated dirty/untracked files were hash-verified unchanged and
excluded from this committed range. Their working copies are not certified.

## Supplemental review of three deferred infrastructure assertions

Subsequent `vk-upload-notes-20260921.md` records a separately tested
private/rebinding fix for part of P1-BE-01; the finding below is the pre-fix
snapshot. Reviewer `cumulative_frontend_review_20260921` also read all three
deferred infra changed assertions and related contracts in the frozen range,
without imports, tests, network or writes. This supersedes the three-path
deferral below, not the remaining83 backend/evidence gaps.

- **TEST-APPROVAL-AUDIT-01, P2:** `tests/test_approval_boundaries_audit.py:14-28`
  covers literal `True` only. The auditor's `ast.Constant(True)` check does
  not flag unconditional `approval_verified or (1 == 1)`, which retains the
  marker. Current runtime uses `approval_verified`; no present bypass found.
  Add a mutation regression and strengthen AST validation separately.
- **TEST-HEALTH-DB-GUARD-01, P2:** `tests/test_readiness_endpoint.py:196-205`
  returns False from a readiness stub but never proves zero calls; a future
  DB-dependent health handler could pass. Current health is DB-free. Use a
  recording/throwing stub and assert no access. Other reviewed assertions cover
  read-only transaction/timeouts/schema/revision/cleanup and generic /ready;
  opt-in native tests own uniquely named loopback databases.
- **TEST-README-GIT-GUARD-01, P2:** `tests/test_readme_git_workflow.py:31-46`
  exact-token predicates miss `HEAD:main` and `credential.helper=store`.
  Current README contains neither prohibited example. Add falsifiable
  command-variant tests before changing the scanner.

These are static test-quality findings, not executed mutation results or
production failures. Confidence medium pending reproduction; low effort,
small test/scanner scope and low correction risk. Impact: regressions may
evade claimed safety gates. Required for reliable CI before production;
acceptance: unsafe variants fail while current valid instructions pass.

## Actual coverage, not inferred coverage

| Area | Inventory | Actual read-only review | Remaining |
| --- | ---: | --- | --- |
| Frontend | 75 changed paths | Fresh frontend reviewer reports all changed hunks, changed assertions and relevant head callers/contracts reviewed; includes configuration, source, tests and locales | No runtime/build/browser test of this exact revision |
| Backend source | 55 changed src paths | Fresh backend reviewer reports changed-hunk review of all 55; deeper dataflow/contract review at security and lifecycle boundaries | Not a full review of every unchanged caller or every line in large modules |
| Backend test tree, excluding infrastructure assignment | 85 changed paths | Only `tests/test_social_media_delivery_ssrf.py` was fully assertion-reviewed, and `tests/test_social_post_service.py:3978-4070` was partially assertion-reviewed | Other 83 paths were inventory/function-name scan only; they need changed-assertion review |
| Infrastructure | 29 changed paths | Fresh infrastructure reviewer read changed hunks; deeper control-flow review for Compose, migrations, ingress, restore/smoke and CI/harness guards | Hunk review is not executed isolation/restore/CI proof |
| Infrastructure tests | 27 assigned paths | Changed assertion/guard review of 24 paths listed below, not necessarily their complete unchanged contents | 3 paths below not reviewed by that reviewer |
| Evidence/docs | 522 changed paths | Complete blob inventory; root inspected current evidence/hand-off/progress/decisions, historical verdict/problems, release-profile scope and selected risk contracts | NOT full semantic reconciliation of 522 artifacts or their historical test claims |

Infrastructure assertion-reviewed paths (all under `tests/`, extension `.py`):
`test_audit_ingress_proxy`, `test_ci_real_api_staging_contract`,
`test_ci_typecheck_gate_contract`, `test_compiled_table_staging_harness`,
`test_creator_offer_distribution_migration_rollback`,
`test_creator_portal_migration_rollback`, `test_default_test_collection_safety`,
`test_docker_base_pins`, `test_docker_browser_permissions`,
`test_docker_build_context_contract`, `test_docker_frontend_artifacts`,
`test_docker_packaging_tools`, `test_openclaw_smoke_recovery_safety`,
`test_postgres_restore_helper_safety`, `test_readiness_journey_benchmark`,
`test_readiness_journey_load`, `test_readiness_journey_measure`,
`test_readiness_query_plans`, `test_release_compose_contract`,
`test_release_constraints`, `test_seed_journey_partnership_contract`,
`test_staging_compiled_build_contract`, `test_staging_fixture_social_publication`,
`test_work_review_migration_rollback`.

The 3 deferred infrastructure paths are `tests/test_approval_boundaries_audit.py`,
`tests/test_readiness_endpoint.py`, and `tests/test_readme_git_workflow.py`.
The infrastructure reviewer also read `docker/audit-ingress/README.md` as
context; it is a documentation path, not an extra primary infrastructure file.

The backend reviewer's initial general test-coverage wording was corrected to
the exact 1-full/1-partial/83-inventory scope above. The infrastructure reviewer
corrected a scripts-count typo: 15 changed scripts, 29 primary paths total.
Neither corrected claim is evidence that the remaining assertions were checked.

## Retained finding and hardening gaps

### P1-BE-01 — VK response-derived upload target (source candidate)

Head `src/services/social_posts/media_delivery.py:512-531,542-551`:
the approved photo flow obtains `upload_url` from the VK API response and
passes it to `_vk_api_request`, which sends a multipart body via unrestricted
`outbound_urlopen`. `SECURITY.md` treats provider responses as untrusted.
A compromised or malformed provider response is the threat assumption; no
normal-user control of that response, actual exploit, exfiltration or production
incident has been demonstrated.

Root verified this is a pre-existing latent path, not a newly introduced
regression: the baseline contains the same raw transport and response-derived
call in `src/services/social_posts/recommendations_handoff.py`.

Next smallest safe check: locally stub the provider response and transport,
return a private/rebinding upload target, and assert refusal before any multipart
transfer. Also retain a valid public upload success control and bounded response
parsing. No real provider request, publication, production access or DB needed.
The existing asset-fetch SSRF test does not exercise this upload sink; the
existing VK publication test stubs the whole upload helper.

A DNS-pinned/no-redirect POST can prevent private/rebinding SSRF, but by itself
cannot prevent exfiltration to an attacker-controlled public host. HTTPS and a
verified provider-host policy would be a separate destination constraint; do not
invent the allowed host list or assume `api.vk.com` is the upload host.
The existing `public_pinned_post` returns at most 1,000 text characters, so it
is not a drop-in for the full VK upload JSON contract. No fix is claimed here.

### INFRA-01 — P2 hardening: mutable compiled-staging ingress image

`docker-compose.compiled-staging.yml:34` uses `python:3.12-slim`, so the
synthetic proof's proxy runtime can drift. Pin a verified compatible image
digest and cover it in the Compose contract before running that proof.
This is not an escape or exploitation demonstration. The immutable application
release-profile contract explicitly excludes this optional staging fragment.

### INFRA-02 — P2 hardening: mutable hosted-CI action references

`.github/workflows/staging-real-api-nightly.yml:20,21,24,41` uses major action
tags. Review/pin full action commit SHAs and assert them in the workflow contract.
This is a supply-chain hardening gap, not demonstrated compromise or newly
granted production privilege: the workflow uses a normal hosted runner with
`contents: read`. No hosted workflow was executed by this review.

### Rejected or deduplicated candidates

- Frontend missing-recipient/ID draft snapshot was initially called P1. Root and
  reviewer traced backend business/count/unique-ID/text/recipient/current-row
  validation and locking. Empty recipients are explicitly supported for
  draft-only approval; malformed input cannot bypass backend validation.
  **Withdrawn; NO_BUG_PROVEN**, not an external-send vulnerability. Do not impose
  a new nonblank-recipient product requirement from that rejected hypothesis.
- Unversioned APT and missing Python artifact hashes are already recorded in
  `docs/production-readiness/09-residual-risks.md`; not a new INFRA-03 defect.
- An initial inventory-output truncation/parse failure was corrected by a
  smaller metadata read. It is a harness issue, not a product failure.

## Authenticated browser observation requested by the user

The existing in-app tab was actually at `https://localos.pro/dashboard/agents`
(the ambient Today URL was stale). Authorised SuperAdmin UI and a loaded task
list were observed. The available console error/warning collection was empty
at the read, not a guarantee about every past/future request or route.

Clicked History only, without running/creating/approving a task. Initial AX/DOM
still showed overview; subsequent screenshot showed History selected with zero
runs and the correct no-runs empty state. This was delayed/stale observation,
not a demonstrated navigation defect. Mixed Spanish/Russian labels were
observed; user's intended locale and deployed Git revision are unknown.
No login secret/session token or business record was copied into this report.
No settings, provider messages, publications, approvals or DB/schema changes
were submitted. This live observation cannot certify the local reviewed commit.

## Remaining acceptance and next action

Whole FAIL; AC1–9/11 remain FAIL and AC10 remains PASS. No historical verdict
is replaced by this partial snapshot. Source inventory/review is not the final
aggregate, canonical image/AMD64 scan, native measurement, restore or demo proof.
The earlier native aggregate/restore preparation denial remains in force;
it was not retried. Last known local disk evidence is 4,108,936 KiB (~3.92 GiB),
not a fresh disk measurement; the 10 GiB image gate is unchanged.

The separate VK package now proves the private/rebinding correction locally,
and all three deferred infrastructure assertion paths have been statically
reviewed. Next: finish the83 remaining backend changed-assertion reviews,
reproduce the supplemental test-quality candidates, and reconcile evidence
consistency before calling cumulative review complete.
No build, installation, Docker, native DB, restore, cleanup, push or deployment
was performed in this source/browser review.
