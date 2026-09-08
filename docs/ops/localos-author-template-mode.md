# LocalOS: approved author invitations

The user authorized the exact `creator_invitation_name_only_v2` on 8 September
2026, including barter **or paid** work depending on the client. Only the verified
first name changes. Sender: `localosgo@gmail.com`. The limit is 150 unique authors
per Moscow calendar day, shared with manual and other author-channel activity.
This is not approval for company outreach or Riderra.

## One template decision, not one approval per recipient

- Read `GET /api/outreach/sender-accounts/{sender_id}/author-template-authorization`.
- A real authenticated platform superadmin can enable the exact manifest with
  `PATCH` on that route: `enabled: true` and `approved_template_sha256` returned
  by GET. `enabled: false` revokes it. Caller-supplied actor IDs are ignored.
- The authoritative decision is an append-only-by-application permission event
  in `outreach_sender_account_events`, not creator campaign constraints. It can
  also be recorded by an authorized server operator using
  `set_author_template_authorization`, naming the actual approving user and the
  actual decision reference. Never fabricate a browser session or review record.
- Prepare and save a single email first-touch draft with canonical creator
  evidence and `invitation_template: verified_name_v2`. Preview and save remain
  non-sending operations.
- Call `POST /api/outreach/campaigns/{campaign_id}/authorize-template`, or
  `approve_campaign_by_author_template` from the authorized project worker.
  This rechecks the live grant and exact renderer before enrolling the draft in
  the existing send queue. It does not require a per-message human approval.
- The existing worker checks history, replies, opt-outs, current evidence,
  sender access, fresh mailbox receipts and atomic daily admission before send.
  Revoked or changed grants stop queued work. Already in-flight provider requests
  cannot be recalled by revoking a grant.

## Integrity and operations

The dispatcher binds actual provider body, subject, recipient and sender to the
freshly validated queue/draft snapshot, not a previously loaded editable draft.
Changing the template definition, grant, recipient or draft requires preparation
again. Ordinary per-message manual-review paths remain unchanged.

Previous successful or uncertain first sends, including manual sends and legacy
creator records, block another first invitation across days and duplicate cards.
Replies are handled as ongoing conversations, never by the first-invitation mode.
Do not raise a cap to compensate for unavailable contacts or provider restrictions.

Do not mark a draft sent. After provider acceptance, record its actual message ID,
verify the Sent copy, reconcile CRM/YouGile and leave one next action. A technical
failure remains a recovery action, not a response follow-up.

## Regression checks

`tests/test_author_template_authorization.py` covers real actor requirements,
exact manifest/copy, revocation, scope, queue/draft mutation, dispatch snapshot
binding and all-time first-touch history. Existing author daily-gate, reply-sync,
campaign, sender and B2B tests remain required. No schema migration is needed.
