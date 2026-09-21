# Docker build-context exclusion review — 2026-09-21

## Scope

Read-only review of the narrow two-file change:

- `.dockerignore`: adds `tmp-google-docs-*`.
- `tests/test_docker_build_context_contract.py`: adds one assertion that the
  exact pattern remains present.

No Docker build, image inspection, provider access, application import,
database access, or cleanup was performed in this review.

## Result: PASS for the static configuration change; image proof remains blocked

The change is correctly scoped to the identified build-context admission path.
The production `Dockerfile` uses `COPY . .` at line 123, so a root-level
provider-response artifact matching `tmp-google-docs-*` would otherwise be in
the default filesystem context and available to that instruction.  The added
root `.dockerignore` pattern excludes that named artifact family from the
default context.

This matches Docker's documented behavior: patterns in a root `.dockerignore`
are removed from the build context before it is sent to the builder, and
`COPY` can access files in that context.  See [Docker build-context
documentation](https://docs.docker.com/build/concepts/context/#dockerignore-files).

The regression test parses non-comment `.dockerignore` lines and asserts the
exact required pattern.  It is coherent with the existing contract tests that
also preserve required runtime inputs, and does not widen exclusions to source,
scripts, migrations, or dependency inputs.

## Evidence reviewed

| Capture | Result | What it establishes |
| --- | --- | --- |
| `git-tree-docker-context-red-20260921.json` | exit 1; 1 failure, 2 passes | The new exact-pattern contract failed before the `.dockerignore` addition. |
| `git-tree-docker-context-green-20260921.json` | exit 0; 3 passes | The three static contract checks passed after the addition. |
| `git-tree-docker-context-quality-20260921.json` | exit 0 | Value-free quality projection confirms the 297,147-byte current artifact is byte-identical to the already-classified historical blob, is ignored and untracked, the baseline lacked the rule, the current file has it, and the broad copy is present; scoped Ruff also passed. |
| `git-tree-docker-context-adjacent-20260921.json` | exit 0; 14 static checks | Adjacent Docker/constraint contracts passed. |

All four captures are complete (not timed out or truncated).  They document
direct static checks (plus scoped Ruff), not an image build.

## Limits retained

The test proves only that the precise exclusion line stays in the root
`.dockerignore`; it does **not** prove that a Docker client/buildkit actually
excluded a concrete file, nor that an already-built image or its existing
layers are clean.  It also does not establish provider-side revocation or
removal of the local artifact.

Accordingly, the current image validation remains blocked: the required disk
floor is 10 GiB and the recorded available space is approximately 6.06 GiB.
Do not report existing layers as clean or the artifact as
verified absent from an image until a permitted Docker context/image inspection
has been completed.
