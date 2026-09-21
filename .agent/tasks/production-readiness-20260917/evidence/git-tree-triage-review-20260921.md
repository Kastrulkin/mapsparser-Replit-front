# Tree-only findings triage — independent bounded review (2026-09-21)

## Scope and result

**BOUNDED ACCEPTED for value-free finding-to-source mapping and context collection; final classification remains pending.** This is an evidence-method review, not a credential-validity, revocation, production-data, or overall-readiness conclusion.

I reviewed only the redacted captures named below and did not inspect private blob contents, request a URI/key, run a scanner, execute the application/tests, or perform database, network, Git, or source changes.

## Mapping evidence accepted

- `git-tree-context-binding-compact-20260921.json` completed successfully without stdout/stderr truncation. Its 42 rows each have one mapped candidate (`matched_rows: 42`) derived from the scanner's redacted `Match` prefix/suffix at the reported source line; candidate values are withheld.
- `git-tree-json-context-compact-20260921.json` also completed without truncation and records an exact-line binding plus source SHA-256 per finding. The earlier non-compact context and JSON captures were truncated; they are retained as history but are not a basis for this conclusion.
- The compact captures preserve source location/shape/context, not a credential identity or usability determination. In particular, redacted JSON keys (`<key>`), shape predicates, and scanner rule hits cannot by themselves establish that a value is a secret, which system accepts it, or whether it remains live.

## Context-specific assessment

- Findings 1–10 are structurally bound to historical Google Docs `imageProperties.contentUri` material. The cited Google Docs reference describes this as a bearer URI with a default 30-minute lifetime. That supports triaging them as historical bearer-capable resource-URI material, rather than assuming either a generic API key or a false positive. It does **not** establish that any captured URI was valid, accessible, unexpired, or unrevoked; no URI was requested.
- For tree finding 14, the AST captures prove an `IMPORT_KEY` string assignment at the matched historical line and prove it reaches the fifth positional argument of `import_report`; the trace also shows separate historical metadata uses. The current-source observation that the fifth argument is named `idempotency_key` is not sufficient to assign the historical call's semantics. The imported function's formal signature must be captured from the same historical revision/blob lineage before classifying this finding. Until then, label it **CANDIDATE — historical signature pending**, not a proven credential or a proven benign identifier.
- JSON context that points to `hashes` is useful negative/alternative context, but redacted keys and value-free scalar shape still require the final classifier's explicit, reproducible rule before dispositioning individual findings.

## Required final-classifier guardrails

1. Use only the complete compact captures for the 42-to-42 mapping claim and retain their exit/truncation fields.
2. State the field/path evidence separately from credential type, validity, exposure impact, and remediation priority.
3. For finding 14, bind the callee definition and fifth formal parameter in the corresponding historical source before using the current signature as corroboration.
4. Keep all emitted evidence value-free; do not fetch, test, or otherwise validate candidate material.

## Limits

No raw value, private blob, live endpoint, external provider, or historical runtime was inspected by this review. The compact mapping shows coverage of the 42 selected tree findings only; it neither resolves the previously recorded broader history/tree coverage gap nor supports AC6 or an overall PASS.

## Addendum — definitive access and digest-contract captures

The following completed, non-truncated captures resolve two previously pending *source-context* questions. They do not test live access or validity.

- `git-tree-access-contract-20260921.json` binds each of findings 1–10 to the exact `contentUri` field of an HTTPS `*.googleusercontent.com` URI. The redacted finding is exactly that URI's sole `key` query value (one distinct value across the ten repeated locations), not the complete URI. Together with the documented bearer-URI contract, this justifies classifying the ten hits as **one repeated historical Google Docs image-resource bearer key**, rather than ten independent API keys or a generic string false-positive. `image_access_not_tested: true` remains decisive: expiry, revocation, authorization scope, and present accessibility are unproven.
- The same capture follows tree finding 14 to `src/services/prospecting_research_service.py` at historical tree `2632efa57452d9de3739ba6f93f4ea563c3457d7`. The parsed `import_report` definition has `idempotency_key` as its fifth parameter and contains both an idempotency-key duplicate lookup and import-ledger insert. Its SHA-256 is explicitly different from current source. This resolves the earlier signature dependency: the matched historical `IMPORT_KEY` is **NO_BUG_PROVEN as a credential candidate / a historical idempotency identifier**, not a proven secret. That classification says nothing about any unrelated identifier semantics or current source state.
- `git-tree-digest-proof-20260921.json` is a useful retained partial attempt: checking only roots available there matched 8 of the 25 selected digest-shaped findings. It must not be used to call the other 17 unmatched.
- `git-tree-digest-history-proof-20260921.json` supplies the required wider frozen history pass. It completed with no truncation, walks the exact 35 frozen commit tips for eight bounded source paths, hashes 216 historical source blobs (24,221,599 bytes in memory), and obtains exact SHA-256 equality for all 25 selected digest-shaped findings (13 and 16–39). This is sufficient to classify those 25 as **historical source-content digests, not credential values** within the frozen history scope.

### Residual boundaries after this addendum

The evidence remains value-free and does not inspect raw candidates. The 25 digest disposition depends on the listed eight code paths and the frozen 35-tip reachable history; it is not an assertion about arbitrary repository objects, unselected findings, present deployment, or live secret validity. Six other tree finding IDs still await the separate final classifier/sidecar, so this review remains a bounded triage validation rather than a complete-tree or readiness PASS.

## Final sidecar reconciliation

`git-tree-triage-20260921.json` is consistent with the reviewed compact, access-contract, digest-history, and independent non-digest captures:

- All 42 tree rows now have a bounded disposition: 25 historical source digests, one historical import/idempotency identifier, two test fixtures, three reservation idempotency fixtures, ten historical Docs image-access URI components sharing one query value, and one deliberately retained `UNKNOWN` (row 11). `tree_unreviewed: 0` therefore means every tree row was *looked at*; it does not mean every tree row was cleared.
- `git-tree-nondigest-proof-verified-20260921.json` completed (exit 0, no timeout/truncation) and independently supports the five non-secret fixture dispositions: rows 12 and 15 are test fixtures, and 40–42 are typed `idempotency_key` fixture fields. The separate six-row review leaves row 11 UNKNOWN because value-free context cannot safely decide the historical documentation-prose candidate.
- The sidecar's arithmetic is sound: 31 non-secret rows + 10 historical resource-URI components + 1 UNKNOWN = 42; remaining 692 = 691 unreviewed history findings + tree row 11. The latest task ledger and immutable verdict retain AC6 and overall status as FAIL.

This is a **bounded accepted classification ledger**, not existing-image hygiene or security clearance. In particular, the ten URI components have not been fetched or verified for validity, expiry, revocation, access scope, or current presence; the 691 history candidates and the graph-versus-scanner membership gap remain. The newly documented Docker context exclusion is separately statically reviewed evidence and does not alter these conclusions or substitute for an image/layer check.

## Staged authored-prose false positives (pending final scan)

The retained initial staged precommit capture correctly stopped on two `generic-api-key` hits. Its value-free diagnosis binds them to the exact 332,884-byte staged diff and two authored documentation/evidence locations. The first prose-proof attempt is retained as a non-proof: its fixed guessed text did not bind either redacted scanner target and is not used for classification.

The replacement `git-tree-staged-prose-verified-20260921.json` completed in 105.462 ms with no truncation and proves, without emitting either candidate, that both scanner targets exactly equal constructed authored-English phrases in their respective documented contexts. Both therefore have the narrow classification **NON_SECRET_AUTHORED_PROSE**. The stated rewording/spaced replacement and the still-running final strict staged scan are intentionally outside this conclusion: this note does not claim the replacement scan passed, a scanner-rule change, a finding-count promotion, or any change to the preserved 692 unresolved count, AC6, or overall FAIL.
