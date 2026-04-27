# Parsing 96% Report — D0

- Date: `2026-04-06`
- Batch ID: `61987050-b2a7-48e3-b93c-0f5aafd8ee5a`
- Source: production server `/opt/seo-app`
- Goal: establish control baseline for `valid_success_rate >= 96%`

## Batch Baseline

| KPI | Value | Notes |
|---|---:|---|
| total_tasks | 131 | full batch |
| completed | 129 | `98.47%` status completion |
| error | 2 | `1.53%` |
| completed_cards | 129 | latest card per completed business |
| with_title_address | 124 | main drop area: 5 completed cards still weak |
| with_rating_or_reviews | 123 | main drop area: 6 completed cards still weak |
| with_active_services | 118 | main drop area: 11 completed cards have zero active services |
| with_products_blocks | 89 | weaker than services, diagnostic only |
| valid_strict_services | 114 | operational KPI numerator |
| valid_strict_services_rate_of_batch | `87.02%` | current control baseline |
| valid_strict_products | 87 | diagnostic cross-check |
| p50_latency | 50.78 min | completed tasks only |
| p95_latency | 90.55 min | completed tasks only |

## Target Gap

| Metric | Value |
|---|---:|
| target_rate | `96%` |
| target_valid_count | 126 |
| actual_valid_count | 114 |
| gap_to_target | 12 cards |

## Failure Pareto

| Reason | Count | % of batch | % of failures | Comment |
|---|---:|---:|---:|---|
| unknown | 2 | `1.53%` | `100%` | both errors are Apify-upstream class, one explicit `apify_empty_dataset`, one `502 Bad Gateway` |

### Main observation

Status completion is already high (`98.47%`), but strict validity is lower (`87.02%`).
This means the current bottleneck is no longer queue completion. It is payload quality:

1. completed card without address
2. completed card without rating or reviews
3. completed card with zero active services

## Proxy Layer

| Proxy | is_active | is_working | success | failure | fail_rate |
|---|---|---|---:|---:|---:|
| `afe48836-72ca-47ac-9407-fc47dbe45e2c` | true | true | 119 | 326 | `73.26%` |
| `61db1841-67da-42d6-a77d-6e3070d7da24` | false | true | 5 | 54 | `91.53%` |
| `bd-resi-test-1` | false | false | 0 | 50 | `100%` |

### Proxy conclusion

Proxy pool is still weak. One active proxy survives, but its fail rate is too high for a reliable `96%` target on its own. This is still a risk, but it is not the dominant reason in this specific batch because the batch already reaches `98.47%` completed status.

## Ralph Loop Baseline (30d)

| Capability | Total | Generated | Accepted | Rejected | Edited before accept |
|---|---:|---:|---:|---:|---:|
| `services.optimize` | 44 | 44 | 0 | 0 | 0 |
| `news.generate` | 3 | 3 | 0 | 0 | 0 |
| `reviews.reply` | 1 | 1 | 0 | 0 | 0 |
| `partnership.draft_offer` | 1 | 1 | 0 | 0 | 0 |

### Ralph loop conclusion

Learning events exist, but the loop is currently generation-heavy and decision-light.
There are almost no accept or reject signals in the last 30 days, so prompt optimization is still under-instrumented. For services in particular, the system generated `44` events but recorded `0` accept or reject outcomes.

## Golden Set Shortlist Signal

A sample shortlist from the same batch shows three clear groups:

1. `valid_high_signal`
Many Kebab cards already have title, address, rating, and active services.

2. `completed_partial`
Typical defects:
- empty address
- empty rating and zero reviews
- zero active services despite completed status

3. `failed_or_blocked`
Only two cards in this batch, both Apify-side or upstream-failure shaped.

## D0 Verdict

- Control baseline captured: `PASS`
- Current `valid_strict_services_rate_of_batch`: `87.02%`
- Gap to `96%`: `12 cards`
- Dominant next workstream: quality uplift on completed cards, not raw queue completion

## Recommended D1 Hypothesis

`EXP-01`

Completed cards are being marked successful before service hydration is consistently finished.
The next safest hypothesis is:

`Tighten completed -> valid gate around address/rating/services and trace why 11 completed cards still end with zero active services.`

## Commands Used

```bash
cd /opt/seo-app
docker compose exec -T postgres psql -U beautybot -d local -v batch_id=61987050-b2a7-48e3-b93c-0f5aafd8ee5a -f /tmp/d0_batch_baseline.sql
docker compose exec -T postgres psql -U beautybot -d local -v batch_id=61987050-b2a7-48e3-b93c-0f5aafd8ee5a -f /tmp/d0_top_failure_reasons.sql
docker compose exec -T postgres psql -U beautybot -d local -f /tmp/d0_proxy_layer.sql
docker compose exec -T postgres psql -U beautybot -d local -v days=30 -f /tmp/d0_ai_learning_baseline.sql
docker compose exec -T postgres psql -U beautybot -d local -v batch_id=61987050-b2a7-48e3-b93c-0f5aafd8ee5a -v valid_limit=20 -v partial_limit=10 -v failed_limit=10 -f /tmp/d0_golden_set_candidates.sql
```
