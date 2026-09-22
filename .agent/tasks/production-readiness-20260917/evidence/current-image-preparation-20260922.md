# Current-image preparation — 22 September 2026

Entry revision: `33c9c7027d78a29d181d0347718563c22de2963a`.
The preceding user-facing flag explanation was NO_PROGRESS for implementation;
this continuation resumes the next unexecuted gate, not the completed stress run.
The full original goal remains ACTIVE and unproven.

## Bounded cleanup, batch 1 (completed)

Independent read-only review verified terminal process absence, synthetic-only
PostgreSQL shutdown/system catalog, no target/interior symlinks, same filesystem,
and all 22 durable stress evidence hashes. Only the following children of each
root were deleted: `baseline`, `baseline.tar`, `current`, `current.tar`, `data`.

- `/private/tmp/localos-five-stress.afdg9mej`
- `/private/tmp/localos-five-stress._nca2inu`

The ten explicit targets accounted for 1,025,245,184 allocated bytes (977.75 MiB).
The exact-path removal returned exit 0 in 4.817964208 seconds. Both root
directories and every evidence/helper/log/job/policy file remain: 4,904 KiB and
5,580 KiB respectively. Free space increased from `df -h` 6.5 GiB to 7.4 GiB;
the subsequent `df -kP` reading was 7,798,420 KiB available.

These were generated Git exports/archives and stopped disposable synthetic
clusters, not user databases. There is no trash copy; exports can be regenerated
from Git and synthetic data from the test fixture. No Docker resource was removed.

## Bounded cleanup, batch 2 (completed)

Nine independently reviewed exact targets were removed (exit 0):

- `/private/tmp/localos-readiness-20260921.hfLYPi/source`
- `/private/tmp/localos-front-ratchet.FLczSS/source`
- `/private/tmp/localos-browser-errors.gtS5JG/source`
- `/private/tmp/localos-browser-errors.gtS5JG/writable`
- `/private/tmp/localos-current-full-v10.BYwJr6/source`
- `/private/tmp/localos-current-full-v10.BYwJr6/source-d0ef4ce8.tar`
- `/private/tmp/localos-current-full-v10.BYwJr6/source.tar`
- `/private/tmp/localos-current-full-aB5f/source`
- `/private/tmp/localos-audit-browsers-20260922`

Durable manifests passed for frontend modules (16 artifacts), browser errors (4),
d0ef backend (17), preceding offline aggregate (7), and every capture in the
isolated hflypi manifest. The prohibited untracked candidate was pathname-absent
from the five exports; its content was not inspected. No active file, mapping,
browser, DB or writer handle referenced the targets. An obsolete read-only search
had candidate names in its arguments but no target descriptors: it was left
untouched, with possible ENOENT in its obsolete output accepted as harmless.

Allocated total was 3,293,608 KiB, but APFS shared clones reduced actual recovery.
Free space after removal was 9,390,816 KiB (`df -h`: 9.0 GiB), still below the
10 GiB build start floor. **No Docker build had run at that checkpoint**. Parent directories,
durable/private results, Python environment, protected a387 source and dependency
support remain. Browser-cache binaries are regenerable by downloading again.
Nonexistent frontend `/temp` and its distinct, unrequested `/tmp` were excluded.

## Bounded cleanup, batches 3–4 (completed)

Independent terminal-process/open-file and durable-manifest verification passed
before deleting five additional synthetic PostgreSQL `data` directories only:
`localos-services55-pg.i5c9as8l`, `localos-content-perf.cuey0qa9`,
`localos-content-perf.6nnlw66l`, `localos-content-perf.vrennm6e` and
`localos-content-perf.pm7ku04l`, all under `/private/tmp/`. Their parent evidence
and logs remain. Allocated total 303,243,264 bytes; removal exit 0 in 0.477859 s.

Three unused generated cache directories under
`/private/tmp/localos-readiness-20260921.hfLYPi/native/` were separately verified
(no symlinks, special files or open descriptors) and removed: `ms-playwright`,
`npm-cache`, `tmp`. Allocated total 283,328,512 bytes; removal exit 0 in 0.997225584 s.
The sibling `venv` and `evidence` directories are explicitly preserved.

The old capability `source` and `testdeps` trees were **not deleted**: Docker's
Virtualization VM still holds actual read-only file descriptors on them. No VM,
container or user application was stopped. Free space after batches 3–4 was
9,983,524 KiB (9.5 GiB), still below the start floor.

## Browser-cache batch (completed)

Metadata inventory found generated browser caches, not missing user documents.
The user-authorized cleanup is narrowed to closed regular hash-named HTTP/JS/WASM
cache entries older than one hour in three exact Yandex cache-data directories.
Browser remains open; cookies, logins, profile, history, tabs and local/site
storage are outside the allowlist. Cache misses may trigger fresh downloads.

Private `cache_cleanup.py` SHA256
`f809a78bf09066c559a9587e838ddf24c156b40b94a581fff1027a41f1bfa43c`
passed Ruff and independent review. Metadata-only plan: 30,951 entries,
1,003,102,208 allocated bytes, SHA256
`42cce8ce659b830dc0274d9fd47b5c5b08e027223d9734645939b260d32757e2`.
Execution rechecks open descriptors and file identity, skips changed entries,
uses no-follow directory handles, and preserves indexes and directory structure.
The expected concurrent cache-read race is limited to a disposable cache miss.
Named execution handle `audit-cache-cleanup-sj9dlo` completed in 11,773.424 ms,
exit 0: all 30,951 planned cache entries removed, no changed/open entries skipped.
Free space immediately afterwards: 11,240,230,912 bytes (10.47 GiB). Raw command,
plan and result remain in the private profile; no file content was read.
Cache deletion has no trash copy; entries are regenerated by subsequent requests.

## Current build preparation (not execution proof)

Private controller:
`/private/tmp/localos-current-image-20260922.SJ9dlO/build_current.py`, SHA256
`611e739530d819b028285cf5aaf4a39e0660767a4603990abd0b0599cc4646e4`.
Target: clean Git archive of entry revision, canonical Dockerfile, ARM64,
Playwright browser enabled, normal layer cache allowed, fresh labelled image.
Independent pre-execution review and targeted Ruff pass. Start floor is 10 GiB
before and after export; live floor is 2 GiB. Build subsequently started in
`audit-current-image-sj9dlo`; inspect its existing handle/result, never restart
because observation expires. The clean archive SHA256 is
`16c923cedffa1de742f4be28c0b32c2a5a989da03fa0ee2cc97f6647ee9cbf7f`:
6,536 files, 148,362,997 bytes, source manifest
`eafa0240d0219baf7b0e94433c8971fad76e11bc9ff3f09b03fb63d0a6fcfc1c`.
The terminal build now passes: capture182.501915s/controller177.067s, exit0;
immutable image `sha256:f5f8970b270d7b74b96e2b188cbfd471477a5a5655d9eb57bf007d45c96f59d6`,
ARM64, user `localos:localos`, owner/revision labels exact. Source manifest and
pre-existing Docker containers/volumes/networks unchanged; owned processes clean,
no cleanup signals/errors. Free10,886,569,984bytes at actual build start and
7,664,631,808bytes at finish. Offline three-check smoke also passes in5.067507s,
all exit0/noOOM, all temporary containers removed. Independent terminal review
PASS. The 17 hash-bound raw artifacts are now in `current-image-20260922/`.
Fresh PostgreSQL/web/worker/full-CI/security verification is still outstanding.

Read-only Docker inventory: 4 images, 23 containers, 20 volumes; build cache
4.131 GB with only 40.96 kB reported reclaimable. Existing image/volume counts
do not authorize pruning. The old `99849935` image stays available for its
unresolved image-security work; current source/runtime environments are retained.

Foreign tracked diff SHA256 remains
`3c70e23be24b8c80af60a3823344b4952d0bf736b2e49a655762c16838bf1ffe`.
Restricted OAuth candidate and native finance picker are not accessed.
