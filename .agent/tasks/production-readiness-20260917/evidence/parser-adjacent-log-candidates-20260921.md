# Adjacent parser diagnostic candidates — bounded static review (2026-09-21)

## Result

Two high-confidence, currently reachable raw-value console candidates remain at
the parser boundary.  Both predate `fdbabac4d830cb82d3ec2ffcb0f884b6250c141a`:
the exact-base-to-current diff for `src/browser_session.py`, `src/worker.py`,
and `src/yandex_maps_scraper.py` is empty.  They are therefore **not evidence
of a regression introduced by the recent parser diagnostic patch**, but are
separate production-readiness candidates for the owner to decide on.

This was source-only review: no module import, worker/provider execution,
database access, network access, scanner, or real-value inspection occurred.

## Candidate 1 — P1: worker emits arbitrary parser/provider exception text

**Sink.** In `src/worker.py`, the broad catch around the ordinary parser call
converts an exception to `msg = str(e)` at lines 5846–5848, then, when the
Yandex worker currently has an active proxy, prints the first 160 characters at
lines 5850–5854.  The retry failure prints the first 180 characters of another
arbitrary exception at lines 5875–5878.  The same job path also prints the
first 240 characters of a returned parser-subprocess message and the first
five traceback lines at lines 5927–5934.

**Reachability/contract.** A queued Yandex job obtains a proxy at lines
5652–5663 and calls `_parse_yandex_card_with_playwright_fallback` with that
proxy, cookies, and the job URL at lines 5797–5812 (the native-first route
similarly calls it at 5738–5761).  The fallback helper deliberately re-raises
ordinary non-async Playwright errors at lines 1389–1398, so they reach this
outer catch.  Provider/Playwright exception text is not an application-owned
enum and can include a requested URL, redirect/location, proxy diagnostic, or
server-provided text.  Truncation is not redaction.

There is an important narrower safe path: the Yandex subprocess entry applies
`redact_sensitive_text` to its exception and traceback before returning them
at lines 992–999.  That does not sanitize the direct-call/retry exceptions
above, and it does not make arbitrary provider error text safe before it is
printed.

**Small synthetic red test proposal.** Extract/execute only the surrounding
worker branch with all DB and browser collaborators replaced by stubs; make the
parser stub raise `RuntimeError` whose message contains a synthetic marker URL
or cookie-shaped marker, set `active_proxy` and `parsed_source` to the reachable
Yandex values, capture stdout, and assert the marker is absent.  It should
currently fail because line 5852 interpolates `msg`.  The production change can
retain the proxy id, a controlled exception class/event code, and retry state,
while replacing `msg`/`retry_msg`/traceback content with value-free metadata.

## Candidate 2 — P1: supported legacy Yandex fallback prints input and card PII

**Sink.** `src/yandex_maps_scraper.py` prints the supplied URL before validation
at line 139 and repeats it in the invalid-URL `ValueError` at line 142.  On a
successful browser parse it prints provider-derived title and address at line
304.  `parse_overview_data` prints a provider-derived telephone number for all
three supported extraction variants at lines 483, 504, and 517.  These are
runtime `print` calls, not a command-line result serializer.

**Reachability/contract.** `src/parser_config.py` selects this function whenever
`PARSER_MODE` is `legacy`, and also falls back to it if importing the
interception parser fails (lines 16–31).  `src/worker.py` imports the configured
`parse_yandex_card` at line 4923; its subprocess entry imports the same
configuration and invokes it with the queued URL at lines 980–999.  Its normal
Yandex path invokes the configured function through
`_parse_yandex_card_with_playwright_fallback` at lines 5797–5812.  Thus the
legacy implementation is a supported configuration/fallback path, not an
unreachable historical CLI.  A URL can carry query identifiers; card title,
address, and telephone are externally sourced business/contact data.

**Small synthetic red test proposal.** AST-extract `parse_yandex_card` into an
isolated namespace with a valid synthetic marker URL and a `sync_playwright`
stub that raises a private sentinel immediately after the initial `print`.
Capture stdout and assert the marker is absent; it currently fails at line 139.
For the phone sinks, execute an AST-extracted overview fragment against a fake
page/link returning a synthetic phone marker and assert captured stdout omits
it.  A minimal fix is value-free progress/status/count output; preserve the
returned `data` contract rather than logging its values.

## Explicit exclusions and limits

- `src/browser_session.py` (195 lines) contains no `print`, logger, or other
  diagnostic output sink.  It passes cookies only to `context.add_cookies` at
  lines 102–107 and suppresses its exception without formatting cookies; no
  raw-cookie output candidate was found there.
- Controlled worker status output (for example queue id, parser route, boolean
  health result, event/error enum, or a fixed `type(...)` name) was not reported
  as a raw-value candidate.  The report also does not treat `parser_config.py`'s
  import-error interpolation as one of the two selected candidates.
- This does not prove all parser-adjacent sinks, other provider modules,
  persistent error fields, or historical revisions clean.  It makes no claim
  about live log retention/access, actual provider exception content, cookie
  validity, runtime configuration, or end-to-end remediation.
