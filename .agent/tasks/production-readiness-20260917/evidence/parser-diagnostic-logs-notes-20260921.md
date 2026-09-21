# SEC-PARSER-LOG-01 — parser diagnostics (21 September)

Parent: `074ee5a01841d7e52adaa7fe5395a60217c24add`. Branch and original
whole-project acceptance remain unchanged; nine unrelated paths are excluded.

## Contract and reproduced cause

The original objective prohibits sensitive data in logs; SECURITY.md and the
previous debug-file correction distinguish application data from diagnostics.
The current parser interpolates provider/user URLs, business fields, review
author/reply/date, post content/keys and exception messages into stdout. These
logs are not gated by the disabled-by-default debug-file option.

The first guarded actual-module probe (`parser-diagnostic-input-red`) proves
that even a rejected synthetic input reaches both stdout and a ValueError
message. It fails on the privacy assertion, not on missing dependencies. No
real browser, provider request, database or production data is involved.

Impact is conditional on the input and log readership: credentials in URLs
or provider errors and private content can enter durable process logs. This
is a local reproduced P1 boundary defect, not evidence of an actual production
compromise. The root cause is raw interpolation, not a missing secret-name
regex. The intended correction uses explicit static events, presence/counts
and the existing fixed-category URL summary; it does not mutate parser data.

## Scope limits

No assertion of universal log sanitation: BrowserSession, worker, HTML fallback
dependencies, CLI-only explicit result output, existing files/logs and deployed
code are separate boundaries. Raw return data still exists by design, including
error/captcha URLs. The unused fallback method's raw error return is unchanged.
No cleanup, rotation, schema/data change, push, deployment or acceptance upgrade.

## Final bounded evidence

The six actual synthetic tests fail only on privacy assertions after payload/
branch controls; corrected harness defaults were read before running RED.
RED501.663ms becomes GREEN465.935ms. Actual-module validation probe separately
changes from exit1/149.291ms to exit0/162.939ms. Expanded final29 pure checks
pass0.53s/capture834.243ms:12diagnostic and17previous helper/parser/orchestrator.
Sockets, child processes and SQLite are denied; no conftest/plugin autoload.

Final quality281.307ms passes scoped Ruff, undefined-name checks, diff and
eight hash bindings. Normalized non-diagnostic AST equals parent074ee5a0.
Its Git child has a nonfatal Darwin temp-path warning. No capture timeout or
truncation. Independent review covers all runtime print expressions; the
suggested arbitrary top-level key leak was withdrawn because the variable
comes from a fixed four-member source list. The CLI-only raw result is excluded.

This is bounded FIX_PROVEN, not original whole-project acceptance. The earlier
file-persistence and the current console boundaries have distinct proofs.
