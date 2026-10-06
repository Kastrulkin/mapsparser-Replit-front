# Full outreach pass — 6 October 2026

## Changes
Existing group, Operator approvals, enrichment records, versioned campaigns, native sending queue and reply synchronization are reused. Collection is displayed separately from audience qualification. Draft-only jobs generate through the existing campaign preview with public evidence and a reviewed offer; one email touch only. Campaign text is canonical in the letter list. Manual review binds text, recipient, sender, version and schedule before native campaign queue admission. Replies and permission changes are rechecked; low balance pauses a resumable draft job. No sending occurs while generating drafts.

Saved groups can review changed quantity, offer and final preparation stage, then resume under the same ID. Prior conditions and charges are retained. Changing audience or automatic sending requires separate review. Search-only conditions never change silently.

## Verification
292 focused backend tests, 20 frontend tests, typecheck and build passed. Six fixture browser scenarios passed on 1440px and 360px. Production read-only queries confirm 42 raw results, 41 collected records, 40 selected contacts, 0 audience-qualified companies, 5 previously charged credits and 0 available balance. Reply sync is connected with a successful recent check. Fixtures do not prove provider text quality or delivery.

## Production compatibility
The production AI authorization guard in outreach_campaign_service and public-offer reader in outreach_routes were reconciled rather than overwritten. Their existing supporting modules are captured unchanged so the reconciled code has its dependencies in Git. No schema migrations or balance changes.

## Pilot gate
The real three-company pilot is not complete: zero balance blocks paid qualification and generation. Review changed conditions first; collect three qualified Indian agencies selling Phuket, generate evidence-based English first contacts and show exact recipients, sender, subjects and texts. Queue only after the user's separate send confirmation. Prepare a separate control email to a user-specified address other than the sender; confirm sending, receive their reply and verify deduplication. No automatic followups.
