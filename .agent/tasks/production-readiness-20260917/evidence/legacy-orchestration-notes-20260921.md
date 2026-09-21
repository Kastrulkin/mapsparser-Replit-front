# SEC-LEGACY-ORCHESTRATION-LOG-01 — bounded fallback parser console fix

Parent `5ef5ba7e811d31d8599857929f2b79219c5954d4`; P1 before production,
high confidence in four selected reachable sinks. `parser_config.py` selects
`yandex_maps_scraper.parse_yandex_card` for legacy mode and interception import
fallback; this is supported runtime code, not solely a CLI.

Four prints in `src/yandex_maps_scraper.py` no longer echo arbitrary launch/
overview exception text, input URL, title or address. They retain fixed events
and fixed browser-engine names. Only two now-unused exception bindings are
removed. All actual parsing, browser/cookie calls, return/raise and retry order
remain unchanged; no blanket claim covers the leaf extraction helpers.

`tests/test_legacy_parser_diagnostic_logs.py` extracts current source AST without
importing scraper/worker/Playwright. Synthetic cases assert fixed events, marker
omission, three launch attempts in Chromium/Firefox/WebKit order, final raise,
overview continuation and same original returned data. The completion selector
binds `browser.close() -> print -> return data`, avoiding the CAPTCHA print.
Only the launch helper runs as a complete extracted function; other cases are
isolated diagnostic branches, not a full card scrape. Audit hooks forbid
sockets/process spawning/SQLite.

Root authoritative `legacy-orchestration-causal-baseline-20260921.json` uses
immutable parent source in memory and final test bytes:4fail/0errors,122.006ms.
The earlier implementer probes were not persisted and are not the acceptance
record. No source reversal or capture overwrite occurred. A Darwin Git temp
warning is retained in the baseline stderr; do not call it clean-stderr proof.

`diagnostic-artifacts-final-20260921.json`:49pass +4subtests in1.51s,
1806.857ms wall; no stderr/timeout/truncation. Includes4legacy +11worker artifact
+34previous pure tests. Exact source/test hashes match independent frozen review:

- Parent scraper: `27aa6f7b2b0d9281f3389ce39c9bcc6f914411acad8170cc16b2cfa004767b2c`.
- Fixed scraper: `d26de3a46789974422455418e354904362672a1d99c98946ddac6cc04786bfa1`.
- Final test: `02c78388dcbf3729675a5f327cf3888b17e1e9dcded36b21651d10863386df76`.

Quality capture266.784ms checks13source hashes, scoped Ruff/diff and entire
legacy AST equality after normalizing print expressions and exception binding
names. This supports narrow source scope, not semantic equivalence of arbitrary
external helpers. Read-only independent review accepts **bounded FIX_PROVEN**
for these four sinks only and reconciles baseline/final hashes/capture limits.

Leaf extraction logs, invalid-URL exception text, wrapped returned errors,
retained logs/artifacts and deployed code remain unresolved. No production,
DB/provider, Docker, cleanup, push or deployment action. No readiness promotion.
