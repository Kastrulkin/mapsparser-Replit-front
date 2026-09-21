# Authenticated read-only UI observation — 21 September 2026

Observed through the user's existing Codex in-app browser tab, approximately
03:26–03:32 UTC. Local source HEAD at the end of this observation:
`bd487501dd22733f92fa5cce80766ead60a554ec`. The deployed revision was **not**
established and must not be inferred from this local commit.

## Scope and observed outcomes

- The existing `/dashboard/today` page was authenticated with the visible
  SuperAdmin role. Current work and decision sections rendered.
- Sidebar navigation to `/dashboard/operator` loaded existing request history.
  The composer stayed empty and Send was disabled. No message was submitted.
- Sidebar navigation to exact `/dashboard/agents` (no query string) completed
  loading, showing ten existing tasks and the selected task's overview.
- Outer Scenario and Settings tabs opened. No field was edited, no Save,
  activation, preview, run, connector, approval or publication control was used.
- Returned to the selected task's Overview and closed the sidebar. The existing
  tab remains on `/dashboard/agents`; no logout, reload or second login.
- Two console inspections returned empty arrays for the tool's captured warning
  and error entries (limits 30 and 50). This is not network-status, server-log or
  exhaustive console-coverage proof.

Source-only route review established the frontend mount paths for Operator and
query-free Agents use GET requests. Today was inspected in place: a fresh Today
mount can claim a stored lead journey, and a `journey_action` query can post
telemetry, so neither path was deliberately exercised. Backend GET handlers and
incidental server/session telemetry were not audited by this browser pass.

## Findings and limitations

1. Mixed Spanish, English and Russian system chrome remains visible on the
   deployed pages (existing UX-LOCALE-07). Raw business content is not expected
   to be translated. No deployment of local locale changes is claimed.
2. **REPRODUCED UI discrepancy (local fix later verified separately):** the same selected
   task's Scenario shows `18:00 · Europe/Moscow`; Settings immediately shows a
   time input of `09:00` with the same timezone. Only tab navigation occurred.
   Local source inspection found separate version-contract and legacy-metadata
   readers. The save endpoints create a new candidate, not an immediate active
   schedule change; no live save was attempted. Track as UX-AGENT-SCHEDULE-01.
3. The drawer remained open after route navigation, and an explicit native
   accessibility toggle closed it. An earlier Playwright toggle observation and
   an accordion role mismatch are tool-interaction limitations, not established
   product defects. No overlay-blocking finding is made.

This is a three-route observation in one SuperAdmin session, not a full demo,
tenant/access-control test, mutation test, browser matrix, current-build test,
backend integration proof or production-readiness acceptance. Existing whole
FAIL, native aggregate/restore authority and image/release gates remain open.
No production write, send, payment, migration, cleanup or deployment was
explicitly invoked. Private history/content and raw browser output are not
copied into this artifact.
