# LocalOS author payload fingerprint release

Status: production runtime already deployed and verified; this commit records
the previously uncommitted, provenance-backed release chain.

## Purpose

Author campaign payloads now evaluate freshness with the same creator bridge
fingerprint used by preview, approval, and dispatch. This prevents an unchanged
creator invitation from appearing stale merely because the generic research
fingerprint path was used by the campaign payload endpoint.

The creator lane remains fail-closed: missing or changed creator facts and an
outdated generation contract still require regeneration. Non-author campaigns
continue to use the existing research fingerprint path.

## Git provenance

- Base: `9aa3815d8cb0e6fa6acb69fe2c464329bcfbeb02`
- Branch: `codex/author-payload-fingerprint`
- No reachable local or current remote commit contained
  `current_outreach_source_fact_fingerprint` or `is_localos_author_lane`.
- The combined delta therefore records the verified author gate, creator
  outreach bridge, creator invitation template, and final payload correction.
- The base already contains the current deployed email adapter, email reply
  service, and reply-sync receipt; those files are intentionally unchanged.

The cumulative files are backed by these exact release receipts:

- Author gate manifest:
  `/Users/alexdemyanov/.codex/visualizations/2026/08/05/019fd1f3-f2a4-7ea3-8741-0b54ffec3b7e/author-gate-release-20260907/MANIFEST.md`
- Creator bridge manifest and patches:
  `/Users/alexdemyanov/.codex/visualizations/2026/08/05/019fd1f3-f2a4-7ea3-8741-0b54ffec3b7e/creator-outreach-bridge-release-20260907/manifest.md`
- Creator invitation template receipt:
  `/Users/alexdemyanov/.codex/visualizations/2026/08/05/019fd1f3-f2a4-7ea3-8741-0b54ffec3b7e/creator-invitation-template-release-20260908.md`
- Final payload patch and isolated test receipt:
  `/private/tmp/localos-author-executor-20260908/author-payload.patch` and
  `/private/tmp/localos-author-executor-20260908/green.log`

## Runtime scope and hashes

| File | SHA-256 |
| --- | --- |
| `src/services/outreach_campaign_service.py` | `66601c7cbffe2e9244532b807eb7416dcaa603f29588954719cbf199416209a3` |
| `src/services/outreach_safety_service.py` | `7152b32567d6a5f3a0fc8205e6630ff17a59c3c1cb924ed9c2c4988919434817` |
| `src/services/outreach_template_service.py` | `f5b573761658d31eb9fd8b257841e7c54d5d600b4946350c772f48a46c647dcd` |
| `src/services/outreach_dispatch_service.py` | `715e531e1d57de1f47b84614a7685db6fa5d23af90326d31f2be9a2befd46547` |
| `src/worker.py` | `b2ed18be60073bcfc9e79cc8ddcabfaac806386d41520bfcca956919dac3ce43` |
| `src/api/outreach_campaign_api.py` | `86f3d35f6feaf488d327e55dd18dd9c3a95e0e3f6552a16950becaebdf675317` |

There is no schema migration and no frontend change.

## Prior production proof

- Author gate release: focused suite `28 passed`, with two Docker-backed
  PostgreSQL fixture skips; production read-only regression passed.
- Creator bridge release: combined suite `233 passed, 2 skipped`; production
  read-only previews retained exact contact, evidence, and bridge fingerprints.
- Creator invitation template release: combined suite `236 passed, 2 skipped`;
  initial previews remained blocked until an authenticated saved-draft review.
- Final payload correction: isolated artifact suite `281 passed`, with two
  integration tests deselected.
- Each production release used hash guards, restarted only affected Docker
  services, passed import/health checks, and caused no approval, queue addition,
  or outbound send during verification.

The earlier deployment artifact also verified that the operational legacy
sender stops before `send_all_now` without the trusted author reply preflight.
That untracked operational script is intentionally excluded from this Git
release. The clean Git suite checks the canonical native safety, campaign,
dispatch, API, and worker paths.

## Clean Git verification

Run from this checkout with the repository itself as the only import source:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/src:$PWD" \
python -m pytest -q -p no:cacheprovider -m 'not integration' \
  tests/test_author_daily_gate.py \
  tests/test_founder_outreach_campaigns.py \
  tests/test_outreach_campaign_history_payload.py \
  tests/test_campaign_payload_creator_fingerprint.py \
  tests/test_outreach_safety_learning.py \
  tests/test_outreach_template_service.py \
  tests/test_outreach_v2_partnership_intelligence.py
```

Result: `281 passed, 2 deselected in 1.56s` (exit `0`). The raw receipt is
`/private/tmp/localos-author-executor-20260908/git-release-tests.log`.

The release does not approve or send creator outreach. External sends continue
to require the existing exact-review and manual approval boundary.
