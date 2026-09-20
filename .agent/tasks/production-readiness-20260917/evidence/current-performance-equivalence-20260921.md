# AC7 current-performance equivalence assessment — 21 September 2026

## Scope and conclusion

Read-only source/evidence assessment at current `HEAD 334c9d4bf69cc9e96fd13a39d9eba8ff32c9f3d6`.
No application, test, network, database, or load command was run for this
assessment.

The accepted paired working-reference measurement remains valid for its stated
source interval only: `2d875357ae5dd0e8206c0665fd0919e92d1e3c3b` to
`272794a439a76204536480f158e79276ccd7b318`.  It completed five warmups and
50 interleaved ABBA serial samples per reference, with 750 measured requests
and 150 invariants passing per reference.  Its independent recomputation is
recorded in `docs/production-readiness/04-performance-report.md`, lines 13–48,
and the underlying result is
`raw/journey-measure-v8-2d875357-272794a4.json`.

That evidence does not establish latency or load behavior at current HEAD.
AC7 therefore remains **FAIL / incomplete**, and overall readiness remains
**FAIL**.  This conclusion neither adds a production-capacity requirement nor
claims that a bottleneck was measured.

## Exact measured scope

`scripts/readiness_journey_benchmark.py`, lines 305–515, defines the fifteen
timed requests and three untimed invariants.  Its five journey sequences are
also listed in `docs/production-readiness/04-performance-report.md`, lines
185–210:

1. Authentication and tenant: login, current user, business data.
2. Service menu: compression draft, review, apply, replay.
3. Finance import: preview, apply.
4. Content: plan, draft, internal news.
5. Operator: refocus proposal, confirmation, replay.

## `272794a4..334c9d4b` equivalence review

Direct source-path review found no changed direct handler/service path for the
first four non-content sequences: authentication and tenant, service menu,
finance import, and the benchmark's operator refocus proposal/confirmation
sequence.  This is a source-only equivalence conclusion for those four paths,
not a new timing result.

The `src/core/action_orchestrator.py` callback recovery change is not a direct
benchmark workload: the benchmark does not seed a callback URL or invoke
callback outbox dispatch.  `services/operator_core.py` imports the
orchestrator, but that import alone is not evidence that callback dispatch was
included in the refocus fixture.

The content sequence is not equivalent.  The benchmark calls
`POST /api/content-plans/generate` at
`scripts/readiness_journey_benchmark.py:370`; the route delegates to
`create_generated_content_plan` in `src/api/content_plans_api.py:237-257`.
After `272794a4`, `src/services/content_plan_service.py` added root/target
scope resolution and write-access authorization before its call to
`load_plan_context_for_business` (`1850-1900`).  The latter performs its own
user/root/scope authorization and context resolution (`1364-1475`).  These
extra checks change the current timed content-plan request work.  They do not,
by static inspection, prove a latency regression or a material bottleneck.

The timed content draft route is likewise covered by the benchmark at
`scripts/readiness_journey_benchmark.py:496-513` and maps through
`src/api/content_plans_api.py:332-366` to
`generate_draft_for_plan_item`.  The later website-description hardening uses
the pinned, bounded redirect implementation in
`src/services/content_plan_service.py:2834-2872`, invoked while assembling
business facts at `3969-3980`.  The benchmark seed inserts no `site` or
`website` field (`scripts/readiness_journey_benchmark.py:164-201`), so this
website branch is empty in the old fixture.  The accepted comparison thus does
not cover website-fetch behavior; it must not be represented as doing so.

Frontend changes to `JourneyActionCard` and `JourneyWorkspaceFocus` are not
one of these fifteen Flask-dispatch API requests.  The historical browser
observation in the report covers login and finance import, rather than those
Journey UI changes, so it does not extend that evidence to them.

## Concrete remaining measurement

When the authorized native-PostgreSQL lane is available, run the reviewed,
guard-first clean-archive measurement method with identical fixture and
provider seams for `272794a4` versus `334c9d4b`.  At minimum it must collect a
paired ABBA distribution for the changed content sequence (`plan`, `draft`,
`internal news`), retain exact source/harness/guard hashes, raw and command
captures, database-cleanup evidence, and independent quantile/count review.

The website path needs one explicit choice in that lane:

- retain the present empty-site fixture and state the website-fetch path is
  excluded; or
- add a deterministic, no-egress local/pinned website seam covering bounded
  redirect behavior.

No such run was authorized or performed here.  Existing results report mixed
tails and no general speedup (`04-performance-report.md:41-46`); they cannot
be reused as current-HEAD latency evidence for the changed content path.
