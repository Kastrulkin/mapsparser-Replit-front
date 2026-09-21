# Renewed cache cleanup — 21 September

User requested audit resume and safe cache cleanup. Goal controller reports
active; no new goal or automation created. Prior cache cleanup was not replayed.

## Removed, with recoverability

- Six exact inactive `~/.npm/_npx` child directories, listed in the raw command
  capture. `stat` confirmed directories, `lsof +D` returned no open files.
  Allocated size106248KiB before,0after. Exit0 in1037.483ms, no stderr.
  These are ephemeral package downloads; future npx use downloads them again.
- Only Puccinialin's cached `stable-x86_64-apple-darwin` toolchain, using its
  own rustup uninstall command with explicit cache-only RUSTUP_HOME/CARGO_HOME.
  No open files, no PATH rustc/cargo, no global ~/.cargo or ~/.rustup setup,
  and no project Rust configuration were found. Cache size579704KiB before,
  57768after; exact toolchain path absent, bootstrap/settings/registry retained.
  Exit0 in482.687ms. The command warns that this cache's default toolchain was
  removed: future use of these cache-local Rust tools requires reinstalling it.
  This warning is preserved, not treated as a global system Rust removal.

Combined allocated deletion628184KiB (~0.599GiB), not an assertion of exact
filesystem free-space gain. Free-space samples5143880KiB before and5758540KiB
after (~5.49GiB) also reflect unrelated concurrent activity.

Raw captures and SHA256:

- cache-npx-cleanup-20260921.json:
  22cad3dc4e36a2c3c0bef1e526d6d098be5cb0ce240dc2f32e780c8e71e65fe1
- cache-puccinialin-cleanup-20260921.json:
  7a5e5c5998fd1e0838bf4aa3fda85cdeacff50c62bf35f6dc9360018aa977f90

Reinstall only if later needed (not executed):

```sh
env -i PATH=/usr/bin:/bin RUSTUP_HOME=/Users/alexdemyanov/Library/Caches/puccinialin/rustup CARGO_HOME=/Users/alexdemyanov/Library/Caches/puccinialin/cargo /Users/alexdemyanov/Library/Caches/puccinialin/cargo/bin/rustup toolchain install stable-x86_64-apple-darwin --profile minimal
```

## Retained / pending

Codex app cache ~1GiB and Yandex browser cache ~0.93GiB have live open files;
neither app was closed or its cache changed. Codex runtime, task history,
attachments, project dependencies, active frozen hfLYPi environment and all
Docker images/containers/volumes were retained during this pass.

All large BuildKit records are shared, so no global prune was attempted.
Old Sep17–18 task-owned synthetic proof containers still retain old images.
Their provenance is confirmed by labels and the existing audit runbook, not
merely stopped status. Removing these exact completed containers+images while
retaining every volume might reclaim ~4.9GB of Docker unique layers; actual
host recovery can differ. A separate user approval question is pending. Do not
remove them or silently rewrite the current lane's29-container baseline before
that decision. Current hfLYPi, active LocalOS/Riderra and ambiguous containers
are explicitly excluded. No Docker mutation occurred in this cleanup.

## Audit checkpoint

05c9c83e archives364 policy/content backend passes and frontend NOT_REPRODUCED
targeted repeats. f137edb5 locally fixes four legacy parser diagnostic surfaces:
4causal RED to4GREEN plus7adjacent. Both match independently accepted staged
diffs, pass strict secret scans and normal hooks;13foreign paths remain intact.
No push/deploy/production/DB change. Remaining aggregate/frontend/security/
browser/performance/CI and historical whole-goal FAIL remain. Native5GiB start /
2GiB live and full Docker10GiB floors are unchanged.
