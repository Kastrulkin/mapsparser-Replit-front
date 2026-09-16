# Organika Operator repair — 16 September 2026

Baseline: 53/100 passed, 44 failed, 3 errors. Candidate v4: 100/100 passed. Candidate v6: 48/48 alternative formulations passed (16 cases × three formulations). Tests use real provider computation with rollback of business mutations; independent confirmation artifacts are explicitly rejected with audit retained. Backend channel labels are not evidence of Telegram delivery or physical device testing.

Repairs cover selected-post edits/translations, explicit scheduling, financial number/currency parsing, read permissions, observations and review, request idempotency, and truthful failures/billing release. Monthly aggregate input is refused rather than misrecorded on a single day. Unsupported compound recommendation rules ask a specific clarification instead of silently applying only part.

Case 19 contract was corrected from clarification to the requested two posts/week: 1, 4, 8, 11 December; dates are asserted. Content planning fixtures cover allocation plus batched generation, with replay remaining idempotent.

Local checks: broad backend suite 662 passed, one transient M4A decoder failure; the three decoder formats passed all three repeats (9 tests), and production M4A normalization passed. Frontend regression tests: 13 passed. Final independent review: 79 focused unit and 23 PostgreSQL tests passed. PostgreSQL checks used an isolated native PostgreSQL 15 database after the local Docker runtime stopped.

Remaining acceptance gates: live release/HTTP/UI verification; Telegram transport recovery; actual iOS/Android voice demonstration. Organika has no appointment/master/approved upsell matrix data: tests must not invent it. Manager review requires an explicit owner permission grant; no grant was made by this repair.

Production source contains unrelated workday changes; deployment applies a checked patch to the current source and preserves those changes. No schema migration is required.
