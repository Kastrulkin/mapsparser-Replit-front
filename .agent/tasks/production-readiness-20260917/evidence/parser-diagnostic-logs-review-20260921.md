# Parser runtime diagnostic-console privacy — independent source review (2026-09-21)

## Result

**FIX_PROVEN at the bounded `parser_interception.py` runtime-console boundary.** No remaining raw URL, title, address, review/post body, arbitrary item-key, exception-string, or dynamic type-name interpolation was found among its runtime `print` expressions. This is a console-output finding only; it is not a general parser-return, worker, provider, browser, image, or log-retention assurance.

## Causal evidence and current-input reconciliation

The retained causal evidence is complete and value-safe:

- `parser-diagnostic-logs-red-20260921.json`: 6 expected failures, exit 1, 501.663 ms. It demonstrates raw input/response URL, writer exception text, invalid-input URL, review values, and post values/key leakage through isolated AST-extracted current methods.
- `parser-diagnostic-logs-green-20260921.json`: the same 6 cases pass, exit 0, 465.935 ms, with no truncation. It records the edited parser SHA-256 `a9737321cb60869d632f0d155bc0905b2e72c5caf6950507b8bb137a0ee04a0a`; that equals the current source. Its tests use an external-I/O guard and no conftest.

The source diff replaces the prior direct values with fixed event text, booleans, counts, controlled parser-mode/status values, or `debug_url_summary`. It removes exception bindings from console-only catches, makes validation failures omit the supplied URL, and keeps raw parser values in returned data rather than printing them. The explicitly raw `__main__` result dump at lines 2768–2769 is a CLI-only demonstration path and is excluded from the runtime-worker console claim.

## Dynamic-console map

- URLs now pass through the bounded `debug_url_summary` at initial parse, intercepted-response, current/overview-page, and best-product-source events. It retains provider/route categories and booleans, not host/path/query/userinfo content.
- Organization ID, debug bundle directory/name, page title, address, rating, review response, post title/date, response text, and raw item keys are no longer interpolated. Diagnostics retain `*_present`, counts, bounded status/mode, and fixed event context.
- The formerly sensitive exception `str(e)` sites now print static failure events. Session-kwargs validation retains only `count=<n>` in both its production log and debug-environment `ValueError`.
- The apparent `key` interpolation in the posts log is safe after binding analysis: its loop variable is restricted to the four source literals `posts`, `publications`, `news`, and `items`; it is not a key drawn from provider data. Arbitrary keys inside a post item are not emitted.

## Functional and scope limits

The patch preserves parser flow, error codes, returned `url` fields, result data, retry/captcha branching, and controlled metrics. `YandexMapsInterceptionParser._fallback_html_parsing` still returns `{error: str(e), url: url}` on failure, but it has no in-repository call sites; it is a return-payload risk outside the console patch and was intentionally left unchanged. The worker's normal validation reads generic `error` and optional `message`; `parser_config` only requires `url` for the captcha compatibility path. Do not generalize the console result into a claim that all downstream payloads are redacted.

The six GREEN tests exercise representative source-level paths, including raw-return preservation. They do not execute a full browser/session/provider lifecycle, worker subprocess forwarding, existing log files, the CLI entry point, or an image/runtime deployment. The separately reported actual-module invalid-input RED capture was not available under the stated evidence filename during this review and is not relied on here; pending combined helper/adjacent checks likewise are not claimed. No application import, provider/network/DB/Docker/deploy/cleanup/test execution, staging, or commit was performed by this reviewer.

## Final freeze reconciliation

The final combined capture, `parser-diagnostic-logs-final-20260921.json`, is complete: exit 0, 29 passes in 0.53 s (capture 834.243 ms), no output truncation, external-I/O guard enabled, and no conftest loaded. Its eight source hashes match current inputs, including the final diagnostic test SHA-256 `489bb061a99567111540bd9bbf91853a2f21bcce93f444ae53c8b8bedcfff56e` and parser SHA-256 `a9737321cb60869d632f0d155bc0905b2e72c5caf6950507b8bb137a0ee04a0a`.

The added boundary cases cover missing review dates with hostile fields, string owner replies, invalid post-timestamp exceptions, valid HTTP input lacking an org ID, CAPTCHA title privacy while retaining the explicit returned CAPTCHA URL, and debug-environment unknown session kwargs reduced to a count. Those tests appropriately preserve parser values/return semantics while asserting that diagnostics omit the synthetic marker.

The actual-module invalid-input pair closes the earlier evidence gap: `parser-diagnostic-input-red-20260921.json` (exit 1, 149.291 ms) records marker presence in both stdout and `ValueError`, while `parser-diagnostic-input-green-20260921.json` (exit 0, 162.939 ms) preserves URL rejection but records marker absence from both. The quality capture is also successful (281.307 ms): it proves non-diagnostic parser AST equality against parent `074ee5a0`, both scoped Ruff checks pass, and `git diff --check` exits 0. The diff check has a nonfatal Darwin temporary-directory warning, so this is not a clean-stderr assertion.

These final captures support the bounded **FIX_PROVEN** result above. They do not expand the claim beyond runtime parser console output: the CLI-only result dump, fallback return payload, downstream worker/legacy-route logging, existing logs/artifacts, real provider/browser behavior, container image, and deployed retention/access controls remain outside proof.
