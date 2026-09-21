# Frozen OAuth-capture rows 1–3 review — 2026-09-21

## Classification

**TEST_TRANSCRIPT_CONTEXT_ONLY / UNKNOWN** — all three rows are in one
test-run transcript, but their exact matched values have not been proven to be
synthetic test inputs. They remain unclassified and must remain in the
canonical remaining-history count.

This is based on the exact frozen binding, not the filename:

- Frozen history metadata rows **1–3** share one commit, one file, one rule,
  and physical JSON source line 21.
- Physical line 21 is the capture wrapper's `stdout` field. The wrapper's
  command targets `tests/test_google_oauth_current_access.py`, uses a test
  runner, and exited nonzero as a deliberately retained red capture.
- Its decoded stdout identifies exactly two current-access recheck test cases;
  both are defined in that test module and the transcript contains a test
  failure marker.
- Static AST review of that module establishes a pytest callback fixture, a
  local `OAuthDatabase` test double, and fixture-scoped monkeypatching. No
  network client library is imported by the test module. The two captured test
  cases use that callback fixture.

## Exact-match check and result

The scanner configuration extends Gitleaks v8.30.1 defaults. In memory only,
the default `generic-api-key` rule was applied to the exact frozen physical
line 21. It yielded three candidate matches, equal to the report's three-row
count. The captured value group from each candidate was then compared without
output against both:

- literal strings in the frozen test module; and
- statically evaluable pure string expressions in that module.

**Result: zero of three exact group equalities in either comparison.** Fixture
and test-transcript provenance therefore cannot establish that the reported
matches are synthetic values. The earlier synthetic classification is
withdrawn.

No match, secret, response line, token value, URI, or provider request was
printed or performed during this review.

## Limits

This identifies only the test-transcript context. It does not prove that any
matched value is synthetic, test credential validity, contact a provider,
establish revocation, prove that other history findings are synthetic, or make
the all-refs history scan clean. The capture's red test result remains
historical evidence, not a test pass. A future reclassification requires an
independent exact-value binding to a known synthetic input or another
value-free, deterministic provenance proof.
