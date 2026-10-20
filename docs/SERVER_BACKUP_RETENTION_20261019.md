# Database backup retention cleanup — 2026-10-19

User explicitly authorized removal of obsolete archives/dumps and duplicates while retaining a current database backup, required rollback material and all working data.

## Result

- Available space at cleanup baseline: 2,860,822,528 bytes (~2.66 GiB).
- Available space after cleanup: 10,161,946,624 bytes (~9.46 GiB).
- Net filesystem increase: 7,301,124,096 bytes (~6.80 GiB).
- Five retired historical dumps total 8,760,354,307 logical bytes.
- Fresh compressed database dump: 1,557,164,437 bytes, mode 0600 in a 0700 directory.

## Preserved

- Fresh full PostgreSQL database archive: `/opt/seo-app/backups/retention-20261019/local-20261019.dump`.
- Previous recovery point: `/opt/seo-app/backups/outreach-cost-controls-20261016/database-complete.dump`.
- Existing September monthly SQL copy and `latest.sql.gz` name remain intact for compatibility.
- Current and previous EREVANTRANSFER release/rollback archives, all unique code/configuration archives and other required rollback material remain intact.
- Fresh and October 16 backup directories marked `.keep` for the existing named-backup pruning mechanism.

Both October 16 and fresh archives were fully decoded with `pg_restore --file=/dev/null`; fresh TOC and SHA256 saved. This validates archive readability, not a live database restoration. No production restore or database mutation was performed. Global role definitions saved separately using `--no-role-passwords`, without elevating privileges. Existing protected runtime configuration retains connection credentials. Private backup contents were not displayed.

## Retired

1. `data/backups/postgres/local_20260912_104901.sql.gz` — 1,687,229,205 bytes.
2. `data/backups/releases/business-knowledge-20261012/database.dump` — 2,065,170,551 bytes.
3. `release-backups/runtime-20260917.J1dT4n/database.dump` — 1,736,112,836 bytes.
4. `/opt/localos-recovery/production-drift-20260810_1545/deploy-backups/localos_before_growth_b3f32f6d_20260809.dump` — 1,578,105,549 bytes.
5. PostgreSQL-container `/tmp/before_conversion_plans_20260914.dump` — 1,693,736,166 bytes; a manual historical dump, not a PGDATA/WAL file.

The first obsolete September dump was retired only after fully validating the retained October 16 archive; remaining dumps were retired only after fresh backup completion, full read validation and checksum verification. Exact sizes, regular-file/header/link-count checks and SHA256 recorded before removal. Historical dump states at these retired checkpoints are no longer retained by these files; current and October 16 recovery points remain available.

Stale `data/backups/postgres/.latest.sql.gz.tmp` name was removed after proving it shared the same inode as the retained monthly/latest file. It reclaimed zero data blocks and was not double-counted.

## Safety / verification

- No production code, frontend, Docker image, Docker volume, media, active database data, schedule or publication changed.
- Ten services running; local app, Telegram control and MAX control HTTP 200; PostgreSQL SELECT 1 succeeded.
- EREVANTRANSFER rollback archives rechecked as present.
- An attempted off-host dump transfer was blocked by the safety reviewer and was not executed or bypassed. All backup work remained on the existing server.
- Fresh dump used a dedicated application name and a 1-GiB free-space cancellation guard. No reserve breach occurred.
- Initial globals export required unavailable password-table access; corrected to lower-privilege `--no-role-passwords` without repeating the database dump or granting access.
- Neighboring cleanup/deployment work coordinated and held during the operation.

Authoritative server evidence and checksums: `/opt/seo-app/backups/retention-20261019/report.json`, `fresh.sha256`, `fresh-contents.txt`, `fresh-validation.log`, `retired-*.sha256`, `retired-*.stat`, and execution logs. No ongoing cleanup job or cron was installed.

## Automated rotation added subsequently

The existing `localos-storage-maintenance.timer` is reused: daily 03:30 Moscow time with up to 15 minutes randomized delay. No second cron/scheduler is introduced. Its service timeout is explicitly one hour, umask 0077. Application containers and customer schedules do not need restarting.

`scripts/verified_backup_retention.py --apply` runs first in the maintenance entrypoint. A failure stops subsequent maintenance. The manual `scripts/postgres-backup.sh` entrypoint uses the same lock and backup store; `--preview` is read-only.

- Managed store: `/opt/seo-app/data/backups/verified`, directory 0700, files 0600.
- PostgreSQL custom archive with zstd level 6; roles exported without role passwords. Protected existing runtime configuration remains necessary for credentials.
- TOC, full native archive decode, SHA256 and a completion manifest are required before a snapshot is eligible for retention.
- Keep the latest two verified snapshots and, when the 5-GiB target permits, one additional weekly recovery point less than 28 days old. Per-file or store `.keep` prevents removal. The target never overrides minimum recovery points or pins; an over-target warning is recorded.
- Keep 3 GiB free; estimated dump size is checked before starting, then free space is monitored during writing. On failure, old verified snapshots remain. No pruning is performed to make room for a failed new backup.
- Rotation deletes only verified, unchanged regular dumps and their own sidecars in the marked managed store. Unknown files, invalid manifests, symlinks and unverified files are not cleanup candidates.
- Repeat runs on the same Moscow date reuse the verified daily snapshot; concurrent runs are locked out.
- Today's already validated Oct19 recovery point is seeded by a hardlink, not a duplicate 1.5-GB copy; its original protected path remains intact. Future managed snapshots are separate dated immutable files.
- Existing protected manual database backups, monthly recovery point and deployment rollback material remain outside this managed cap and are not removed by the new rotation. Arbitrary manual archives can still grow; this is not a total-host disk quota. Existing disk monitoring remains in place.
- No off-host replication is configured; a copy on this server does not protect against loss of the server itself.

Focused regression checks: `python3 -m pytest -q tests/test_verified_backup_retention.py tests/test_prune_postgres_backups.py tests/test_prune_named_database_backups.py` — 13 passed. Shell syntax checks passed. Archive decoding is not a test restoration into PostgreSQL.

Deployment evidence and previous scripts: `/opt/seo-app/backups/backup-rotation-20261019/`. Rollback: restore its `rollback/postgres-backup.sh` and `rollback/run_storage_maintenance.sh`, remove only the new service drop-in `backup-retention.conf`, reload systemd. Leave all snapshot files/manifests intact. The timer itself remains the preexisting timer.

Production acceptance on Oct19: seed and repeat both returned `status=verified`, `created_new_dump=false`, no warnings or removals. Latest managed archive `db-20261019T171559Z.dump`, 1,557,164,437 bytes; checksum equals the protected source archive. Both names have link count 2, so no duplicate data blocks were allocated. Next timer occurrence confirmed as Oct20 03:37:54 MSK. Available space 10,160,345,088 bytes (~9.46 GiB), ten services running and app HTTP 200. The full legacy maintenance tail was not manually invoked; the new canonical backup entrypoint was tested directly. First new scheduled dump remains a future run, not a claimed completed backup.

## SQL sidecar compatibility fix — 2026-10-20

The first scheduled run successfully created and validated the Oct20 snapshot. The legacy SQL compressor then renamed the managed role definitions to `.globals.sql.gz`; the next verified-store scan required an uncompressed sidecar and incorrectly rejected both snapshots. The dump contents and compressed roles were intact.

The compressor now excludes the managed verified store and role-definition sidecars (`*.globals.sql` / `globals.sql`). The verifier also accepts an already compressed roles file, requiring a regular nonsymlink file, nonempty decompressed contents and a successful complete gzip read including its checksum/trailer. Corrupt, truncated, empty and symlink sidecars remain ineligible and are preserved. Snapshot deletion handles the compressed sidecar explicitly; seed adoption supports the already compressed seed without rewriting it.

Regression evidence: the real maintenance entrypoint failed before the fix on isolated backup fixtures. After the fix, both plain and previously compressed cases complete the whole entrypoint twice: verify/reuse daily snapshot, retain minimum/weekly/pinned snapshots, retire only eligible obsolete fixtures, compress ordinary legacy SQL, run legacy pruning and debug retention, then rescan verified records. No database operation is permitted in this same-day fixture test. Compressed seed adoption and invalid gzip/symlink cases are also covered. The focused suite contains 20 passing tests; bash syntax checks pass. Archive readability is not a live PostgreSQL restoration test.

Production deployment replaced only `scripts/compress_sql_backups.sh` and `scripts/verified_backup_retention.py`, with guarded original hashes and saved previous scripts. All five maintenance stages were then executed in read-only preview: two verified snapshots, no warnings and no planned removals. No production `--apply`, backup creation, archive deletion, role import or database restore was used to test this fix. Managed-store inode/size/mtime inventory and combined service/timer configuration hashes remained identical before/after. No application restart or schedule change was performed by this deployment.

Deployment/rollback evidence: `/opt/seo-app/backups/backup-sidecar-fix-20261020/` (`rollback/`, `before-state.json`, `deployed.json`, `production-preview.log`, `verification.json`). Current backup files remain in their existing compressed/plain forms; the compatibility fix reads them in place. Last post-deployment disk measurement: 8,595,648,512 bytes free (about 8.0 GiB). The next unattended nightly cycle is not claimed completed by this daytime check.
