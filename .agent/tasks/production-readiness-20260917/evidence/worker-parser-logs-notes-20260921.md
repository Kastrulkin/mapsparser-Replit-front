# SEC-WORKER-PARSER-LOG-01 — bounded console fix

Parent: `fdbabac4d830cb82d3ec2ffcb0f884b6250c141a`.
Priority P1 before production; high confidence in the six reachable sinks.
The ordinary Yandex proxy fallback and subprocess-result handlers interpolate
arbitrary provider messages/tracebacks into console output. Truncating those
strings does not protect input URLs, credentials or private provider content.
See `parser-adjacent-log-candidates-20260921.md` for the call path.

## Change and proof

Only `src/worker.py` changes runtime code. Six print expressions now emit
fixed event/category text rather than arbitrary message/traceback/error values.
Two unused diagnostic temporaries and an unused exception binding are removed.
Proxy identity, retry admission, arguments, return/rethrow behavior and original
persisted reason are retained. This intentionally reduces console detail.

Five AST-isolated tests exercise direct proxy recovery and rethrow, subprocess
error result and exception, and successful subprocess recovery. They assert
synthetic-marker omission, actual retry calls, proxy=None, fixed events and
preserved/replaced result identity. Neither worker top-level imports nor an
application/database/browser/provider is executed.

Authoritative root RED `worker-parser-logs-final-baseline-20260921.json` uses
the final test bytes and immutable parent worker AST:5fail/0errors,300.591ms.
It binds parent worker SHA-256
`fd6e429dd7a016ed8d59ee3a4b5ed95c376721d0cc68fa20bbeec5b19e744ca8`
and final test SHA-256
`4a2221cbea7d7190beaab53bc8b104d4adb6c641492d8a579f5325d77d66513b`.
The root current capture reports34pass/0.76s/1075.389ms and binds the same test
plus fixed worker SHA-256
`21e02cc78241de155460f6a53279e569cf02dffc4e63439d5b17ced9f096f910`.
The34 comprise5new cases plus29existing parser/helper/orchestrator cases, not
34files or a whole-worker integration suite. External I/O is denied; pytest
conftest and third-party plugin autoload are disabled.

Quality capture6827.410ms verifies13source hashes, scoped Ruff/diff checks,
non-diagnostic AST parity and110historical report bindings. The normalization
omits print expressions, the two diagnostic temporaries and now-unused retry
binding only. This is source-scope proof, not general semantic equivalence.

## Independent review and evidence limitation

The independent reviewer initially observed a temporary baseline during the
agent's expanded RED and correctly rejected applying an earlier green to it.
After explicit freeze, the reviewer verified both source hashes, all six sinks,
the five test contracts, current34pass capture and root immutable-parent RED,
withdrew that pre-freeze observation as a final finding and approved the bounded
fix. Classification: **FIX_PROVEN for these two diagnostic branches only**.

During expansion the agent overwrote its initial3-case RED and4-case GREEN
captures. Original bytes are unavailable; no fabricated recovery was attempted.
The same-named retained pair covers5cases (RED238.070ms/GREEN232.021ms).
Root independently reproduced the final RED from immutable parent AST without
reverting shared files, then reconciled it with the final hash-bound GREEN.
Use this root pair, not the discarded intermediate observations, for acceptance.

## Residual risk and next action

Raw proxy health reasons, other worker prints and debug-file writers, supported
legacy scraper diagnostics, retained logs/files and deployed code remain outside
this correction. Do not infer that provider credentials are absent from them.
Next: reproduce legacy scraper URL/contact diagnostics and worker artifact
writers, then correct them under their respective data contracts. No native
aggregate/restore, Docker, production, cleanup, provider, push or deployment
action occurred. Whole readiness and original AC statuses remain FAIL.
