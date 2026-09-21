# SEC-LEGACY-LEAF-LOG-02 — remaining leaf parser console values

Parent `c587b20f5f28187c1fed04323e6f6b118982282c`. P1 before production,
high confidence. Supported legacy mode/interception-import fallback reaches
overview, review, news, feature, product and competitor extraction helpers.
Their console prints previously included business fields, contact links,
review/reply text and raw exception details. Log exposure depends on parser
execution and log access; no actual live compromise was tested or claimed.

## Local correction and acceptance

Thirty-nine print expressions now emit fixed phase/failure events (some retain
source-fixed selector names). Only unused exception bindings and one obsolete
comment change otherwise. Function results, parsing actions, fallback/return/
raise flow and existing raw invalid-input exception contract remain unchanged.
Small patch, low functional blast radius; intentional loss of forensic detail.

The new three-method suite `tests/test_legacy_parser_leaf_diagnostics.py`:

1. Uses function + paired parent/final message fragments for every changed
   sink; executes all39 with synthetic values, requires no marker and nonempty
   fixed events. This is print-expression execution, not39 full scraper flows.
2. Executes the whole extracted overview helper with an inert page and checks
   title/address/phone/social result values are retained while stdout omits them.
3. Executes the whole extracted main-page review helper with a failing page;
   empty default result is retained and exception text is not printed.

Neither scraper nor Playwright/worker top-level is imported. Audit hooks deny
sockets/process spawning/SQLite; the final combined harness installs the guard
before collection, clears the environment and disables conftest/plugin autoload.

## Evidence, review-discovered gap and scope

The first uncommitted harness used line numbers and omitted the phone exception
sink: it covered38, not39. Root review caught the omission and requested stable
semantic anchors, nonempty events and the full overview fake-page check. A WIP
mapping test that would skip without parent input was removed before freeze;
no skipped tests were used for acceptance. Earlier implementer probes were not
persisted or used as final acceptance. No capture overwrite/source reversal.

Authoritative root baseline `legacy-leaf-causal-baseline-20260921.json` runs
final test bytes against the immutable parent in memory:3privacy failures,
0errors,399.426ms. Parent SHA256
`d26de3a46789974422455418e354904362672a1d99c98946ddac6cc04786bfa1`;
fixed source `1b5312a8fb74b0a079eb2cbec69a659b1f19abd93d78075f82a8a18c678d7d50`;
final test `86d6651a6e9c4deeeb38a3307fb63a0f40a8c46194a6aba5a422ad88e1dd5a70`.
The baseline Git temp-directory warning is retained, not an application failure.

`parser-privacy-final-20260921.json`:86passed +4subtests,10.61s/10996.407ms,
no stderr/timeout/truncation. Scope:3new legacy,14new Apify,20existing service
and49prior parser/worker units. `parser-privacy-quality-20260921.json`:
269.823ms,20source hashes, new-test Ruff and legacy/service F821 checks; exact
one-to-one39 changed-print AST pairs and entire legacy AST equality after
normalizing print expressions and exception-binding names. Not a general
semantic equivalence proof of external helpers or a full backend integration.

Independent static/source/capture review found no actionable regression and
confirmed all retained interpolation is fixed selector/browser names or numeric
count/config/loop metadata. Such metadata remains intentionally observable.
Raw invalid-input/returned errors, other worker/service logs, old retained
artifacts and deployed code remain separate boundaries. No global no-PII or
credential-lifecycle clearance. Original AC/whole FAIL unchanged; no production,
DB/provider, Docker, cleanup, push or deployment action.
