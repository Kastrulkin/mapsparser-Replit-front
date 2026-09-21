# Tree-only triage and Docker context correction — 21 September

Parent `08c383e14de9b555c7ea4591319ccf4c88905cf7`; frozen scan inputs remain
`7cf0cd24`. Original objective reread; previous login-only turn was no progress.
This package advances security evidence and fixes one concrete packaging gap.

## Triage result

`git-tree-triage-20260921.json` is an additive sidecar; the original scanner
report, base metadata and historical verdict are not rewritten. All 42 tree
rows have exact source-line bindings. Dispositions:

- 25 source SHA-256 values: exact equality to 216 historical blobs across eight
  source paths rooted in the frozen 35 commit tips. The earlier roots-only
  attempt matched only 8/25 and remains partial, not contradictory evidence.
- One import idempotency identifier: AST call trace plus the callee's fifth
  parameter and duplicate/import-ledger SQL in the same historical tree.
- Two static callback-test fixtures and three typed reservation idempotency
  fields; exact scanner-value binding, not just equal string lengths.
- Ten Google Docs image-resource URI components: one repeated query value,
  not ten independent API keys. Each is bound to `contentUri` and its `key`
  parameter. These are retained as historical access material, not false positives.
- Tree row 11 stays UNKNOWN. Alongside 691 untouched history candidates,
  **692 findings remain unresolved** (previously 733 unreviewed).

Google documents `contentUri` as access-bearing image URLs with a default
30-minute lifetime. This does not prove that these particular URLs expired,
were public, or were revoked. No URL/key was requested or tested.
[Google Docs ImageProperties](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents#ImageProperties).

## SEC-BUILD-CONTEXT-02

The current ignored/untracked provider response is byte-identical to the
classified tree blob (297,147 bytes). Git exclusion did not protect Docker's
filesystem context: `Dockerfile:123` uses `COPY . .`, while `.dockerignore`
lacked the artifact-family rule. Add only `tmp-google-docs-*` plus one static
regression assertion; no provider file is edited or deleted. Docker documents
root ignore patterns as removal from the context before transfer to the builder.
[Docker build context](https://docs.docker.com/build/concepts/context/#dockerignore-files).

Direct stdlib checks, with no pytest conftest or application imports: RED
1 fail/2 pass in 103.137 ms; GREEN 3 pass in 44.845 ms; six-file adjacent suite
14 pass in 62.345 ms; scoped Ruff and artifact/source predicates pass in
220.146 ms. Independent review accepts the configuration/static proof only.
Actual Docker context, fresh image/layers and existing images were not checked.
This is a local source correction, not image-level FIX_PROVEN or a release.

## Retained unsuccessful or partial diagnostics

The coordinate-based value-shape probe mapped only 1/42 rows. Prefix/suffix
binding and exact-line JSON context replace it for classification. The original
context-binding and JSON-context captures have truncated stdout; their compact
successors are complete. The first non-digest proof used a nonexistent `/usr/bin/rg`
and exited 1; the corrected explicit installed path exits 0. None of these
diagnostic limitations is a product failure or silently converted into a pass.

The first staged-package scan exited 1 with two matches in authored report prose,
so its precommit capture is retained as failed. The diagnostic records the exact
332,884-byte staged-diff hash; fixed-phrase predicates then prove both matches
non-secret. An initial guessed-prose probe did not bind either phrase and is not
classification evidence. The verified probe does. The two sentences were spaced
and reworded for clarity; no scanner rule or suppression was changed. Final
package verification must still pass after including these captures.

Verified precommit: exit 0 in 4,735.097 ms; 39 owned files, 355,707 staged bytes,
22 captures reconciled, 10 input hashes and nine private blob IDs verified.
Strict Gitleaks reports no findings and the known resource query value is absent
from the staged patch. Ten URI occurrences represent eight distinct full URLs
sharing one query value, not one identical URL. The original statuses/verdict
and nine excluded foreign paths are unchanged. Nonfatal Darwin temp fallback
warnings remain in stderr. The final 40-file package includes this capture and
is checked once more before the local commit.

The separate count review establishes different metrics: the frozen Git graph
contains 3,117 commits; Gitleaks reports 3,095 commits reaching fragment
processing. Exact membership of the 22-count difference remains unproven.
No new full scan, fetch, history rewrite or cleanup was performed.

## Continuation

Resume value-free triage of the 691 history candidates, prioritizing captured
provider/debug responses; resolve tree row 11 with stronger source predicates.
Do not repeat the completed 42-row mapping or use API shape as blanket safety.
Native aggregate/restore preparation still needs renewed permission; Mac
6,352,832 KiB (~6.06 GiB) is below the 10 GiB image floor. Existing privileged
credential revocation, prior unsafe-reset INCONCLUSIVE effects, nine foreign
paths, original AC statuses and overall FAIL are unchanged. No database,
production, provider, Docker, cleanup, push or deploy action occurred.
