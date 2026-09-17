# Problems and non-PASS criteria

This file records current implementation gaps, not a final independent verifier's findings. Goal remains active. No P0/P1 closure or production-ready claim is inferred from targeted passing tests.

Latest local infrastructure blocker: Docker/EXT4 I/O failures during final3fadbabd suite and next image build/scan. Complete run is NOT green (3565pass691skip4fail79errors); current host2.6GiB, restart/recovery affects other user containers and permission was requested. See incident report. No heavy jobs remain running. Guard-only restore/compiled packages are reviewed/committed with20fake tests, not actual restore/compiled runtime proof. Existing following phase descriptions are prerequisite coverage, not authorization to rerun Docker before recovery.

## AC1 / AC2 — Audit coverage and risks

Inventory/recon and several high-priority reproduced fixes are complete; remaining candidates must be falsified/reproduced before treating them as defects. See the maintained backlog for data compression races, finance partial failure, ambiguous sends, SSRF, viewer mutation and remaining frontend scope callbacks.

Confirmed historical privileged credentials require owner/provider revocation evidence (external blocker on that item only). Do not test/rotate keys or rewrite history without authorization. Local safe work can continue.

## AC3 / AC4 — Aggregate frontend, backend and real API

Baseline backend3542pass19fail691skip1error. All identified fixture groups/rollback/harness defects repaired. ca8 aggregate3622pass691skip1fail21errors exposed two harness causes: invalid isolated test DB name and nested network-guard assertion. Correct-name43pass and guard5pass bothmodes verified; full3fadbabd completed3565pass691skip4fail79errors during Docker/PG I/O failure. All691skip reasons classified in incident report, including668missing isolated OPERATOR_VOICE_TEST_DSN. Safe DSN-based tests need later execution; no live-provider toggles.

Real API full baseline95pass19fail; patched targeted33pass proves original registration/mobile issues, not all114cases. Compiled browser proof lacks actual runner/profile/approved synthetic-run fixture. Standalone helper has hardcoded target and unscoped queue claim; adapt safely before use. Do not fabricate completed runs or skip meaningful assertions.

## AC5 — Image, migration and restore

Clean ARM64 packaging and browser-enabled ca8 image pass including actual nonroot/network-none/read-only Chromium launch. Empty migration/23rollback tests pass.3fadbabd data-patched build failed on containerd I/O; AMD64 remains. Actual synthetic consistent-snapshot restore matches288tables data/columns/constraints/revision; indexes/triggers/views/functions/sequences/grants and production recovery unverified. Hardened restore helpera04686de and compiled harnessa842d648 are independently reviewed/committed,20fake tests pass; real invocation awaits Docker recovery. Populated feature downgrade intentionally fails closed.

## AC6 — Security and supply chain

Current tracked-baseline scan is triaged but final current files, Docker layers, runtime logs and resolved Python dependencies are not fully audited. Historical privileged exposure remains unresolved externally. Full threat model including AI tools/tenant roles needs explicit evidence. No absence-of-vulnerability claim.

## AC7 — Measurements

Build/test durations exist; they are not five-journey p50/p95/p99 or load measurements. Capture realistic baseline/after with bounded synthetic local traffic and query plans before optimizing.

## AC8 / AC9 — Operations and demo

Static health is not validated dependency readiness. Restore safety/immutable-release/CI/migration-owner concerns remain. Telegram transport stalls were observed read-only in production and not fixed. Prepare and rehearse a10–15minute synthetic demo with integration fallback and confidential-data exclusions.

## AC10 / AC11 — Reports and final verification

Working progress/system map/backlog/changelog/security contract exist. Reports00,03,04,05,07,08,09,10 are pending. Final whole-diff independent review and required aggregate reruns have not occurred. verdict.json UNKNOWN is intentional; only its scaffold AC1 is currently populated, so it must be replaced by the fresh final verifier, not treated as complete acceptance coverage.
