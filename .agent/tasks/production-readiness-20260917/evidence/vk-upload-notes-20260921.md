# VK upload destination — bounded local correction

Parent: `8be8e45a5a2930607311becebf05a3d456d100b0`.
Finding: **SEC-VK-UPLOAD-DESTINATION-01**, P1 security, local FIX_PROVEN for
private/rebinding destinations. This addresses part of cumulative **P1-BE-01**,
not every provider-trust risk. Whole readiness remains FAIL.

## Cause, impact and change

An approved-photo upload accepts `upload_url` from a VK API response and used
unrestricted `outbound_urlopen` for the multipart body. Provider responses are
an untrusted boundary in SECURITY.md. With a malicious/malformed response,
photo bytes reached a mocked request boundary for private or non-HTTPS targets.
The baseline already contains this behavior; it is not a regression introduced
by the recent module extraction. No real exploit, file write, data exfiltration
or production incident was exercised or demonstrated.

The new `public_pinned_https_post` rejects non-HTTPS/credentialed destinations,
validates every DNS address twice, then connects to a validated public IP with
the logical Host/SNI and certificate hostname. Explicit HTTP(S) proxy routing
uses CONNECT to that IP without direct fallback. Redirects/retries are disabled.
The upload response read is capped at 1,000,001 bytes, with a 1,000,000-byte
accepted limit. HTTP, decode, empty/invalid JSON, oversized and transport errors
stop with finite local error codes. Valid parsed provider JSON is otherwise
preserved, including its error payloads; this is not universal diagnostic
sanitization. Fixed VK get-server/save API routing, callback POST, media GET,
approval decisions, database and business policy are unchanged.

Impact: prevents approved media from being submitted to private services under
the stated provider-response threat. Confidence is high for the local boundary;
production likelihood is unmeasured. Effort/blast radius are small (two runtime
files), with medium transport compatibility risk. Required before production.
Rollback is a local revert of this package after review, not an automatic
deployment action; reverting would reintroduce the destination weakness.

## Actual proof

All captures below are in this directory with suffix `-20260921.json` and
contain exact commands. The manifest binds source and capture SHA-256 values.

| Capture | Result | Captured ms |
| --- | --- | ---: |
| vk-upload-final12-baseline | Same final causal subset on immutable parent: 11 assertion failures, 1 success control, 0 errors | 446.770 |
| vk-upload-final25-green | 25 current tests pass; includes the 12 causal cases and 13 additional checks | 671.103 |
| vk-upload-adjacent24 | 24 selected unchanged assertions pass: 2 proxy, 1 callback POST, 11 media GET, 10 public GET | 487.616 |
| vk-upload-quality | Scoped Ruff, exact unaffected-AST parity, diff check, 13 foreign and 3 historical hashes preserved | 358.472 |

No final capture timed out or truncated output. New tests exercise private,
mixed and rebound DNS, credentials, HTTP/file schemes, public success with
1,200-character photo JSON, TLS identity/Host/query/port, IPv6, proxy/no fallback,
redirect refusal, overflow, invalid JSON, read failure and resource cleanup.
Three tests use real urllib3 manager/pool/connection construction and proxy
preparation, intercepting `connect` before sockets. They prove construction and
CONNECT configuration, **not actual TLS or proxy interoperability**.

The runner denies socket activity, child processes after installing its guard,
environment-file reads and PostgreSQL/Docker imports. It does not import the
application or pytest conftest. Current adjacent checks preserve existing test
bodies but AST-select only isolated network assertions; the actual facade,
database callbacks and contact collector integration are excluded. This is not
an aggregate backend, provider or deployed test run.

Independent reviewer `cumulative_frontend_review_20260921` accepted the two-file
runtime diff and 22 initial tests, then separately accepted the three actual
urllib3 construction tests. Static acceptance does not expand runtime proof.

## Retained failed and intermediate evidence

`vk-upload-initial-red` accidentally ran zero tests with exit 0: a harness
failure, never a product PASS. `vk-upload-causal-red` corrected discovery and
ran 6 tests with 5 failures/1 control. `vk-upload-six-baseline` and
`vk-upload-six-green` compare the adapted six. `vk-upload-causal12-baseline`
and `vk-upload-guarded22-green` precede the three construction tests. They are
retained history, not substitutes for the final same-source comparison.
Current-only hardening injections are not counted as baseline reproductions.

## Remaining boundaries

- A malicious **public** HTTPS upload host returned by a compromised provider
  can still receive media. No verified VK upload-host allowlist was available;
  do not invent one or assume `api.vk.com` hosts uploads. This part of P1-BE-01
  remains a documented trust-policy question, not a closed finding.
- urllib3 timeout configuration is not proof of an absolute wall-clock deadline
  against slow-trickling responses. Real proxy/TLS and provider contract checks
  remain unexecuted. No response-model completeness claim is made.
- No production, DB/schema, provider side effect, Docker, cleanup, push or
  deployment. Native aggregate/restore preparation remains denied; the image
  disk gate and original acceptance criteria are unchanged.
- Cumulative source review is still partial. Outstanding backend assertions,
  historical evidence reconciliation and original release gates remain; this
  small correction cannot establish whole-project readiness.
