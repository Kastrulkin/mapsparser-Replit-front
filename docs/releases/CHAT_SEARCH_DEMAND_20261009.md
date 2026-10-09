# Operator reviews and search demand — 2026-10-09

Status: beta. Shared web/Telegram implementation in `src/services/operator_core.py`.

- Reading a network parent expands only to businesses the current actor can read. Reviews include branch, source, rating, text and stored update date. Queries remain bounded (500 reviews / 200 module items); partial results are explicitly marked.
- `seo.search_demand` reads saved Wordstat data through the existing keyword collector, honors exclusions/negative keywords, and filters by the business services. It never refreshes Wordstat. Snapshot dates are shown; growth/newness and source-frequency region are unknown without period history/provider metadata. Business city is not a frequency-region claim.
- Service-name previews receive filtered saved keyword evidence. A compound request may read both services and keywords before preparing a preview. Reading alone cannot terminate that compound request early. Applying the preview retains the existing separate approval boundary; external cards are not written.
- Review-refresh cost/availability requests show a read-only plan. Asking for the date of the last update is a read request, not consent to launch paid parsing.

Regression coverage: authorized vs denied network branches, network review labels/freshness, irrelevant mask-show and pet-product keywords, historical-demand disclosure, multi-step preview, refresh preflight without launch, and last-update wording without paid refresh.

Limitations: no period-history comparison or automatic Wordstat refresh was added. Per-source frequency-region metadata is not inferred. Generated names still need human review for faithful service meaning.
