# Service Catalog Compression Plan

## Problem

Some map cards import too many service rows into LocalOS. The card stays technically complete, but the owner sees a long raw catalogue instead of a workable service structure. Organika is the current example: after the 2026-07-01 refresh it has 244 active parsed services, including many variants by gender, body zone, hair length, product volume, scar size, and seasonal offer wording.

## Goal

When a business has an overloaded service catalogue, LocalOS should analyze it and propose a shorter grouped version for manual approval. The system must not delete, merge, publish, or rewrite external services automatically.

## User Flow

1. Detect overload after map parsing or when opening the services tab.
2. Show a clear alert: "Много услуг: можно сократить и сгруппировать".
3. Generate a draft grouping with before/after counts.
4. Let the user review categories, merged rows, hidden duplicates, and kept exceptions.
5. Apply only after explicit approval.
6. Keep the original parsed rows for audit and rollback.

## Detection Rules

- `active_services_count >= 80`: show recommendation.
- `active_services_count >= 150`: mark as high-priority cleanup.
- Repeated base names with variants by ml, cm, gender, zone, age, hair length, or package size are merge candidates.
- Rows starting with promo markers such as "Сезонное предложение" should be proposed as promotions or highlighted offers, not ordinary catalogue rows.
- Categories with more than 25 active rows should be reviewed for subgroups.

## Suggested Data Model

Add a draft table such as `service_catalog_compression_requests`:

- `id`
- `business_id`
- `user_id`
- `status`: `draft_ready`, `needs_review`, `approved`, `applied`, `rejected`
- `source_card_id`
- `before_count`
- `after_count`
- `groups_json`
- `diff_json`
- `created_at`
- `updated_at`

Add item-level rows or a JSON detail structure with:

- source service ids
- proposed category
- proposed display name
- variant labels
- price range
- reason code: `duplicate`, `variant_by_length`, `variant_by_gender`, `variant_by_zone`, `variant_by_volume`, `promotion`, `category_cleanup`
- apply state

## Organika Draft Heuristics

The current Organika catalogue can be reduced without losing meaning:

- Laser epilation: combine female and male zone rows into category pages or grouped rows with variants by zone and gender.
- Injectable cosmetology: keep major procedure families, move препарат/ml variations into variants or description.
- Seasonal aesthetic cosmetology: move "Сезонное предложение" rows into promotions/highlights.
- Hair services: group biowave, colouring, hair care, and kids haircuts by length or age instead of separate top-level rows.
- Scar aesthetics: group correction by scar size and procedure type.
- Permanent makeup: group by area and technique.
- Podology and manicure/pedicure: split medical podology from nail services, then group repeated treatment variants.

## Acceptance Criteria

- A business with more than 150 active parsed services gets a visible cleanup suggestion.
- The proposal shows before and after counts.
- The proposal includes merge reasons and source service ids.
- Applying the proposal requires explicit approval.
- Raw parsed services remain recoverable.
- No external provider write is performed by this feature.
- Tests cover detection thresholds, duplicate grouping, promotion extraction, and approval-only apply behavior.

## Implementation Phases

1. Backend analyzer: pure function that accepts active `userservices` rows and returns grouped suggestions.
2. Request persistence: save draft compression requests and diffs.
3. Services tab UI: alert, preview, grouped diff, approve/reject controls.
4. Apply path: create/activate curated display rows while keeping raw parsed rows inactive or linked as sources.
5. Post-parse hook: run analyzer after successful parse when service count crosses the threshold.
6. Audit and rollback: show source rows and restore previous active snapshot.
