# README Git workflow safety review — 21 September 2026

## Scope and method

Independent read-only source/evidence review of the Git-workflow documentation
change attributed to parent `81e67435`. Inspected the current README Git section
(lines 626–652), `tests/test_readme_git_workflow.py`, and the retained focused
RED/GREEN captures. No tests, Git commands, Git configuration, credential
lookup, application import, database, Docker, or network activity was run.

## Verdict

**BOUNDED ACCEPTED.** The copyable README workflow now removes the unsafe
recommendations observed by the retained RED capture and preserves the required
human review and publication-authority boundaries.

- The local sequence obtains branch/status context, limits staging to an
  explicit `path/to/file`, and places both `git diff --cached --check` and the
  complete staged diff before `git commit` (README lines 631–637). The prose
  explicitly says to inspect the whole staged diff, including already-staged
  files (line 640).
- The access guidance recommends already-configured SSH or an HTTPS credential
  manager backed by protected OS storage, forbids changing global settings
  automatically, and forbids token/password URLs, arguments, examples, logs,
  and reports (lines 644–646). It explicitly warns that the `store` helper is
  unencrypted and says not to retrieve saved credentials for diagnosis. The
  linked Git references are appropriate to those two statements:
  `gitcredentials` for helper options and `git-credential-store` for the
  plaintext-storage warning.
- Push is separately authorized only after agreement on the current branch and
  `origin`; `git push --set-upstream origin HEAD` does not hardcode `main` or
  `master`, and the text denies that a local commit authorizes push, merge, or
  deploy (lines 648–652).
- The retained RED capture is causal documentation evidence, not an assertion
  of an actual compromise: 5 failures / 1 pass, exit 1, no timeout. It detects
  a token-bearing HTTPS URL, `credential.helper store`, hardcoded `main`, broad
  `git add .`, and missing staged review. The unchanged direct-stdlib GREEN
  invocation (`python -I -S -B`) records 6 passes, exit 0, no timeout or
  truncation.

## Test adequacy and limitations

The focused test realistically parses the Markdown section's copyable `git`
commands with `shlex`, then asserts absence of credential-bearing HTTP(S) URLs,
`credential.helper store`, broad staging forms, and hardcoded main/master
pushes; it also asserts both staged review commands occur before commit. This
is appropriate for preventing regressions to the observed unsafe examples.

It does **not** prove that a developer's existing credential helper is secure,
that OS keychain access works, that an arbitrary prose sentence outside the
parsed command forms is safe, or that no credential was ever exposed. In
particular, the helper test only examines `git config credential.helper` command
examples; the README's explicit prose prohibition on `store` is therefore an
important independent source safeguard. The test does not execute Git or make
any claim of remediation of historic credential exposure, remote permissions,
push success, merge safety, or deployment authorization.

No application, runtime, production, or whole-project readiness conclusion
follows from this documentation-only package.

## Final quality and ledger reconciliation

**ACCEPTED, bounded.** `readme-git-safety-quality-20260921.json` exits 0 in
2,690.392 ms without timeout or truncation. It records isolated Ruff success
for the new test, syntax-only `bash -n` parsing of exactly two README bash
blocks (not their execution), a clean diff check, and byte-identical README
content outside the replaced Git section. It also records SHA-256 values for
the README and focused test; the package ledger reports those two input hashes
as matching.

The two retained Darwin/Git temporary-directory fallback warnings are nonfatal
and are explicitly preserved. Current task evidence and the newest package
references agree that `SEC-DOC-GIT-01` is documentation-only `FIX_PROVEN`, the
previous UI finding was reconciled into the backlog rather than retested here,
and no application source changed after GREEN.

This reconciliation finds no new inconsistency. It preserves the stated
acceptance boundary: AC1–AC9 and AC11 remain FAIL, AC10 alone is the current
documentation-consistency PASS, and `verdict.json` remains the immutable
historical FAIL snapshot. The nine foreign worktree paths, native
aggregate/restore permission limits, and all non-documentation gates remain
outside this package.
