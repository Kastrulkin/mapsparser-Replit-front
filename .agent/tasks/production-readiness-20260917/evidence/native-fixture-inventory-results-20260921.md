# Frozen fixture inventory — 21 September

Parent `47ac36cf`; source `99849935` unchanged. This package is collect-only
metadata and audit-harness repair, not application test execution or a release.

## Actual attempts

| Attempt | Child result | Controller result | Child + postcheck duration |
| --- | --- | --- | ---: |
| v1 | 737 collected, one collection error | rejected: absent SQLAlchemy metadata URI | 5.416 s |
| v2 | 5,481 collected, exit 0 | rejected: full stat comparison included access time | 11.653 s |
| v3 | 5,481 collected, exit 0 | rejected: two ZIP timestamp-dependent parameter IDs | 12.186 s |
| v4 | 5,481 collected, exit 0 | accepted: exact record validation and owned cleanup | 11.987 s |

These durations do not include final temporary cleanup/serialization. Raw
failures remain preserved; v2/v3 exact helper snapshots and child records are
archived. Exact v1 helper bytes were not archived before editing: only its
recorded hashes and terminal evidence survive. Do not infer a reproducible v1
source snapshot from the current helper. v1 import failure was test-environment
configuration, not an application defect.

The fixed passwordless metadata URI points at denied loopback port 1; inherited
DATABASE_URL is rejected. The collector child denies sockets, subprocesses and
libpq connections, runs pytest collect-only and executes no test bodies. The
5,720 frozen blobs/modes and full source file inventory match before/after;
default guard remains `07d3...1150`. The v4 owned temporary result directory is
gone only after regular-file identity/hash and exact directory-entry checks.
Failure directories are retained, not recursively removed.

## TEST-FIXTURE-METADATA-01 — P2, audit harness, locally FIX_PROVEN

The original file-identity gate compared access time, which the read itself can
change. Effect: a correct metadata result was rejected, blocking whole-suite
admission planning. Fix: compare device/inode/mode/link-count/owner/group/size/
mtime/ctime and SHA-256, excluding atime only. Controls accept atime-only drift
and reject all other identity fields, symlinks, replacements and foreign entries.
v3 passed this gate, exposing an independent historical-ID mismatch. Confidence
high; local audit-only impact, small effort/blast radius; no product outage claim.

Two auto-generated pytest IDs contain bytes from freshly written DOCX/XLSX ZIP
fixtures, including DOS timestamps. v4 reconciles only those exact MIME-prefixed
nodes against the pinned test source. It verifies exact stored member names and
contents, masks only four DOS date/time fields at parsed local/central-header
offsets, and requires every other byte equal. All other 5,479 IDs/order remain
exact. Original and observed IDs plus the two mappings are retained; no test,
fixture, assertion, timestamp or result is changed. Controls reject payload,
path, MIME, CRC/header, central-directory, missing/duplicate and other-ID drift.
Risk is over-normalization; exact source/name/ZIP-byte gates and independent
review bound it. This does not make the original parametrization deterministic.

Final controls/Ruff/diff pass in 208.917 ms; prior v3 controls in 172.699 ms.
Independent pre-execution and actual v4 runtime/cleanup review PASS. Result:
5,481 unique records, 10,515 fixture definitions, including 2,322 frozen-source
definitions and exactly two declared timestamp mappings. Raw metadata secret
scan: 7,704,473 bytes, no findings, capture 12,025.549 ms.

The first staged scan rejected one generic-api-key finding: the manifest's
SHA-256 value for a filename containing `raw-secret-scan`, not a credential.
Redacted finding and failed capture are retained. The value is independently
recomputed from the evidence file; the artifact was renamed to
`metadata-integrity-scan.json` without changing its bytes. No suppression or
allowlist is used; final strict staged and expanded-archive scans are required.

## Admission planning, not additional passed tests

Read-only source/fixture reconciliation yields disjoint planning buckets:

| Lane | Nodes | Status |
| --- | ---: | --- |
| Shared conftest PostgreSQL | 104 | accepted by earlier exact runtime evidence |
| Direct OPERATOR_VOICE_TEST_DSN fixtures | 686 | 673 imported voice-pg + 13 content-rules-pg; not all executed |
| e2e directory | 10 | one actual Vite fixture, nine harness/error tests; not one homogeneous lane |
| Configured-service/provider probes | 7 | six ChatGPT API probes + one Yandex environment probe; no live authority |
| Other unclassified admission scope | 4,674 | includes previously accepted pure slices; not 4,674 failures |

No node has multiple `pg`/`postgres_container` definitions in this metadata.
The existing operator-service whole28 acceptance includes 21 direct-DSN nodes
and seven fixtureless nodes; never add 28 to the 686. Default no-I/O guard is a
global safety prerequisite, not proof that every residual test is unit-only.

Next coherent runtime target: entire 382-node `test_operator_voice_pg.py` via
the existing owned-bootstrap approach, after a literal profile, connection
budget and provider-double review. Remaining direct-DSN module counts:
business-input53, work-journal48, editorial27, finance-daily24, service-creation21,
followups16, workday-integration13, post-rewrite13, content-rules13, work-review11,
workday11, disk-import10, request-history9, architecture-boundaries9,
organika-journal7, plan-revision6, profile-input5, Google-Drive4,
storage-OAuth3, receipt-schema-lock1. These are planning counts, not CLI profiles.

Accepted runtime slices remain 2,811/5,481; collect-only adds zero passes.
Current-source aggregate, image-layer security, browser, frontend flake,
performance, CI/demo/final gates remain open. Production/providers unchanged;
no push/deploy. All 13 foreign paths and historical whole-goal FAIL preserved.

Compressed metadata is lossless; its expanded SHA-256 is
`e49b7a637b77af2c437d7fc2a7f9190c81f81c82da2d1a22fbcab13ed1dedb52`.
`native-fixture-inventory-hflypi-20260921/manifest.json` binds artifacts/support
and expanded gzip identities. Keep existing attempts immutable.
