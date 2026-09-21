# Proxy diagnostic projection — 21 September 2026

SEC-PROXY-DIAGNOSTICS-01 is a bounded local confidentiality correction.
Parent: `ae609660cfb5f0d5a087164efb49b352b8507e9e`.

The raw RequestException-derived preflight reason was printed in the selected
map-proxy path and entered review metrics, native-only worker errors and
delta/full fallback warning SQL. Proxy-stat DB exceptions also printed the
raw reason and exception. Synthetic-marker tests reproduce these paths.

The correction leaves `_preflight_yandex_proxy` unchanged. A finite helper
projects known statuses, bounded HTTP codes and request class prefixes for
diagnostics; unknown text becomes `proxy_preflight_failed`.
`_mark_proxy_result` retains raw internal policy input and its original
circuit-breaker/SQL behavior, but its exception log is value-free. The map
failure path projects the reason after health marking; review metrics use the
projection while the health marker receives the original reason.

## Verification

- Final worker SHA-256:
  `c88fee3044cbb07b1ae8b474d570f6466de4ae57146e0a5c259cb0842d327141`.
- Final test SHA-256:
  `cf29e935a0bd2f1fc3633597ecf5643801fd96701a30dff7eab93f6f59e1811e`.
- Same final 7 tests: immutable parent 5 assertion failures / 2 passes /
  0 errors (0.518 s, captured 925.375 ms); current 7 passes (0.656 s,
  captured 786.558 ms).
- Broad: 135 tests + 4 subtests, 17 files, 31 source hashes stable before/after,
  15.19 s / captured 15877.751 ms. No full worker import, network, env-file,
  subprocess or real DB; the existing owned IPC synthetic fork is intentional.
- Adjacent: 16 exact existing AST-isolated proxy/review/validator/retry tests,
  411.193 ms, including actual pure completeness/validation bodies.
- Quality: 589.819 ms; new-test Ruff, worker F821/F822/F823, diff and exact AST
  parity for unchanged preflight, health SQL/cleanup, map control and review
  fallback behavior outside the diagnostic substitutions. Local Git/Ruff run.
- Independent runtime/test and evidence reviews accepted the frozen scope.

The manifest binds all 31 source hashes and 6 captures. Initial 3-test RED
(2 failures / 1 pass, 623.102 ms) is retained separately. Optional helper
scaffolding and the full-review case were finalized before the final baseline;
no captured harness failure or weakened assertion is claimed as product proof.
Local test durations are not service-performance measurements.

## Limits and next step

Raw preflight return and health-policy input remain internal functional data.
Other completeness/card/host:port/CAPTCHA/DLQ/handler diagnostics, old rows and
artifacts/history remain outside this slice. No full-worker/native DB/provider/
image or deployed proof, production mutation, cleanup, push or deploy.
Whole FAIL, original AC1–9/11 FAIL and AC10 PASS remain. Native aggregate/restore
preparation remains denied; disk checkpoint 4108936 KiB (~3.92 GiB) is below
10 GiB. Next: a fresh cumulative committed source/diff review, without treating
source review as aggregate/image/demo acceptance.
