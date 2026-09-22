# Commit-only a387 full-backend profile (preparation only)

This profile was prepared from `git archive a38720ce3530783caf59f6515a00baa1c532ce01`.
No collection, test, database, Docker, provider, network, or production action
was run while preparing it.

## Inputs

- Archive: `source-a38720ce.tar`, SHA-256 `54aa49449522b5aec428e0b314d72016e938e740967dc3b706877b15e3cb4e77`.
- Extracted source: 6,469 regular files, 126,524,264 bytes.
- Extraction uses the local umask: 6,364 archive files0664 become0644 and
  105 archive files0775 become0755. Content and Git executable bits match;
  group-write is intentionally removed, not restored. Freeze binds the exact
  extracted modes thereafter. Do not claim full Unix-mode equality to the tar.
- Runner: `run_current_full_a387.py`, SHA-256 `056c47fc84df9b5e0b1e2c8de6c2ec7c3742f544ca0a0afe121c4c4a0ac225d3`.
- Policy: `policy-a387.sb`, SHA-256 `70285c3cbf4d027c08bb95a8d818efb47e578a3a58961e11915b5eda27b24e80`.
- Ownership helper: SHA-256 `4f16b6c343223717dcf3b5bdbf86ff9159594b33fa92d744527891188c4c227b`.

The archive path manifest and extracted tree both exclude the restricted OAuth
test path. This was checked by path presence only; its workspace content was
not read or copied. The archive member list has no absolute or traversal entries
and no symlink entries.

## Deliberate delta from accepted v10 profile

The runner is a mechanical root/ref/archive/output rebinding to a387 plus one
safe callback field: `warning_categories` counts only warning class names. It
retains the accepted freeze/control/full flow, safe failure frames, 8 OS
controls, 9 pure controls, process ownership, timeouts and 5/2 GiB disk floors.
The policy differs only in the three source/writable root paths required by the
new private profile.

## Proposed execution commands (review required first)

```sh
tmux new-session -s audit-a387-freeze '/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python -B /private/tmp/localos-current-full-a387-0iwMmh/run_current_full_a387.py freeze'
tmux new-session -s audit-a387-control '/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python -B /private/tmp/localos-current-full-a387-0iwMmh/run_current_full_a387.py control'
tmux new-session -s audit-a387-full '/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python -B /private/tmp/localos-current-full-a387-0iwMmh/run_current_full_a387.py full'
```
