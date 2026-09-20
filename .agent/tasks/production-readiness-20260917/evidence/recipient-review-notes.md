# Campaign recipient review — 20 September 2026

Parent `ca0c3d36`; finding `UX-CAMPAIGN-RECIPIENT-01`, P2, local bounded fix.
Owner/operator task: inspect the destination beside each message before
approving the campaign. The builder showed the message/channel/approval control
but no actual recipient. This is a review-information defect, not proof of an
unauthorized send. No production interaction occurred in this package.

## Minimal contract

- Saved campaign projection joins exactly `touch.contact_point_id` to the
  contact UUID and selects `normalized_value AS recipient`; the LEFT JOIN keeps
  historical touches with absent contacts visible. No fallback to another lead
  contact, no new query per touch, no schema or persistence change.
- Channel availability prefers the selected contact's normalized provider
  value, retaining its existing display-value fallback for legacy input objects.
  Generic preview copies it onto each touch; Riderra uses its binding-validated
  manifest recipient. Selection, permission and sender gates are unchanged.
- The UI renders only server `touch.recipient` as React text; absence warns.
  Existing saved-touch spread retains the field. Long values wrap; no new
  control, focus target, HTML sink, link or implicit approval/send is added.
- Approval hashes, provider dispatch, contact writers and capability flags are
  not changed. This is not an immutable contact snapshot migration.

## Reproduction and reconciliation

Backend `red.json` initially has five failures, including a non-causal fixture
failure: the creator bridge lacked preferred_contact and its existing identity
gate correctly returned no touches. Fixing only the synthetic bridge address
produced `red-causal.json`: five actual missing/incorrect-recipient failures
plus one passing history-identity control. The final RED adds the separate
Riderra preview path: six failures/one pass, 0.89s, capture1362.726ms.
`backend-green.json` runs seven focused cases and the explicit neighboring
selection together:288passes/1.42s, capture1936.259ms. All backend captures have
zero recorded DB/network/dotenv/child-process attempts. SQL is a projection-aware
fake, not native PostgreSQL execution.

Frontend first RED has five failures/one pass but truncated verbose DOM stderr.
`frontend-red-causal.json` repeats unchanged tests/source with DEBUG_PRINT_LIMIT
500: five recipient-text failures/one pass,9.40s/capture10794.223ms, untruncated.
`frontend-green.json`:6passes/4.76s/capture6216.942ms, empty stderr. Saved,
fresh-preview, missing recipient, escaped markup and resolved workstream
transition are covered. The latter is not a delayed-response race test.
Full suite, quality, build and integrity results are reconciled in COMMANDS.

Named localos-recipient-* tmux sessions, private arm64 Python/env-i/-I/-B,
disabled dotenv/plugin autoload/conftest/cache and the pre-import bootstrap
guard are used for backend. Node22 uses the existing no-egress-compatible.cjs
chain, envDir:false and frontend child cwd. These are process-local guards,
not proof of OS-level/native isolation. No test server or real provider starts.

## Two hypotheses rejected, not silently hardened

1. Same contact ID changing normalized recipient through supported writers:
   NO_BUG_PROVEN. `contact_intelligence_service.upsert_contact_points:965-1023`
   creates a new UUID and conflicts on `(lead_id, contact_type, normalized_value)`;
   its UPDATE changes display/provenance/status metadata, never normalized
   identity. The manual API normalizes and uses that writer
   (`contact_intelligence_routes:88-151`). The schema unique key is in
   `20260715_add_contact_intelligence.py:20-67`. Different normalized address
   therefore gets a different ID; an old touch remains on the old address.
   Raw-DB/future-writer mutation is defense-in-depth debt, not a demonstrated
   normal-flow approval bypass. Prior checkpoint wording is superseded.
2. Truthy non-booleans in sender capabilities: NO_BUG_PROVEN. Supported email,
   VK, Telegram and MAX writers generate boolean values; permission fields are
   BOOLEAN and corresponding update APIs reject non-booleans. Source references:
   outreach_email_adapter401-425; outreach_sender_service204-268,306-372,403-581;
   outreach_vk_adapter188-203,264-283; telegram_account_permissions_service116-151;
   outreach_campaign_api674-690,962-971; telegram_research_api1048-1069 (line
   numbers may shift with later additive edits). Manually corrupt JSON is not
   supported API reachability. No speculative capability-policy change added.

## Limits

Independent bounded review PASS is in recipient-review-review.md. No native
JOIN/lock/transaction, new-build browser/mobile/layout, real provider, current
full backend or whole-project readiness proof follows. Late async response
after a workstream change is a separate source candidate, not reproduced here.
Current read-only disk observation4,853,324KiB (~4.63GiB) is below the10GiB
Docker floor. Aggregate-v2 and restore denials persist, as do earlier unguarded
reset-run INCONCLUSIVE effects. Nine foreign paths stay excluded. No push,
deploy, database change, external send, Docker operation or cleanup.
