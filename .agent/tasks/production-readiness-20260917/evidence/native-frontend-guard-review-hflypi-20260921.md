# Frontend guard review — hfLYPi

The independent read-only reviewer accepted the final v5 preload and launcher
semantics for the trusted frozen frontend unit suite. This is not acceptance
of unrun tests, real API integration, or an adversarial security sandbox.

Preserved attempts:

- v3 blocked Vite's localhost DNS lookup before tests started: harness startup
  incompatibility, not a product failure.
- v4 ran 830 tests: 828 passed, two ProgressPage tests failed and one unhandled
  exception was reported. The preload made global fetch throw synchronously.
  CardAuditPanel's useApiData chained `.then/.catch` on the expected Promise,
  so the artificial synchronous exception crashed the React tree. These are
  harness-induced results, not evidence of a product network-failure defect.
- v5 refuses the same requests with rejected Promises. Its activation probe
  requires a thenable, no synchronous fetch throw and an actual guard rejection.
  Callback DNS is asynchronous, supports numeric family options and computes
  approved loopback answers entirely in memory, without calling original DNS.
  Callback exceptions are not swallowed/retried. Guard scope text and capture
  failure labels were corrected after review.

The source tests and product assertions are unchanged. The two formerly failing
files pass under v5: six tests, 18.362s captured duration. Full-suite evidence
and post-run frozen-source identity are reconciled separately; this review does
not substitute for their captured results.

Limits: this blocks common Node net/http/https/tls/dns/dgram/global-fetch paths,
not arbitrary child-process or custom native-binding execution. Socket IPC is
also denied, so no general IPC-preservation claim is made. The unmocked relative
API requests in the two ProgressPage fixtures remain fixture limitations; these
unit results do not prove live API behavior. Earlier failed captures and guard
bytes are retained, not overwritten by green attempts.

## Final bounded reconciliation

The same independent reviewer verified all28new frontend capture hashes, the
six prep captures and the42earlier isolated captures. v6 uses byte-identical
v5guard code with `--maxWorkers=2`: actual full result830/830,143files, exit0,
197.257s; scoped3/3 and guard activation pass. The post-run5720tracked blobs
match exact99849935 with zero mismatches. Default-parallel v5 remains failed;
no claim of a product fix or unrestricted concurrency stability is made.

The reviewer found one future-only capture-label defect: the failure handler
still tested the retired `--targeted-progress` option instead of current
`--targeted-flaky`. Root corrected that literal and repeated static quality
checks only, as recommended. No historical capture or test result was changed,
and no test/Docker/DB rerun was needed for this reporting-only correction.
