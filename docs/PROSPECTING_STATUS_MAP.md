# Prospecting Lead Status Map

Last updated: 2026-04-13

This document records the current lead status strings used by the prospecting flow, where they appear, and how they are expected to behave.

## Primary lead statuses (prospectingleads.status)

| Status | Meaning | Used in | Notes |
| --- | --- | --- | --- |
| `new` | Newly saved lead, not yet shortlisted | UI Inbox tab; API default on save/import | Default for search/import/manual links |
| `shortlist_approved` | Approved into shortlist (ready for contact prep) | UI Shortlist tab; `/api/admin/prospecting/lead/<id>/shortlist` | Shown as “В shortlist” |
| `shortlist_rejected` | Rejected during shortlist review | UI Rejected tab; same shortlist endpoint | Treated as rejected |
| `deferred` | Deferred for later work | UI Deferred tab; status update endpoint | Used for “Отложить” |
| `selected_for_outreach` | Moved from shortlist into contact stage | API `/api/admin/prospecting/lead/<id>/select-for-outreach` | Used to gate audit + message prep |
| `channel_selected` | Outreach channel chosen | API `/api/admin/prospecting/lead/<id>/channel` | Required before draft generation |
| `queued_for_send` | Enqueued into send queue | API batch creation / queue | Used by dispatcher |
| `sent` | Sent (or delivered) | Queue delivery updates | UI Sent tab |
| `delivered` | Delivered (provider confirmed) | Queue delivery updates | UI Sent tab |
| `responded` | Response received | UI Sent tab | Outcome / pipeline analytics |
| `converted` | Final positive conversion | UI Sent tab | Outcome / pipeline analytics |
| `rejected` | Hard rejected (legacy) | UI Rejected tab | Treated as rejected |

## Search job statuses (prospectingsearchjobs.status)

| Status | Meaning |
| --- | --- |
| `queued` | Job enqueued |
| `running` | Job in progress |
| `completed` | Finished with results |
| `failed` | Job failed |

## Outreach queue delivery statuses (prospectingoutreachqueue.delivery_status)

| Status | Meaning |
| --- | --- |
| `queued` | Waiting for dispatch |
| `sending` | In send attempt |
| `retry` | Waiting for retry |
| `sent` | Sent (provider accepted) |
| `delivered` | Delivered |
| `failed` | Failed |

## Where statuses are used (code)

- Backend constants: `src/api/admin_prospecting.py`
  - `SHORTLIST_APPROVED`, `SHORTLIST_REJECTED`, `SELECTED_FOR_OUTREACH`, `CHANNEL_SELECTED`, `QUEUED_FOR_SEND`
- Frontend UI logic: `frontend/src/components/ProspectingManagement.tsx`
  - Tab filters, badge labels, sent groupings

## Notes

- `shortlist_approved` is the canonical shortlist state in current flow.
- `selected_for_outreach` + `channel_selected` are used for Contact/Draft stages.
- `rejected` is legacy; should be treated the same as `shortlist_rejected`.
- `deferred` is used for “Отложить” and has optional `deferred_reason`/`deferred_until` fields.
