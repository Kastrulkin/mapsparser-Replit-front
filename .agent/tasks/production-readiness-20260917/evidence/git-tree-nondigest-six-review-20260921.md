# Value-free tree-scanner review: six non-digest rows — 2026-09-21

## Scope and method

Independent, source-data-only classification of tree-scanner rows 11, 12, 15, 40, 41, and 42. The private redacted report and the corresponding tree-only blobs were read programmatically only to emit structural booleans, AST context, field paths, types, and lengths. No raw source line, match, secret, URI, object identifier, or scanner value is reproduced here. No application import, test, runtime, database, network, Docker, or deployment action occurred.

All six report rows are `generic-api-key` rows with a fully redacted secret field and a single redaction marker in the match field. The exact source-line number supplied by the scanner was available for each row.

## Classifications

| Scanner row | Classification | Value-free proof |
| --- | --- | --- |
| 11 | `UNKNOWN` | The source is historical documentation prose and the reported target length is 25. It is not a standalone identifier token under the safe structural tokenizer. Without emitting or reconstructing the redacted target, this review cannot prove it is a fixture or a credential. |
| 12 | `NON_SECRET_TEST_FIXTURE` | The exact historical line contains one unique 18-character identifier-shaped token. Passing that token to a literal stdin-only current-source search returns only a test module. Its AST contains the same constant exclusively in `test_callback_dispatch_signature_and_dedupe_guard`; it is not imported or obtained from runtime state. |
| 15 | `NON_SECRET_TEST_FIXTURE` | Same deterministic proof as row 12: one unique 18-character token, literal stdin-only current-source match only in the same test module, and AST ownership exclusively in `test_callback_dispatch_signature_and_dedupe_guard`. |
| 40 | `NON_SECRET_IDEMPOTENCY_FIXTURE` | The exact line is parseable JSON. Its nested reservation-result idempotency field is a string of the reported 24-character length, while the surrounding record has typed reservation/preflight fields. This is a test baseline record, not a provider credential field. |
| 41 | `NON_SECRET_IDEMPOTENCY_FIXTURE` | Same JSON-schema and nested idempotency-field proof as row 40. |
| 42 | `NON_SECRET_IDEMPOTENCY_FIXTURE` | Same JSON-schema and nested idempotency-field proof as row 40. |

## Limitations

Row 11 remains deliberately unresolved: source context alone is insufficient under the value-free rule. The classifications for rows 12, 15, and 40–42 establish only that these historic tree values are fixture/idempotency identifiers in their recorded context; they do not certify the rest of the scanner inventory or any current deployment state.
