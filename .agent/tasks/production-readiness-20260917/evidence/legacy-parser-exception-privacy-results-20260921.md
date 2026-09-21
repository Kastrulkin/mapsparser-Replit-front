# SEC-LEGACY-EXCEPTION-01 — local parser exception privacy checkpoint

Status: **FIX_PROVEN locally, bounded scope only.** This is a child finding of
`SEC-PARSER-LEGACY-LOG-01`; it does not close that parent, make a deployment
claim, or establish a production incident.

## Exact result

The final four-case regression test ran on Darwin arm64 with the isolated native
Python runtime. Its immutable-parent capture has **4 failed**, while the same
test bytes against the corrected workspace have **4 passed**. The corrected
adjacent harness reports **7 passed** (four diagnostic-log and three leaf-log
checks). Scoped Ruff and `git diff --check` passed.

The final cases prove that synthetic private exception text is absent from the
outward parser-config ImportError notice, invalid-URL exception value/stdout/
formatted traceback, and both legacy Playwright timeout and general exception
value/stdout/formatted traceback. They preserve parser selection and return
payload, invalid-URL `ValueError` and no Playwright admission, plus browser
close on timeout/general paths.

The immutable comparison is bound to parent revision
`ea1a50362ddf56e9267dded0a361e55dcfded23d`; source blobs and the final-test
hash are recorded in `legacy-parser-exception-privacy-final-red-manifest-20260921.json`.
All eight capture hashes plus the current hashes for the two production sources
and new regression test are recorded in
`legacy-parser-exception-privacy-manifest-20260921.json`.

## Reproduction provenance

An earlier three-case RED capture is retained, but its first browser-close
control assertion followed the marker assertion. That assertion therefore did
not execute on its privacy failure and is not used for the final control claim.
The final four-case RED is the causal comparison.

The first frozen adjacent invocation is also retained. Its leaf harness compares
`SOURCE_TEXT` with `CURRENT_SOURCE_TEXT`; patched stdin makes those bytes differ,
so it enters historical RED expectations for a sink already changed by an
earlier package. This is a harness/source-version mismatch, not a product RED.
The v2 invocation uses clean current leaf-test bytes, which are identical to the
frozen file; only invocation mode changed and no assertion or test was changed.
It passes all seven adjacent checks.

## Caller compatibility review

`parser_config.get_parser` selects an interception or legacy parser at import;
the revised ImportError message is a display notice only. Worker routes use
`_parse_yandex_card_with_playwright_fallback`. Its dedicated sync-in-async
fallback reacts only to the known Playwright phrase. That exception originates
before the legacy parser inner try, so the fixed timeout/general branches do
not mask it. Forced subprocess routes turn a legacy exception into the stable
`parser_subprocess_exception` result code; proxy retry and transient retry
branch on that code, not its message. Raw-message policy remains limited to
2GIS timeout and Apify empty-dataset cases, not this legacy parser.

No structured raw-reason retention is needed for the current policy. If a later
policy must distinguish legacy timeout from another parser failure, it should
receive a new finite structured result code rather than restored exception text.

## Narrow limits and next boundary

This checkpoint intentionally excludes a potential fifth invalid-URL case in
which a caller already handles an unrelated exception; that is distinct from
the direct invalid-URL leaf proof here. Context-manager entry and browser
lifecycle before the legacy parser inner `try` are separately excluded. Broader
legacy leaf/value logs, provider/browser execution, and every worker or
public-route error sink are also outside scope. The tested outward exception
messages now use fixed codes; no live HTTP route was exercised. Other exception
sources can still reach the public route's raw error interpolation and remain
outside this proof. Existing logs/artifacts, deployed source and historical
retention are not assessed.

## Finding contract

**Category and priority:** confidentiality/security P1 child finding, required
before a release containing this legacy fallback boundary; it is not a complete
before-demo or production-readiness clearance.

**Business effect:** an operator or user-facing diagnostic could disclose a
private parser input or provider-derived exception value to its normal reader.
No production incident, affected user, frequency, or real private value is
claimed; the evidence uses a synthetic marker.

**Technical risk and root cause:** supported legacy fallback paths interpolated
an ImportError or caught exception directly into outward text, and chained
exceptions could retain that text in formatted tracebacks. The corrected narrow
projection emits finite local codes while preserving the applicable exception
class, parser return contract and browser-close behavior.

**Fix risk, blast radius and effort:** small source surface in two parser files;
low expected control-flow blast radius and medium diagnostic-fidelity tradeoff.
Compatibility confidence is high for the four synthetic contracts and reviewed
worker callers. Execution likelihood is bounded to supported fallback/error
paths; production frequency and log-reader exposure remain unmeasured.

**Acceptance:** immutable final four failures become four passes with identical
test bytes; parser selection/return payload, `ValueError`/no-browser admission,
timeout/general browser close and marker absence from value, stdout and formatted
traceback remain asserted; seven adjacent checks and scoped static checks pass.
The excluded caller-level invalid-URL and pre-inner-try lifecycle branches need
their own causal reproduction before any wider closure.
