# Platform outreach room currentness

## Result

`FIX_PROVEN`

Five existing LocalOS platform drafts are now recognised as current without regenerating their messages. No campaign was approved, queued, or sent.

## Reproduction

Two focused regression cases failed before the fix:

- a valid `sender_mode=localos` draft without `room_id` was reported as stale;
- `localos_sales` attempted to create a sales room in the recipient business scope through `lead_business_id`.

Command:

```bash
python3 -m pytest -q tests/test_outreach_batch_preparation.py tests/test_outreach_v2_partnership_intelligence.py
```

Before: `2 failed, 28 passed`.

## Root cause

`_campaign_is_current` required `room_id` for every sender mode. At the same time, `prepare_private_room` used `lead_business_id` as a fallback owner, although that ID belongs to the recipient for LocalOS sales and is not a valid LocalOS tenant boundary.

## Fix

- A LocalOS platform draft does not require a tenant-owned sales room.
- Business partnership drafts continue to require a room.
- `localos_sales` does not create a room owned by the recipient business.

The change does not alter message text, evidence, quality scores, approval state, scheduling, delivery queues, or provider calls.

## Verification

Targeted result: `30 passed`.

Broader outreach and sales-room regression result: `146 passed`.

Production checks:

- `app` and `worker` restarted successfully;
- `http://localhost:8000` returned `200 OK`;
- the live container contains the corrected conditions;
- read-only inventory returned `draft_current: 5` for all five affected workstreams;
- no AI generation or external dispatch was performed.

## Residual scope

Platform-owned digital rooms need a separate explicit platform-scope data model if LocalOS sales rooms are required later. This fix deliberately prevents tenant leakage and does not introduce a second pseudo-business or a schema migration.
