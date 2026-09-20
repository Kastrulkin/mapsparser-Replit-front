# Git onboarding safety — 21 September 2026

Parent: `81e674353a47160cde366e0b10b6b3e0c12abc08`.
Finding: **SEC-DOC-GIT-01**, P2 before production/technical handoff.

The original objective was reread through EOF and current Git/disk state checked.
Previous goal turn was progress (committed UI fix/full frontend proof), not a
blocked or waiting turn. This package changes only the README Git instructions,
a read-only documentation regression test, and readiness evidence/records.

## Contract, cause and risk

The old README Git section (parent lines 626–639) recommended a plaintext
credential helper, a credential-bearing HTTPS push URL, broad staging and a
hardcoded main-branch push without staged review. A developer following these
instructions could persist a token without encryption or expose it in command
arguments/logs, and inadvertently include unrelated changes. Likelihood depends
on following that workflow; credential impact can be high, affected scope is the
developer's repository access, and source confidence is high. Actual compromise
or prior use of the instructions is **not proven**.

Primary contract: Git documents that its store helper saves credentials without
encryption ([credential-store](https://git-scm.com/docs/git-credential-store))
and lists OS-backed alternatives ([gitcredentials](https://git-scm.com/docs/gitcredentials)).
Both were read on this date; no credentials or project data were sent. The
project's original task separately requires preserving foreign edits and explicit
publication approval. These contracts support a documentation correction, not
a claim that Git itself is vulnerable.

## Correction and verification

Use explicit file paths, current-branch inspection and full staged diff/check
before local commit. Separate optional publication under explicit approval,
using an existing SSH or secure HTTPS helper and the agreed origin/current
branch. No helper/configuration/credentials were inspected, saved or changed;
no push occurred. Everything outside this README section is byte-identical to
the parent. Fix effort/risk/blast radius: small/low/documentation only.

`tests/test_readme_git_workflow.py` reads the named section, tokenizes copyable
Git examples and checks six bounded contracts. It never executes those commands.
Direct Python `-I -S -B` invocation uses only stdlib, no site packages, pytest
configuration, application imports, DB, network, Docker or native preparation.

| Evidence | Actual result | Capture ms |
| --- | --- | ---: |
| readme-git-safety-red-20260921.json |5 failures /1 pass; exit1; unsafe examples and missing staged checks |51.081|
| readme-git-safety-green-20260921.json |Same6 checks pass; exit0 |49.120|
| readme-git-safety-quality-20260921.json |Scoped isolated Ruff,2 bash blocks parsed with `bash -n` (not run), section boundary/hash and diff checks pass |2690.392|
| readme-git-safety-precommit-20260921.json |15owned staged files; strict redacted Gitleaks clean for46118bytes;2source hashes and original statuses/historical verdict match;9foreign excluded |3690.533|

All captures are complete with no timeout. Quality retains nonfatal Git/Darwin
temporary-directory fallback warnings. The quality capture binds README and
the test to hashes. Independent source/evidence review is BOUNDED ACCEPTED in
`readme-git-safety-review-20260921.md`.

Precommit capture checks the original15-file stage before this capture and its
result notes are added. The final local commit package contains16owned files;
its exact staged inventory and complete diff must be checked again before commit.

Classification: **FIX_PROVEN for these documentation instructions**. Tests do
not implement a complete Markdown/shell/credential scanner; prose, alternate
command spellings, existing Git configuration, key revocation and real GitHub
authentication are outside proof. No application change means the prior 809-test
frontend result retains its scope; it was not rerun or claimed as new evidence.

## Original goal and next gate

The missing `UX-DRAFT-REVIEW-ADMISSION-01` row is now reconciled into backlog02,
with its actual commit and bounded proof, not a new test result. All original
acceptance statuses and historical verdict remain unchanged: whole FAIL.
Nine foreign paths stay excluded. Native aggregate/restore prep still awaits
renewed explicit permission; Mac free space 6,598,736 KiB (~6.29 GiB) is below
the 10 GiB image floor. Historical unsafe-reset effects remain INCONCLUSIVE.

The next distinct safe evidence step is a frozen-ref, strict redacted all-refs
history scan and triage; current source plus branch delta do not cover other
refs. It cannot establish historical credential revocation, image/log cleanliness
or full AC6. Do not repeat completed frontend/source reviews or retry denied
native preparation. No production/provider/data/cleanup/push/deploy action here.
