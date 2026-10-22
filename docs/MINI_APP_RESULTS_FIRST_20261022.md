# Mini app: saved results first

Status: available in the shared Telegram/MAX interface. Telegram browser acceptance performed; real MAX acceptance still requires a configured bot and client access.

## Entry behavior

- Partnerships opens the latest saved group with letters, with companies and their readable letters together. Imported legacy records are grouped by source/file and date when no search-run identifier exists; this is explicitly described in History. Existing search identifiers separate launches.
- The default contact filter excludes companies with saved contact/reply/conversion history. Approval alone is not evidence of sending. Missing LocalOS history does not prove that no communication happened outside LocalOS.
- History opens earlier groups without changing or deleting the current result. Letters without a matching visible lead remain in a separate saved-letter group. An explicit browser-local default is labeled “Открывать здесь по умолчанию”; it is not a server-wide setting.
- Content opens a saved usable plan: prefer ready texts/publications, a plan covering the current period, active/approved status, then creation time. Empty, running, failed and archived plans are not automatically selected. Explicit post links are respected.
- Existing content-plan list/detail APIs provide plan history and full selected-plan data. An archived plan can be read from history without making it current. Existing API list limits still apply. With no plan, source analysis and company information remain directly available before starting generation.
- Readable results contain no editing fields, generation or send controls. Editing, new searches and new plans require separate entry. Existing previews, approvals, permissions and send boundaries remain intact.

## Validation

34 focused frontend cases cover result grouping, legacy Flask RFC timestamps, current-plan selection, archive browsing, linked posts, scope isolation, revoked access, transient failures, edit/save protection and existing partnership actions. Production-based frontend build passed. Dates are parsed before comparison rather than ordered by weekday text.

Live Telegram pass: current imported group and saved letter; older group and return; current saved content plan, older plan and return; explicit editing entry/exit; cancelled new-plan setup. No new generation, approval, delivery or client content update was performed.

Partial frontend deployment uses source and index guards, retains prior assets, and verifies the running container index. No migration, schedule change or service restart is required. Private screenshots and client material are excluded from this document and Git publication.
