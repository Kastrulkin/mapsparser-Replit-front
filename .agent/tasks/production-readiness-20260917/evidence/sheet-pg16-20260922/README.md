# Sheets queue/recovery native PostgreSQL evidence

First current-parent run: 16 exact nodes / 48 lifecycle phases passed, outer
9.875424 s / exit 0. All writes target a newly owned synthetic database and
provider adapters are test doubles. This does not exercise live Google Sheets.

The source is an immutable d0ef archive bridged to parent `3ce90e4a`. The executor
specifically bridges to committed HEAD, **not** its existing dirty working copy;
the excluded working-copy hash is recorded. Other eight inputs match current
working copies. Do not claim a full dirty-worktree or production result.

Executed sources are verbatim `.py.txt` evidence. Private absolute paths, parent
HEAD and completed session names are historical, not instructions to rerun.
The controller derives from the PG51 controller with the same bounded native
lifecycle and isolation policy. Independent review accepted its exact profile,
source boundary, selectors, runtime outcomes and cleanup.

The generated DB was dropped, owned cluster stopped and process registries
empty. The stopped cluster directory retains system-database files; it is not
empty or recursively deleted. Restricted OAuth/native-picker tests were absent.
