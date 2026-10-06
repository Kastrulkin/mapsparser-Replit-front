# Outreach chain UI audit — 2026-10-06

## User and job
A business owner selects a search group and advances unique companies through Companies → Letters → Sending → Replies. The first release focuses on Riderra, India → Phuket. Existing Operator, jobs, lead workstreams, campaigns and sending permissions remain the execution boundary.

## First layer
The same server presentation powers the pinned chat card and partnerships card. It identifies the selected group, actual current work, three distinct counters, actual credit charges, an estimate and one next action. Raw candidates never count toward the verified-company target. Manual selection remains separate from evidence.

Companies combines candidates and shortlist with All / Suitable / Needs decision / Excluded filters. Group and filters persist in URL. Lists filter by tenant and durable search membership before pagination; letters, queue and replies share that membership. Legacy stage URLs remain accepted.

## Second layer
Conditions, history, technical stage, exclusions and source evidence are expandable. Missing proof remains unverified. Existing confirmations and dispatch grants are preserved; draft preparation cannot grant sending. Native inbound replies are displayed without legacy reaction mutation controls.

## Recovery
Commands carry explicit selected group, including voice. No silent latest-group selection. Pending input remains visible and retries retain the command identity. Low balance links to the existing account subscription area, then requires an explicit resume. Cancelled searches only expose saved results. Failed letter jobs do not restart company discovery; uncertain external results do not offer replay.

## Evidence
49 focused backend tests passed; 26 frontend tests passed. Production read-only Riderra checkpoint: 42 raw, 0 verified, 41 requiring decision, 5 charged, available balance 0. Browser fixture uses these actual counters but does not execute providers or establish delivery. Integrated production-source typecheck and build passed. Browser validation also caught a filter update that changed the URL without updating the list; filters now maintain explicit state like existing stage/group selectors. Final wide/narrow evidence is recorded with the release.

## Release boundaries and remaining checks
No database schema changes, messages sent or credits replenished. A fresh paid real pilot is blocked by zero available balance. Provider text quality and delivery are not proven by fixtures. The existing English-only group-draft preparation restriction remains; expanding languages is separate from this UX change. Production frontend is built from the exact current calendar release snapshot with the outreach overlay, preserving unrelated content changes. Backend overlay preserves the separate public-offer-reader hotfix. Backups and source guards are required before partial deployment.
