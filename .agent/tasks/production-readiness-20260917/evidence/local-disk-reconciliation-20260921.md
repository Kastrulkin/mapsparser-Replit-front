# Local disk reconciliation — 21 September 2026

Read-only inspection only; no data, cache, image, volume or evidence was deleted.
This does not override the earlier native aggregate/restore preparation denial.

Root `df -k . /private/tmp` observations fluctuated from5,169,456KiB free to
943,272KiB, then3,246,448KiB and3,543,804KiB. `sysctl vm.swapusage` reported
6144MiB total/5262.31MiB used swap at one observation. Docker.raw reported228GiB
logical size but20,536,620KiB allocated via `du -sk`; logical size is not consumed
host space. These snapshots establish pressure/fluctuation, not its cause.
Other local audit tmux panes were present; they were not restarted or stopped.

Independent read-only inventory covered `/private/tmp/localos-*` and generated/
dependency directories in this repository. Long `du` commands ran in named tmux
sessions; observations existed in pane scrollback, not a frozen output file.
Representative commands:

```sh
df -k . /private/tmp
find /private/tmp -maxdepth 1 -iname 'localos-*' -print0 | xargs -0 -n1 du -sk
du -sk frontend/node_modules venv .agent
```

Largest potentially reproducible components at that observation:

| Path/component | Allocated KiB | Restriction |
| --- | ---: | --- |
| Project frontend/node_modules |896288|Current offline test/build dependency tree|
| Project venv |567048|Shared project environment; ownership/use not cleared|
| /private/tmp/localos-backend-deps-v2-20260920.xYc0jK/venv |639788|Verified133-distribution environment; restore would require dependencies|
| /private/tmp/localos-mixed-frontend-20260920.Bm3ckx/browsers |202460|Retained browser runtime/evidence dependency|
| /private/tmp/localos-frontend-current-20260920.GtHPOV |232760|Source archive/build with validation provenance; not all disposable|
| /private/tmp/localos-backend-full-20260920.XoKy4o |197704|Source/archive/bytecode with retained runtime provenance|

The broadest candidate group is only about2.6GiB, not a verified safe deletion
set or a5GiB remedy. Unique `.agent` evidence, scanner inventories, operational
`outputs`, databases and backups are not cache and must be retained. No proposal
to delete dependency trees, private evidence or Docker.raw follows from this
inventory. Docker/image work still requires10GiB; native aggregate also requires
renewed scoped authority and its reviewed start prerequisites.

Only bounded frontend regressions were started after a fresh check confirmed
at least2GiB free. The initial regression's CPU loop was a test-harness bug,
separately documented; it does not explain earlier disk movement.
