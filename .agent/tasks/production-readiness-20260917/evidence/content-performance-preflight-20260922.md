# Current content-performance refresh — preflight

Code checkpoint: `dc1a6b76`, branch `codex/production-readiness-20260917`.
This is source/runtime preparation, **not a completed benchmark**.

## Measured workload and reason for refresh

The accepted historical working-reference pair ends at `272794a4`.
`scripts/readiness_journey_benchmark.py` times these content steps:

1. `POST /api/content-plans/generate` (plan).
2. `POST /api/content-plans/items/{id}/generate-draft` (draft).
3. `POST /api/content-plans/items/{id}/create-news` (internal news).

The current plan path includes additional scope/write checks introduced after
that checkpoint. This is a reason to measure, not evidence of a regression.
The fixture has no business site/website and no content rules; text generation
is deterministic. Internal news is a database write, not external publication.
Website fetching, provider latency, browser latency and production capacity are
excluded. The unchanged full benchmark also executes12 other timed requests
and3 untimed invariants; do not describe it as a content-only runtime.

## Runtime discovery

The historical v8 wrapper, guard and native cluster directory are absent.
Installed native PostgreSQL15.15 binaries are available via `/usr/local/bin`
links into `/usr/local/Cellar/postgresql@15/15.15_1/bin`. Native Python3.11.7 is
available in the retained hfLYPi test environment. Existing Testcontainers
profiles are not measurement profiles and must not be re-used by relaxing their
allowlist. No existing database connection was made during this discovery.

## Acceptance before accepting new timing evidence

- Independently reviewed fresh private-cluster lifecycle; no existing DB or
  Docker resources; exact spawned process and data-directory identity.
- Sanitized environment, guard-first source hash and OS denial of all network
  destinations except the one owned loopback PostgreSQL listener.
- First pilot0warmups/1serial sample per ref. Only then full5warmups/50serial
  samples per ref, ABBA, load0, aggregate deadline and disk limits.
- Resolved baseline `272794a439a76204536480f158e79276ccd7b318` and current
  `dc1a6b76`, clean git archives, identical current harness, archive import origins.
- Successful request semantics and all invariants, raw values retained, no
  failed/omitted requests silently excluded from correctness counts.
- Independent recomputation of plan/draft/internal-news distributions **and the
  per-run sum**, with p99 explicitly exploratory at50 successful samples.
- Every planned generated database verified absent afterward. Driver's existing
  cleanup result alone is insufficient because it does not query post-drop absence.
- Only the newly owned PostgreSQL process stopped; artifacts preserved.

Outcome: pilot and full paired series completed. See
[accepted results](content-performance-results-20260922.md) for110validruns,
independent reviews, raw distributions, setup failures and cleanup evidence.
This document preserves the original preflight requirements, not current pending work.

The secondary OAuth related-refresh test is separately platform-restricted and
remains unrun/uncommitted. It is not part of this procedure. Production, external
providers, pushes/deployments and additional Docker cleanup are out of scope.
