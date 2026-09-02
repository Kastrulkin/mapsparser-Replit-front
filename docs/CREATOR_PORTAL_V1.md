# Creator relationships and portal v1

Status: `beta`.

## Product boundary

- `creator_relationships` stores the platform-wide relationship stage independently of searches and client campaigns.
- `creator_contact_events` is the append-only delivery and reply ledger.
- A business sees only creators selected for its own campaigns. Creator contacts and LocalOS conversations are not returned to a business user.
- A creator account is invitation-only and is linked one-to-one with `creator_profiles`. It does not grant access to a business account.
- LocalOS creates an invite URL, but never sends it automatically.
- Only collaborations with `review_status = approved` are visible in the creator portal or eligible for notification.
- The shared `@LocalOspro_bot` only authenticates creators and opens approved offers. Decisions and messages stay in the portal.

## Lifecycle

Relationship stages:

`discovered` → `contact_ready` → `contacted` → `replied` → `interested | needs_details | declined | paid_only | invalid_contact | paused`.

Offer review:

`draft` → `needs_review` → `approved | rejected`.

Any creator response cancels pending reminder records for that creator. Notification delivery uses `creator_notification_outbox`, a unique `dedupe_key`, provider message IDs and bounded retries.

## Rollout flags

- `CREATOR_RELATIONSHIPS_ENABLED`
- `CREATOR_PORTAL_ENABLED`
- `CREATOR_BOT_ENABLED`

The portal remains closed without a valid invite even when all flags are enabled.

## Verification

1. Back up PostgreSQL.
2. Run `scripts/backfill_creator_relationships.py` without `--apply`.
3. Apply the Alembic migration.
4. Record newly verified email replies, then run the backfill with `--apply`.
5. Run `scripts/smoke_creator_portal.py` only against an explicitly disposable database whose name contains `creator_portal_test`.
6. Verify the relationship registry, email and Telegram account activation, approved-only offer visibility, role separation, and provider logs.
