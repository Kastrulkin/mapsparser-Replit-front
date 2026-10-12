# Content fact contract: production rollout, 12 October 2026

Runtime release commit: `33d093492471f424d3e2eb7d0df1db474e53973e`.
Push confirmed to `origin/codex/openclaw-reuse-20261012`.

Exactly one canonical runtime file was patched:
`/opt/seo-app/src/services/content_plan_service.py`.
No frontend, Compose, provider/model settings, DB schema/data, schedules, messages
or receipt writes were part of this release. No GigaChat call was made.

The fresh production file was used rather than replacing it with the older Git
tree. Its non-target AST nodes were verified unchanged by the installer. Shared
fact sources retain business ID, service record ID, origin and observation date;
writer and validator read the same snapshot. No diploma-specific ban remains.
Markdown fences are stripped without repairing invalid JSON. Creative remarks
are non-blocking warnings, not factual failures.

Installed/live-container SHA256:
`531b15407dcef125dbc6de6ad746386dd5bf38fec509d7c3fe830fad2f8bd256`.

Rollback copy:
`/opt/seo-app/backups/content-facts-20261012T100532Z/content_plan_service.py`.
Deployment evidence:
`/opt/seo-app/backups/content-facts-release-20261012/rollout.log`.

Checks:

- Seven local regression tests passed; no provider calls.
- PostgreSQL checks before and after rollout ran in read-only transactions.
  Real service descriptions including diploma and the branch address reached the
  common snapshot (29 sources). Unknown source and unsupported price rejected;
  JSON fences normalized; malformed JSON not repaired; imagery not blocked.
- Live module import and digest confirmed after installation.
- Only `app`, `worker`, `operator-worker` restarted by this rollout. All nine
  containers were up, worker logs showed normal startup.
- Local HTTP root and content route returned 200.
- Schedule fingerprint remained identical:
  `5a6eb30c195287775002e5115e0891a58dd6fc2707d4c0fe1384f167c65afdf4`.
- Current `scripts/check_outreach_navigation_release.py frontend/dist` passed.

Concurrency caveat: the first attempt stopped before modifying runtime because
another task staged a contact-intelligence change. That task subsequently
restarted the services; the second attempt observed no unactivated source files.
The frontend fingerprint changed during this rollout while the independent
business-knowledge task was deploying/republishing frontend. Therefore the
whole-frontend equality check is not reported as passed. This release did not
write frontend assets, did not revert that task, and separately verified the
current navigation gate. No whole-site/browser-flow or paid generation result
is claimed from these checks.

Semantic limitation: the shared source contract fixes drift and provenance; it
does not prove every sentence merely because a model lists valid source IDs.
Human review remains applicable. Original posts, approvals and receipts retained.
