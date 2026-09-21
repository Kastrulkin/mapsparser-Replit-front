# SEC-DEBUG-BUNDLE-01 — new parser debug-file persistence

Category: confidentiality. Priority: P1 before production, conditional on the
explicit debug opt-in (default false). Confidence: high for the reproduced
response writer; remaining file sinks have source/helper proof, not a complete
browser run. Impact: private provider/session values may become durable local
files. Likelihood is conditional on operator enablement; blast radius includes
the shared diagnostic storage and anyone receiving a bundle.

## Cause, correction and tradeoff

The response callback wrote arbitrary JSON with `json.dump`, while related
debug paths wrote raw HTML, payloads, URLs and screenshots. Provider material
can occur under unknown field names and inside scripts/forms/URL components;
a short list of redaction names would not establish this boundary.

The three-file correction adds a stdlib-only helper for bounded, value-free
schemas, fixed URL categories/flags and HTML placeholders. All current parser
debug file sinks use these representations; response filenames are independent
of URLs and screenshots are not taken for bundles. The helper keeps at most
120 nodes, depth five and three list samples. No arbitrary input keys or scalar
values are retained. Length/count metadata still reveals coarse structure.

The parser's in-memory provider payload and final result remain unchanged.
Tradeoff: bundles cannot replay raw pages or responses. Canonical filenames
remain, but URL files now contain JSON metadata. The only located support
consumer prints page.html and remains usable with the placeholder; it must not
be used to disclose old raw bundles. No data migration or cleanup was performed.

## Verification

All captures are complete, with no timeout/truncation:

- RED: exact nested response callback compiled from the then-current parser
  AST; one failure actually finds the synthetic marker in the produced JSON,
  one disabled-writer control passes; 142.814 ms. Original raw-payload identity
  in parser state was checked before the failing assertion.
- GREEN: five callback/helper/static checks pass, 91.599 ms. This original
  green precedes additional assertions for wide cycles, unsupported values,
  malformed URLs and absence of screenshot calls.
- Adjacent: twelve existing parser units pass, 868.012 ms; actual parser and
  browser-session module imports, with socket/process/SQLite use denied.
- Final: all seventeen cases pass in 0.23 s / capture 539.002 ms, including the
  expanded assertions; seven exact source hashes recorded.
- Quality: 2,938.348 ms; full configured Ruff for new helper/test, F821/F822/F823
  for the parser slice, Node syntax for historical triage support, diff check,
  and seven-source hash reconciliation pass. A nonfatal Darwin temp-directory
  warning from Git remains visible in its child result.

The test runner does not load repository pytest conftest or third-party plugins.
No database, real browser, provider or production request occurred. Only fresh
synthetic test directories were created and automatically cleaned by the tests;
existing user files and stored debug bundles were not removed.

Independent review: `parser-debug-bundle-review-20260921.md`.
Result: FIX_PROVEN for the reproduced response-file persistence boundary with
bounded helper/static/adjacent evidence; not a universal confidentiality claim.

The precommit capture passes in 10,806.085 ms: 29 owned files / 613,462 staged
bytes; strict scan clean, seven captures and source hashes reconciled, 572
historical field bindings reproduced, immutable statuses/verdict and nine foreign
paths preserved. Final 30-file package includes that capture and receives the
same verification again before the local commit.

## Remaining risks

The response regression executes an exact AST-extracted callback, not the full
navigation/environment-flag flow. Static sink assertions do not replace a full
browser lifetime. Fresh image import/packaging, current runtime configuration,
old files, filesystem permissions and retention are unverified. Existing raw
URL/title/address/exception stdout diagnostics are a separate next finding to
reproduce and fix. No deploy, production change, key test/rotation, history
rewrite or readiness promotion is implied. Whole-goal FAIL remains unchanged.
