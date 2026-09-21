# Historical debug artifact producer review — 2026-09-21

## Scope and result

Read-only current-source review of the parser-interception and worker debug-bundle producers, their enablement/access boundaries, and the available redaction helper/tests. No historical value, raw provider response, cookie, HTML, URI, app import, test, database, Docker, provider, or network action was used.

**New actionable static candidate: `SEC-DEBUG-BUNDLE-01` (P1, conditional on explicit debug enablement).** This is not dynamically reproduced in this review.

## Reachable trigger and contract

`PARSER_DEBUG_BUNDLES_ENABLED` is parsed as an explicit truthy opt-in and defaults to `false` in [parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:571). The worker likewise creates a bundle only for a business-scoped queue item when that environment switch is enabled ([worker.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/worker.py:5615)). It then passes the bundle identity into the native parser alongside Yandex session cookies ([worker.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/worker.py:5745)).

With the flag enabled, a Yandex JSON response is written with `json.dump` before any field-level redaction ([parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:671)). Redirect/failure paths write browser page content verbatim ([parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:855), [parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:883)), and later bundle paths again write raw page HTML plus the final parser payload ([parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:1480), [parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:1526)).

Expected contract: an opt-in diagnostic bundle may retain only redacted, bounded diagnostic data; it must not durably persist provider-token/cookie-bearing JSON, redirect HTML, or credential-bearing request/final URLs.

Cause: the parser writes these raw browser/response values directly. Its in-memory interception record also includes request headers ([parser_interception.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/parser_interception.py:690)); while the current summary does not dump those headers, no shared serialization redaction boundary protects future/debug callers.

## Access and persistence boundary

- This is not enabled by default, and the reviewed Compose files do not set the opt-in flag.
- Once enabled, local Compose bind-mounts the same debug directory into both app and worker ([docker-compose.yml](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/docker-compose.yml:290), [docker-compose.yml](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/docker-compose.yml:579)); the release profile instead shares a named volume across application roles ([docker-compose.release.yml](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/docker-compose.release.yml:14)). Bundle naming embeds a business identifier but does not implement filesystem tenant authorization.
- No dedicated HTTP route serving arbitrary parser bundle files was found in the reviewed source. That does not remove host/container/operator access: the support helper accepts a business identifier and prints the leading page HTML ([show_last_debug_bundle.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/scripts/show_last_debug_bundle.py:44)). Retention cleanup is time-based, defaulting to seven days, not a confidentiality control ([prune_debug_data.sh](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/scripts/prune_debug_data.sh:6)).

## Existing redaction and coverage gap

`redact_sensitive_text` covers selected query/header/JSON field names ([sensitive_text.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/src/core/sensitive_text.py:9)) and has a focused synthetic unit assertion ([test_yandex_review_delta_sync.py](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO%20с%20Реплит%20на%20Курсоре/tests/test_yandex_review_delta_sync.py:107)). The parser debug write sites do not call it. Its reviewed pattern list also does not cover the two historically observed provider-specific field names or generic cookie/HTML scrubbing.

No parser debug-bundle regression was found that enables the flag with a temporary bundle directory and asserts that intercepted JSON, redirect HTML, canonical page HTML, payload, and URL files exclude synthetic sensitive markers.

## Smallest deterministic check

At the parser unit layer, use a fake page/response/context, a temporary debug directory, and the explicit opt-in. Include synthetic markers in: a response JSON provider-token field, request/final URLs, session cookies, and redirect HTML. Assert every produced artifact excludes every marker while preserving only approved structural diagnostics. Add a negative assertion that the opt-in disabled path produces no bundle. This test must avoid real browser/provider I/O.

## Relation to existing findings and limitations

`SEC-HISTORY-01` documents historical privileged/provider material retained in Git; it does not close this current raw-producer path. The evidence therefore records a new current-source candidate, not a claim that historical material remains valid or that any live runtime currently has debug bundles enabled.

This is static source evidence only. It cannot establish the actual environment value, filesystem ACLs, existing bundle contents, public reachability, or runtime provider response shape.
