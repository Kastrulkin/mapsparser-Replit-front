# AI Agent Use Cases

These scenarios are safe starting points for LocalOS-aware agents.

## 1. Audit a Map Card

The agent receives a map URL or `business_id`, fetches audit data, summarizes the top issues, and prepares a short action plan.

Approval: required before sending the audit externally.

## 2. Prepare a Location Improvement Plan

The agent reads card audit, reviews, services, and posts, then groups actions into today, 7 days, and recurring work.

Approval: required before creating tasks or changing data.

## 3. Generate Card Posts

The agent drafts posts from services, events, seasonal demand, or content plan items.

Approval: required before publishing or copying into an external provider.

## 4. Draft Review Replies

The agent drafts replies that mention the reviewed service where supported by the text and optionally suggests a soft adjacent service mention.

Approval: required before publication.

## 5. Analyze Services

The agent detects weak service names, missing attributes, duplicated services, or lost SEO keywords.

Approval: required before applying changes.

## 6. Run a First Finance Review

The agent reads finance KPIs, data quality, and red zones, then explains what data is missing and what to fill first.

Approval: required before writing finance entries or importing files.

## 7. Find Nearby Partners

The agent imports or searches potential partners, parses leads, matches services, and drafts an offer.

Approval: required before shortlist changes, outreach, or sending batches.

## 8. Prepare Telegram Summary

The agent summarizes audits, finance red zones, pattern proposals, or partnership status for the owner or superadmin.

Approval: not required for read-only summary; required for buttons that trigger writes.

## 9. Regenerate Problem Items

The agent identifies low-quality service/news/review suggestions and queues regeneration only for the problematic subset.

Approval: required for bulk regeneration and applying results.

## 10. Monthly Recalibration With HITL

The agent collects monthly evidence, proposes new industry patterns, and sends a summary to superadmin.

Approval: required before activating or rolling back patterns.
