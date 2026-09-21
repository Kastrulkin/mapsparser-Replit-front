# Shared PostgreSQL fixture reconciliation — 21 September 2026

Frozen source `99849935de26e2932613f2a73cf515dff49104a1`, not current source.
The historical `tests/conftest.py::postgres_container` inventory is now
reconciled: 104/104 dependency nodes accepted, 0 pending, across 19 modules.
This package adds exactly the final 17 nodes in 13 serial, isolated profiles.
It does not assert a full PostgreSQL suite or a current-source aggregate.

| Profile | Nodes passed | Captured child / wrapper seconds | Relay connections | Child DSN admissions |
| --- | ---: | ---: | ---: | --- |
| author-daily-gate-pg-v1 | 2 | 7.501 / 11.063 | 3 | 1 |
| knowledge-schema-pg-v1 | 1 | 7.220 / 10.604 | 2 | 1 |
| outreach-pain-library-pg-v1 | 2 | 6.918 / 8.685 | 4 | 1 |
| riderra-template-pg-v1 | 3 | 3.648 / 5.314 | 3 | 0 |
| sales-room-proposal-race-pg-v1 | 1 | 7.581 / 9.289 | 5 | 1 |
| sales-room-deadlock-pg-v1 | 1 | 7.912 / 10.352 | 4 | 1 |
| telegram-shared-audience-pg-v1 | 1 | 6.827 / 9.766 | 2 | 1 |
| web-tracking-pg-v1 | 1 | 14.028 / 16.368 | 5 | 4 |
| worker-captcha-pg-v1 | 1 | 7.583 / 9.323 | 7 | 1 |
| worker-expired-pg-v1 | 1 | 8.557 / 10.933 | 5 | 1 |
| worker-resume-pg-v1 | 1 | 8.356 / 10.712 | 9 | 1 |
| finance-import-transaction-pg-v1 | 1 | 2.760 / 4.508 | 4 | 0 |
| service-compression-race-pg-v1 | 1 | 7.225 / 8.997 | 8 | 1 |

All 17 collected nodes passed with zero skips/errors. Each capture reports one
upstream `testcontainers.postgres` deprecation warning and empty test stderr.
Finance and service-compression admitted `postgres` only for their fixture
admin connections plus one exact generated disposable database each; their
parent-admin and cleanup evidence is in the copied raw journals. The
compression migration child admitted the generated database.

The guarded lifecycle preserved 5,720 frozen blobs before and after every
profile, restored the default guard, removed only the owned tmpfs container,
and left the retained baseline at 23 containers, 4 images, 20 volumes and 23
networks. The internal network was empty after cleanup. No product,
production database, provider, or external write was performed.

`shared17-fixture-controls-v2.json` is the accepted static-control capture.
`shared17-fixture-controls-v1.json` is preserved as raw history; its collector
source is not archived by this package. `SHA256SUMS` binds the 65 profile raw
captures, both control captures, and the five reviewed support-file hashes.

The collection-level reconciliation becomes 2,811/5,481 accepted slices and
2,670 unclosed. This is accounting for the frozen collection only, not a
current-source pass, performance claim, or full-PG completion claim.
