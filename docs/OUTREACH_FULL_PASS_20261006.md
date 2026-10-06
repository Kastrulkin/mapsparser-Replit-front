# Outreach implementation and verification

## Changes
Reuse existing groups, Operator approvals, enrichment records, versioned campaigns, the native send queue and reply synchronization. Display collection separately from audience qualification. Draft-only jobs generate through the existing campaign preview with public evidence and a reviewed offer, with one email touch. Campaign text is canonical in the letter list. Manual review binds text, recipient, sender and version before native queue admission. Low balance pauses a resumable draft job. Generating drafts never sends messages.

Saved groups can review changed quantity, offer and final preparation stage, then resume under the same ID. Prior conditions and expenses remain intact. Changing audience or automatic sending requires separate review. Search-only conditions do not change silently. No new database tables.

## Verification
292 focused backend tests plus 13 existing async/review regression tests, 20 frontend tests, type checking and builds passed. Six fixture browser scenarios passed on desktop and mobile. Read-only deployed API and browser checks verified group status, substeps, expenses, server-side filters and pagination on desktop and mobile. Release checks verified source integrity, runtime imports and publicly served assets. Temporary verification access was closed.

## Remaining acceptance gates
Tests and read-only checks do not establish model text quality, real recipient delivery or reply matching. The real pilot still needs sufficient balance, reviewed preparation conditions, qualified leads, evidence-based letters, a separate send confirmation and a control reply round trip. Do not treat the full end-to-end pilot as complete until those checks pass. No automated followups are included.
