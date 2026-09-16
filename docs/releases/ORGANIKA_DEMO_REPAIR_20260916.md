# Organika Operator repair — 16 September 2026

Baseline: 53/100 passed, 44 failed, 3 errors. Candidate v4: 100/100 passed. Candidate v6: 48/48 alternative formulations passed (16 cases × three formulations). Tests use real provider computation with rollback of business mutations; independent confirmation artifacts are explicitly rejected with audit retained. Backend channel labels are not evidence of Telegram delivery or physical device testing.

Repairs cover selected-post edits/translations, explicit scheduling, financial number/currency parsing, read permissions, observations and review, request idempotency, and truthful failures/billing release. Monthly aggregate input is refused rather than misrecorded on a single day. Unsupported compound recommendation rules ask a specific clarification instead of silently applying only part.

Case 19 contract was corrected from clarification to the requested two posts/week: 1, 4, 8, 11 December; dates are asserted. Content planning fixtures cover allocation plus batched generation, with replay remaining idempotent.

Local checks: broad backend suite 662 passed, one transient M4A decoder failure; the three decoder formats passed all three repeats (9 tests), and production M4A normalization passed. Frontend regression tests: 13 passed. Final independent review: 79 focused unit and 23 PostgreSQL tests passed. PostgreSQL checks used an isolated native PostgreSQL 15 database after the local Docker runtime stopped.

Remaining acceptance gates: live release/HTTP/UI verification; Telegram transport recovery; actual iOS/Android voice demonstration. Organika has no appointment/master/approved upsell matrix data: tests must not invent it. Manager review requires an explicit owner permission grant; no grant was made by this repair.

Production source contains unrelated workday changes; deployment applies a checked patch to the current source and preserves those changes. No schema migration is required.

## Production follow-up

Enabling request auditing exposed two additional settings-gate errors: STT ruble abbreviation `р` was understood by finance but not by setup; `допродаж` was mistaken for a financial write. Commit `60947280` reuses currency recognition and adds word boundaries. Its exact deployed 100-case run passed 100/100.

Commit `dac32211` additionally keeps addressed receipt/refund observations and explanatory questions out of business settings. The final focused PostgreSQL/unit batch passed 100/100. The exact final production rerun includes the original 100 plus five adjacent cases.

Partial deployment preserves unrelated live workday code. Organika was added to the review and request-audit allowlists, without granting manager rights. Backups: `release-backup-1789586146.tar.gz`, plus each settings-module pre-patch copy. App and operator-worker respond normally; public and local HTTP checks returned 200.

Live HTTP: web and Mini App upload → worker → SpeechKit → chat → audit → duplicate suppression passed. The real UI saved a marked wish, displayed it in the review inbox, cancelled it, and displayed both historical versions. A non-superadmin owner could review, create one linked task and suppress its duplicate; employee access and comment hiding were verified, with the transaction rolled back.

Telegram remains unavailable: both approved HTTP and SOCKS proxy endpoints timed out; public and private SSH paths to OpenClaw time out before authentication. Access to the hosting console is needed to restore the proxy host. No unauthorized alternative proxy was introduced. Device and Telegram delivery checks remain incomplete.

Final deployed `dac32211`: **105/105 PASS** (original 100 and five advice/observation regressions). Additional live HTTP financial voice test: 10 checks, 2 upsell checks, RUB revenue350/refund20 parsed exactly; replay suppressed; approval rejected via canonical API; no financial record applied.
