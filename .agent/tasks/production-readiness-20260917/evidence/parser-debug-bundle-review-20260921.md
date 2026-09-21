# Parser debug-bundle safety — independent static review (2026-09-21)

## Result

**FIX_PROVEN at the bounded debug-file boundary.** The patch removes the reproduced persistence channel while preserving raw data only in parser memory. This is not a runtime, provider, log-retention, existing-artifact, image, or production-data assurance.

## Causal evidence and changed sink coverage

`parser-debug-bundle-red-20260921.json` is a valid causal RED: its extracted nested response handler wrote the synthetic provider marker to an opt-in JSON bundle while the disabled-bundle branch passed (1 failure / 1 pass, 142.814 ms). It compiles that handler directly and does not import the application.

All current filesystem writes gated by `debug_bundle_dir` in `src/parser_interception.py` now use bounded value-free output:

- intercepted response JSON (`~673–680`) and canonical `payload.json` (`~1542–1546`) use `debug_value_shape`;
- redirect and failed-page artifacts (`~854–888`), per-page HTML (`~1471–1473`), and canonical `page.html` (`~1513–1519`) use `debug_html_placeholder`;
- summary URLs, request URL, and final URL (`~1420–1434`, `~1521–1532`) use `debug_url_summary`; summary fields reduce cookie domains and organization identity to counts/presence;
- summary `found_key_paths` is reduced to per-key counts before write (`~1463–1469`), and the authenticated screenshot write is removed.

The response filename is now time-based rather than URL-derived; the summary names are time-based and no screenshot path remains. Raw `json_data`, response metadata, `api_responses`, and final parser `data` remain in memory for parsing and control flow, so the patch does not intentionally alter extraction behavior.

## Helper boundary assessment

`src/core/parser_debug_artifacts.py` is appropriately bounded for JSON-shaped provider data:

- `debug_value_shape` emits only type, string length, object/array counts, a fixed allowlist of field *names*, at most depth five, three list samples, and a 120-node traversal budget. It emits neither arbitrary keys nor scalar values.
- `debug_url_summary` emits fixed provider/route categories and booleans only; it does not retain host, userinfo, path, query, or fragment. The route vocabulary is finite.
- `debug_html_placeholder` emits fixed HTML plus source character count only.

The intentional diagnostic tradeoff is material: raw payload/HTML/URLs/cookies and screenshots can no longer be recovered from debug bundles. A future support workflow that needs such material must be separately designed with explicit access, retention, and redaction controls—not by weakening these artifacts.

## Residual limits and adjacent risks

- Shape/count/length metadata can disclose coarse structure; it is value-free, not information-free. The scope is bounded because inputs are JSON response trees and traversal/sample/depth limits apply.
- The existing parser stdout diagnostics still interpolate raw title/address values (`DEV summary` and final completion logging around `~1480–1552`). They are not debug-bundle file writes and predate this patch, but filesystem sanitization must not be represented as a general log-redaction guarantee.
- `debug_bundle_id` construction/path logging remains outside the new artifact helper boundary; this review makes no claim about bundle-directory access controls, retention, or path sensitivity.
- The current RED test directly exercises the response-JSON sink and disabled branch. It does not by itself execute all HTML, URL, summary, payload, or screenshot-removal paths; the static sink trace above is the basis for those conclusions until the owned expanded test evidence arrives.

No application/runtime import, test execution, database, Docker, provider request, production action, deletion, staging, or commit occurred in this review. Nine foreign paths remain outside scope.

## GREEN and adjacent-test reconciliation

The retained `parser-debug-bundle-green-20260921.json` is complete and successful: 5 tests, exit 0, 91.599 ms, no stdout/stderr truncation. Beyond the causal handler/disabled-bundle cases, the expanded tests prove that the helpers do not mutate fixture input; withhold synthetic values and arbitrary keys; terminate a cycle at the depth boundary; cap array samples; and emit only summary/placeholder data for hostile URL and HTML fixtures. They also source-assert the canonical write expressions and absence of the prior raw canonical expressions.

`parser-debug-bundle-adjacent-20260921.json` is separately successful (12 tests, exit 0, 868.012 ms). It records hashes for the three existing parser-unit files plus `parser_interception.py`, `browser_session.py`, and the new helper, and reports an I/O guard that denied socket, process, and SQLite use with no conftest loaded. This is credible adjacent regression evidence for actual parser-module imports; it is not an authenticated browser or provider run.

Accordingly, the reproduced raw-response file persistence is **FIX_PROVEN at the bounded debug-file boundary**: RED writes the synthetic marker, GREEN proves the changed response sink and helper contracts do not, and static inspection covers the remaining changed artifact sinks. The claim deliberately stops there. The causal response test executes an AST-extracted nested handler rather than the full parser/browser lifetime; the source-expression assertions are regression guards rather than exhaustive data-flow proofs. Runtime environment/import packaging, real session behavior, live images, provider data, existing artifact cleanup, and log retention remain unknown.

## Final combined capture and hash reconciliation

`parser-debug-bundle-final-20260921.json` is complete: exit 0, 17 passes in 0.23 s (capture 539.002 ms), with no stdout/stderr truncation. The final safety suite adds coverage for the shared traversal budget on a wide cyclic structure, non-string URL input, and AST confirmation that no `screenshot` call remains in the parser source. Its seven recorded source hashes—including `tests/test_parser_debug_bundle_safety.py` SHA-256 `b0f691e584b322d3a3865223d367e9749dc909bf5d46f16bdfdeffbfad985748`—match current inputs; the combined capture correctly records that it is not backend/browser/image proof.

`parser-debug-bundle-quality-20260921.json` is also successful (2,938.348 ms): both scoped Ruff checks and Node syntax check exit 0, and `git diff --check` exits 0. The latter emitted a nonfatal Darwin temporary-directory warning, so this is a successful diff check, **not** a clean-stderr claim. No quality or test result alters the bounded FIX_PROVEN boundary or the residual runtime/live-image/provider/log/retention limits above.
