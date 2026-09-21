# PostgreSQL capabilities and governed operations — 21 September

Parent71f966ad; unchanged frozen application99849935. Previous goal turn made
verified progress (approved cleanup08d39906 and agent/social71f966ad), not a
wait or restart. No application/fixture/assertion/schema source changes here.
All production, existing databases/volumes, providers, push and deploy excluded.

## Real PostgreSQL API57

Literal57nodeids exactly match the function-scoped capabilities_client users
in tests/test_capabilities_api_phase1.py; three adjacent pure nodes are outside
this profile. Fresh owned internal-only PostgreSQL/tmpfs, original migration
child and per-test synthetic schemas; unchanged Flask test-client assertions.
Auth identities/providers are test doubles, so this is not real-session or
provider certification. Covers tenant scope, approvals, idempotency, billing,
callback retry/DLQ, audit exports and channel routing in the tested contracts.

All57pass, no skips/xfails/errors, pytest43.92s/capture44.774s/wrapper48.118s.
One retained warning: testcontainers.postgres import is deprecated in favour
of testcontainers.community.postgres; no dependency/assertion changes made.

Required harness capacity was identified before runtime: each of57fixtures
opens three connections, so the old32lifetime limit cannot fit even171setup
connections. This is a newly required test profile, not a product defect or
an observed application outage. Only the named capabilities profile receives
1024total; default/oldprofiles remain32,8concurrent/600slifetime/120sconnection
limits unchanged. Unknown profiles deny. Same reviewed owned relay/DSN and
parent DATABASE_URL lifecycle; all endpoint/identity/policy checks retained.

Actual326relay connections, all326execs exit0/graceful/empty stderr,0active/
rejects/failures. Ten IO-denial probes, real guarded child, eight capability
denials and parent+Flask-child DSN evidence pass. Parent DB value bound/unbound
once. Owned container55ef640eab34889a26a1e389a13a0b3b98d027a9682cfb43db75ec833740b1d9
removed; its synthetic data discarded. Network/capability directory empty,
23pre-existing container identities/running states unchanged. Default guard
07d3... restored, temporary adapter/relay copies removed,5720frozen blobs match.
Independent pre-execution and runtime acceptance reviews PASS; raw runtime
gates pass. Independent live inspection also found the same23containers and
empty approved internal network, with the exact default guard restored.

## Pure/mock inventory correction, not a hidden skip

First governed profile:856collected,835passed,21skipped,0failures in7.60s
(wrapper10.280s). Although pytest exits0, the existing no-skip acceptance
correctly rejects it. Preserve v1raw; it is not an856PASS result.

The21skips are localized to tests/test_operator_service_creation.py:
its imported pg fixture (tests/test_operator_voice_pg.py:15–18) requires
OPERATOR_VOICE_TEST_DSN. creation(pg,...) produces21DB-backed parametrized
nodes; seven adjacent pure nodes passed. Static console/module ordering and
fixture definitions explain the raw count; this run did not capture per-skip
reason records. This is missing real-PG test configuration, NO_BUG_PROVEN for
the product; the metadata-only Flask URI must not be used for this fixture.

Version2classifies37modules/828nodes as pure/mock, retaining the same fixed
passwordless denied-port metadata URI and inherited-DSN rejection. Full mixed
operator28is still required, not waived/removed from the audit. v2passes828/
828,0skip/fail/xfail/subtest, exit0/stderr0; pytest7.80s/capture8.577s/wrapper
10.662s. Exact37module counts and unique nodes verified; default guard and
5720frozen blobs unchanged. Independent pre-exec/runtime review PASS.

Final pure controls (three TC profiles, four pure profiles, actual subtest
reports), Ruff7files and diff check pass, exit0/stderr0/389.990ms. Earlier
399.592ms preflight is retained separately. Raw captures and16hashes are in
native-capabilities-governed-hflypi-20260921/manifest.json, including v1.

## Coverage and remaining work

Accepted complete-slice count:1097prior+57PG+828pure =1982of5481in58module
slices;3499not yet closed by complete accepted slices. Do not count v1's
seven partial operator passes again. This is not a full aggregate, proof of
later changed source, deployment, or production readiness. The previously
mapped shared-Testcontainers group has28remaining; the newly identified
mixed operator28is a DIFFERENT set outside that group. Neither is optional.

Next: entire operator-service module with one new owned-TC bootstrap before
pytest because it never requests postgres_container. Bind only initially
absent OPERATOR_VOICE_TEST_DSN after capability validation; no parent
DATABASE_URL and no Flask-child requirement for this profile. Its21pg fixtures
create/drop unique voice_<uuid> schemas and apply the documented voice/service
migrations; keep32connection budget and require actual21..32clean connections.
Unbind exact env value, remove only owned tmpfs container, keep original guard
and resources. This is a reviewed plan, not implemented/run evidence.

Frontend default-full flake, remaining backend/PG aggregate, security/privacy,
browser/CAPTCHA, five-scenario performance, hosted CI and final audit remain.
Historical whole-goal FAIL/spec/problems untouched;13foreign paths preserved.
