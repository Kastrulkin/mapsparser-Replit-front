# Outreach user-flow repair, 9 October 2026

These files reflect the deployed production source, which differs from main and from the earlier one-file universal-outreach branch. Deployment used the production snapshot plus the focused repair delta, not a checkout of this branch. No database writes, searches or sends were performed by deployment.

Fixes: blocked search preview returns a typed reason; group message filter applies before pagination; stale group responses are ignored; canonical letters no longer display projected legacy drafts; web-search readiness is read-only and does not route to Wordstat; generic profile workflows cannot claim to perform outreach.

Verification: 28 focused backend tests, 1 queue UI test, production frontend build. Five existing agent-run tests fail identically on the unmodified production baseline because fake cursors lack advisory-lock SQL handling. Full TypeScript baseline has existing errors; changed queue and continuation components introduce none.

External blockers remain: verified free search credentials and provider balance. This repair does not claim the full autonomous pilot is complete.
