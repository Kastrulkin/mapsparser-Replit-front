# Services/content role proof — current a387 source

## Scoped verdict: PASS

55 exact tests /165 unique setup-call-teardown reports pass, with no skip,
failure, xfail, warning or collection error. Outer command19.615268s/exit0,
controller18.273419s; actual pytest child7.495288s. Independent final runtime
review recomputed accounting, provenance, schema and cleanup and accepted PASS.
This is not a full backend/production-readiness pass and does not rewrite the
offline aggregate's4,391pass/12fail/1,119skip accounting.

## What was exercised

Unmodified `tests/test_services_content_viewer_readiness.py` SHA0ebeb619 runs
against cloned tables from the real migrated schema. It checks stored write
roles for service creation/enrichment/update/compression/apply/rollback and
content item updates/generation; viewer/network-viewer/revoked/foreign denials;
authorized writer controls; resolved target authorization; mobile denial/error
mapping and context-scope boundaries. Assertions include persisted state, not
only status codes. Session-token decoding and unrelated provider/context inputs
are test doubles. This is not real Google/AI/provider or complete session proof.

Source is the unchanged accepted commit `a38720ce3530783caf59f6515a00baa1c532ce01`
archive; preceding evidence-only commit654d09c7 changes no runtime/test source.
Before and after manifests contain the exact6,469 accepted path/content/mode/size
records. Current collection artifact312fed27 supplies precisely55 selectors;
the full node/freeze artifacts are already in `../current-backend-a38720ce-20260922/`.
No dirty/untracked workspace overlay or restricted OAuth file was imported.

## Real prerequisites and cleanup

Fresh native PostgreSQL15.15 listens only on `::1:35418`; Python3.11.7 runs
ARM64 and PostgreSQL is the installed native x86_64 build. The generated
`readiness_full_test_<8hex>_<12hex>` database has synthetic fixtures only.
Actual guarded Flask CLI upgrade and current checks pass,4.292001s and2.566976s.
Database Alembic revision equals the sole repository head `20260907_001`.
All12 required public tables exist; `pgcrypto1.3` and `vector0.8.6` are both
available and installed. Schema compatibility here is PG15, not a fresh PG16
production-image claim or a new restore/rollback rehearsal.

Seven runtime controls reject foreign database/port/libpq overrides, inherited
PG environment, native off-port connections, guard writes and user-home reads.
The OS policy permits only IPv6 loopback35418 and owned temporary writes;
source and guard/context writes stay prohibited. Policy/hash and copied guard
origins/content are checked. Start5GiB/live2GiB floors,300s controller allocation,
bounded children and4MiB per-stream caps remain. All captures are untruncated,
have no drain errors and retain digests rather than arbitrary application logs.

No viewer schemas remain. Generated DB absence is verified and the final catalog
contains only postgres/template0/template1. Postmaster52990 stops; children53016,
53024 and53028 all exit with clean birth-pinned registries, no forced signals or
remaining processes. An independent root `ps` check found those exact PIDs
absent. Read-only `lsof` confirms the original Docker process36729 still owns
127.0.0.1:35418. Neither its database nor its containers were changed.
Stopped private run roots are retained as evidence; system-cluster files remain.

## Failed preparations retained honestly

1. v1/runner06a0fb00:1.396014s/exit1. The IPv4 port was occupied, before mkdtemp,
   PostgreSQL or DB creation. This is not a failed application test.
2. The existing fixture explicitly admits `::1` on the same35418 port. A private
   lifecycle copy changes only source-root binding, listen address, bracketed
   DSN and identity check. No test admission/assertion is relaxed. `remote ip6
   localhost:35418` compiles; a separate actual OS probe rejects the occupied
   IPv4 endpoint with EPERM in33.154ms. No network restriction was relaxed.
3. v2/runner3084733c:7.005995s/exit1. Flask reports NoSuchCommand before migrations
   or tests because the launcher omitted the application's src import path.
   Its generated DB is removed and owned postmaster52718/child52754 are stopped.
4. v3 adds only the canonical source paths and explicit guarded src.main import
   before the same Flask CLI. It passes without any product/test source change.

Final26 pure preflight checks pass1.389872s; they include failed process-tracker
construction, stream-reader failure and timed-out graceful postmaster stop on
fakes only. Final controller Ruff89.804ms and preceding four-file Ruff150.239ms
pass (exact timings in command JSONs are authoritative). Independent pre-execution
review accepted each executed profile; v1/v2 are not discarded or called passes.

## Provenance and next action

Private controller `/private/tmp/localos-services55-g839Mw/`, accepted v3 runtime
`/private/tmp/localos-services55-pg.i5c9as8l/`. Final runnerafc8d1af, guard9aff5c84,
private lifecycle78ce5ebf, unchanged owned-process helper4f16b6c3 and policy4143f002
are pinned. The private lifecycle file retains historical unused functions; the
accepted controller does not call its old main/stop/group-kill paths. It uses
its own reviewed direct/birth-owned cleanup. Never run the archived helpers as
generic launchers or restart completed `audit-services55-pg-v1/v2/v3` handles.

`SHA256SUMS` binds20 raw/source artifacts, including the preceding aggregate
scan and commit captures. No raw result was normalized. Next: scoped secret
scan/local evidence commit, remaining current integration/security/image206,
five-journey bounded stress/resources, CI/demo and independent final whole-diff
review. All original DoD requirements remain in force; no push/deploy authorized.
