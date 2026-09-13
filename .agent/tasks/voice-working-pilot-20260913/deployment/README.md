# Production release deb0f637

The scripts document this specific release and its observed host hashes; they are
not general rerunnable migration/deployment commands. Do not run restore cleanup
or overwrite another release without a new review.

Backup retention: validated the custom-dump contents from September 11 and 13,
and gzip integrity of September 12. Removed only the four older database backup
files from September 5, 6, 8 and 9. Retained their code/rollback files. Freed about
6.4 GiB. Working containers, volumes and current application images were preserved.

Restore uses a dedicated network-isolated PostgreSQL 16/pgvector container,
512 MiB memory (raised to 900 MiB for index construction), low-priority CPU and a 1200 MiB disk-reserve guard. fsync/WAL tuning
applies only to the disposable restore database, never production.

After complete restore, migration rehearsal uses the actual server migration
lineage and the existing application image. Production code is a three-way merge
of 78dfdd98, deb0f637 and actual server files, checked again before write.

Live smoke records only harmless capability questions. Six HTTP/common-channel
paths are not evidence of a real Telegram client or physical mobile devices.
Temporary verification sessions are invalidated in finally.
