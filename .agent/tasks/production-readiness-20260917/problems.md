# Problems and non-PASS criteria

This file records current implementation gaps, not a final independent verifier's findings. Goal remains active. No P0/P1 closure or production-ready claim is inferred from targeted passing tests.

Latest18September checkpoint: user explicitly authorized local Docker startup without reset. Fresh task-only PG16 storage probe and clean a025 ARM64 image/offline Chromium smoke passed; no production action. Native whole-backend5e1ebe79 passed4319tests with117skips; real-API browser111pass3missingcompiledfixture failures. PG16 previously-skipped group rerun is active. Hostfreeabout3GiB after exact old-audit-image/cache cleanup, so no concurrent heavyweight image/scan/load. Earlier temporary artifacts were lost across interruption; durable raw captures survive. These partial successes do not close the remaining whole-goal gaps below.

## AC1 / AC2 — Audit coverage and risks

Inventory/recon and several high-priority reproduced fixes are complete; remaining candidates must be falsified/reproduced before treating them as defects. See the maintained backlog for data compression races, finance partial failure, ambiguous sends, SSRF, viewer mutation and remaining frontend scope callbacks.

Confirmed historical privileged credentials require owner/provider revocation evidence (external blocker on that item only). Do not test/rotate keys or rewrite history without authorization. Local safe work can continue.

## AC3 / AC4 — Aggregate frontend, backend and real API

Baseline backend3542pass19fail691skip1error. All identified fixture groups/rollback/harness defects repaired. ca8 aggregate3622pass691skip1fail21errors exposed two harness causes: invalid isolated test DB name and nested network-guard assertion. Correct-name43pass and guard5pass bothmodes verified; full3fadbabd completed3565pass691skip4fail79errors during Docker/PG I/O failure. All691skip reasons classified in incident report, including668missing isolated OPERATOR_VOICE_TEST_DSN. Safe DSN-based tests need later execution; no live-provider toggles.

Real API finalnative111pass3fail; all three remaining cases need actual runner/profile/approved synthetic-run fixture. Standalone helper's target/claim safeguards were committeda842d648; durable proxy/profile packaging is now under review. Canonical frontend preview flag fixed44d597af but a025image predates it. Do not fabricate completed runs or skip meaningful assertions.

## AC5 — Image, migration and restore

Clean a025 ARM64 image and actual nonroot/network-none/read-only Chromium/pypdf6.16.1/pipcheck smoke pass; subsequent source changes need final image. AMD64 remains. Historical synthetic restore matched288tables data/columns/constraints/revision, but indexes/triggers/views/functions/sequences/grants and production recovery remain unverified; its tempdump is gone. Hardened restore helpera04686de and compiled harnessa842d648 need real invocations. Populated feature downgrade intentionally fails closed.

## AC6 — Security and supply chain

Current tracked-baseline scan is triaged but final current files, Docker layers, runtime logs and resolved Python dependencies are not fully audited. Historical privileged exposure remains unresolved externally. Full threat model including AI tools/tenant roles needs explicit evidence. No absence-of-vulnerability claim.

## AC7 — Measurements

Build/test durations exist; they are not five-journey p50/p95/p99 or load measurements. New one-sample harness is under review:18nominal step successes must not be accepted while content-generation fallback can masquerade as success and provider environment isolation needs strengthening. Legacy financial date/row-mapping defect reproduced in that probe is being fixed separately. Capture realistic baseline/after only after invariants/provider seams pass review.

## AC8 / AC9 — Operations and demo

Static health is not validated dependency readiness. Restore safety/immutable-release/CI/migration-owner concerns remain. Telegram transport stalls were observed read-only in production and not fixed. Prepare and rehearse a10–15minute synthetic demo with integration fallback and confidential-data exclusions.

## AC10 / AC11 — Reports and final verification

Working progress/system map/backlog/changelog/security threat model and05UX exist. Reports00,04,07,08,09,10 remain pending. Final whole-diff independent review and required aggregate reruns have not occurred. verdict.json UNKNOWN is intentional; only its scaffold AC1 is currently populated, so it must be replaced by the fresh final verifier, not treated as complete acceptance coverage.
