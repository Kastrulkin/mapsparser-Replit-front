# Problems: p0-p1-runtime-hardening-20260518

No verifier findings for the requested P0/P1 pass.

Known non-blocking gaps:
- Local Docker daemon is unavailable, so local runtime smoke stops at `docker compose ps`.
- Live Yandex external account smoke requires `YANDEX_TEST_BUSINESS_ID` and was skipped by design.
- Legacy report routes still use SQLite placeholders through `safe_db_utils`; this is intentionally outside the PostgreSQL runtime cleanup.
