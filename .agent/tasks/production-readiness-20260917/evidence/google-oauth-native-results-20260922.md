# Google OAuth current-access native results — 22 September 2026

## Scope and result

**GOOGLE-OAUTH-STALE-ACCESS-02 is locally FIX_PROVEN for the native callback
fence.** The actual Flask Google Business and Google Sheets callback routes passed
**24/24** against a fresh, Alembic-migrated, disposable PostgreSQL database.
Provider exchange and encryption were fake; authorization queries, transactions,
locks, persistence and rollback were real PostgreSQL behavior. No live Google
provider call, production DB write, deployment, push or image build is claimed.

| V3 measure | Result |
| --- | --- |
| wrapper / child / pytest | 26.959s / 23.511s / 16.44s |
| nodes | 24 passed; 0 fail, skip, xfail or setup failure |
| matrix | 6 pre-exchange revocations; 6 mid-exchange revocations; 8 owner/admin insert/update controls; 2 lock fences; 2 deferred rollback cases |
| relay | 175 graceful connections, within 512 cap; no rejection/failure |
| cleanup | schema 0, generated DB 0, owned container removed |
| preserved state | 23 unrelated container IDs/states and 5,720 frozen blobs unchanged |

The test proves that a signed state does not preserve stale access: owner, admin or
active-account revocation prevents callback credential persistence in LocalOS; the second
admission acquires actual `FOR SHARE` locks only during persistence; and a deferred
database failure restores prior credentials and Sheets auth references.

## Provenance

Parent `debd6006`. Execution used the frozen `99849935` archive plus exactly the
new primary test overlay. The actual API module, DatabaseManager, pg_db_utils and
guarded fixture helper are byte-identical to the current committed sources; their
four hashes are checked before execution and stored in the raw result. This is
not execution of the whole current dirty worktree. No application source changed.

- Final test SHA: `84957e16d6c644e8ad04928452841f5d4547c2efeb682959a64a7aa052e0c193`.
- Final launcher SHA: `f63c680106e632872f1fb87f412449c3030424fe5fd64c738d4f38066a3cc4c1`.
- Final adapter SHA: `859b535fa6637b01fb73f99d7f43474662e3b9ebd2c6ebc4849cdc8a26f2069c`.
- Guard and relay were unchanged from the accepted callback profile.
- Raw attempts and event journal:
  `/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence/native-tc-google-oauth-current-access-pg-v{1,2,3}.json` and matching `*-events.jsonl`.
- Durable copies: [evidence manifest](google-oauth-native-20260922/SHA256SUMS),
  containing 13 raw attempt/probe/relay/journal files and the preceding callback
  commit/strict staged-scan captures. The 15 hashes all verify.
- Independent source, pre-execution and terminal reviews: bounded PASS.

## Preserved non-passes

- **V1 — NOTPASS:** 5.127s, stopped before tests because a reused callback mode
  rejected the OAuth journal prefix. This is a harness-alias prerequisite failure,
  not a product result.
- **V2 — NOTPASS:** 12.276s, collection/import prerequisite failure. It is retained
  as raw evidence and is not counted as a product failure or a pass.

## Boundary and next candidate

This is not live-provider, stock-image, deployment, performance, security-image or
whole-readiness certification. The overall audit remains ACTIVE/FAIL.

`tests/test_google_oauth_related_refresh_pg.py` (SHA `ee2cf09…`) is a separate,
reviewed candidate for a secondary Google Business related-account refresh race.
It is **NOT_REPRODUCED**: not run, not committed and not a confirmed finding.
