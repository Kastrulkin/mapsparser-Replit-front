# Current canonical image — 22 September 2026

**Build and offline image smoke PASS; full runtime/CI/security are not yet proved.**

Source: clean `git archive 33c9c7027d78a29d181d0347718563c22de2963a`,
6,536 files / 148,362,997 bytes; archive SHA256
`16c923cedffa1de742f4be28c0b32c2a5a989da03fa0ee2cc97f6647ee9cbf7f`.
Manifest before/after:
`eafa0240d0219baf7b0e94433c8971fad76e11bc9ff3f09b03fb63d0a6fcfc1c`.
No untracked/dirty source overlay; the restricted OAuth candidate is absent.

Canonical ARM64 Docker build with Chromium enabled completed in 182.501915 s
(controller 177.067 s), exit 0. Normal Docker layer cache was allowed; this is
not a no-cache build. New immutable image:
`sha256:f5f8970b270d7b74b96e2b188cbfd471477a5a5655d9eb57bf007d45c96f59d6`.
Owner `production-readiness-20260917-sj9dlo`, exact source revision label,
user `localos:localos`; three birth-observed CLI processes cleanly exited without
cleanup signals. Existing container/volume/network inventories match exactly.

Both frontend builds completed (29.00 s dashboard, 8.10 s public Vite build).
BuildKit emitted four name-based `SecretsUsedInArgOrEnv` warnings for the ARG/ENV
pairs `VITE_JOURNEY_POST_AUTH_REDIRECT_ENABLED` and
`VITE_BROWSER_COOKIE_AUTH_ENABLED`. Their defaults are literal `false`, not
credential values. This classification does not replace a current-image secret
scan or close the older image206/history-security work. pip root-install and
third-party annotation warnings remain visible in the retained build log.
The byte-exact raw log retains 19 whitespace-only progress suffixes flagged by
`git diff --check`; these are evidence formatting, not source-code errors. Do
not normalize the log and break its execution-bound SHA256. Other staged files
pass the whitespace check.

Offline smoke: 5.067507 s capture / 4.923 s controller, all three checks exit 0:

- `python -m pip check`.
- UID10001, expected writable directories, private-file exclusion and Chromium
  launch/static DOM assertion.
- Canonical transitive asset verification for dashboard and public builds.

Each fresh image-ID-pinned container had no network, mounts or exposed ports;
capabilities dropped, no-new-privileges, 768 MiB/256 PID caps. No OOM, forced stop
or cleanup failure; all three exact owned containers removed. Original Docker
state before/after is unchanged. This is not browser E2E or provider evidence.

The safe cleanup that enabled the build is separately detailed in
`../current-image-preparation-20260922.md`; free space6.5→10.47GiB before export,
10,886,569,984 bytes at actual build start and7,664,631,808 bytes after build.
Private per-entry browser-cache plan/result remain under the profile; their
SHA-bound counts were independently reconciled. No profile/cookies/user DBs
or pre-existing Docker resources were deleted.

Next: fresh isolated synthetic PostgreSQL16 migration/schema/startup/HTTP and
worker signal proof on this immutable image; full CI integration, current-image
security, broader browser/demo and final whole-diff review remain open. No
production mutation, real provider request, push or deployment is claimed.
