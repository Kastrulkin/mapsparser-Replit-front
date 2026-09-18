# Synthetic real-API CI slice

The scheduled workflow
[`staging-real-api-nightly.yml`](../../.github/workflows/staging-real-api-nightly.yml)
is separate from unit and mocked browser gates. It starts a disposable,
GitHub-hosted Docker Compose project with the existing staging override,
existing isolation preflight, and deterministic synthetic seeder.

It runs the existing tenant-negative, owner review/finance, and social receipt
reconciliation journeys through the actual app, PostgreSQL, browser and guarded
fixture CLI. Provider credentials are blanked by the staging profile; workers,
bot, dispatchers, and real providers are not started for this slice.

The launcher accepts only a numeric GitHub run ID and attempt, creates an
exactly named project, refuses pre-existing same-name resources, derives the
fixture container from that project only, and performs only label-scoped Compose
cleanup. It does not run on a local machine, target a supplied host URL, accept
a native fixture DSN, or perform a broad Docker prune.

Artifacts contain bounded synthetic metadata plus Playwright reports, traces,
and failure screenshots. They intentionally exclude rendered Compose config,
environment dumps, raw logs, and database dumps. A workflow definition and its
static tests are not evidence that GitHub image build, migration, seeded
journeys, or cleanup have succeeded; that evidence requires an actual run.
