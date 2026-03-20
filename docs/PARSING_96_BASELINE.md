# Parsing 96% Baseline (Current State)

Дата среза: `2026-03-20 14:33`  
Источник: production server `/opt/seo-app`, batch `localos_mass_20260319_136`
Автоматически собран скриптом:
`python scripts/parsing_baseline_snapshot.py --batch-id localos_mass_20260319_136`

## Snapshot
| Metric | Value | Notes |
|---|---:|---|
| Total tasks in batch | 136 | fixed batch size |
| Completed | 43 | `31.62%` |
| Pending | 90 | queue mostly waiting/retrying |
| Processing | 3 | current in-flight |
| Error | 0 | текущий loop авто-реанимирует часть transient/error |
| Paused | 0 | текущий loop раз в минуту возвращает paused->pending |
| Captcha | 0 | текущий loop раз в минуту возвращает captcha->pending |

## Valid Quality (Definition Of Valid)
Definition used:
1. `title` and `address` are present
2. `rating` is present OR `reviews_count > 0`
3. `products` blocks > 0

Computed on latest card per completed business:

| Metric | Value | Rate |
|---|---:|---:|
| Completed tasks audited | 43 | 100% of completed |
| with_title_address | 36 | 83.72% of completed |
| with_rating_or_reviews | 37 | 86.05% of completed |
| with_products | 9 | 20.93% of completed |
| valid_strict | 6 | 13.95% of completed / 4.41% of full batch |

## Proxy Layer Baseline
Active proxy pool state:

| Proxy ID | is_active | is_working | success_count | failure_count |
|---|---|---|---:|---:|
| `afe48836-72ca-47ac-9407-fc47dbe45e2c` | true | true | 11 | 64 |

Derived metric:
- `proxy_fail_rate_pct = 85.33%` (for active proxy: failures / (successes + failures))

## Failure Taxonomy (Current Top Prefixes)
From `parsequeue` status + `error_message` classification:

| Reason | Count |
|---|---:|
| `captcha` | 47 |
| `empty_payload` | 1 |
| `unknown` | 1 |

Вывод: доминирующая причина деградации — `captcha`.

## Latency / Throughput Baseline
On completed tasks (`created_at -> updated_at`):

| Metric | Value |
|---|---:|
| p50 latency | 902.99 min |
| p95 latency | 1198.73 min |

KPI loop (`logs/parser_kpi_loop_localos_mass_20260319_136.log`) за последние ~20 минут:
- latest snapshot showed growth to `43 completed`, but sustained throughput remains low and unstable

## Cost Baseline
- `cost_per_valid_card`: not available from DB yet (needs billing join or provider API pull)
- BrightData spend is visible in provider UI (manual source), but not yet ingested into platform KPI

## Target vs Actual
Цель для batch `136`:
- `target_valid_count = ceil(136 * 0.96) = 131`

Текущее:
- `actual_valid_count = 6`
- `gap_to_target = 131 - 6 = 125 cards`
- `actual_valid_success_rate = 6 / 136 = 4.41%`
- `progress_to_target = actual_valid_count / target_valid_count = 4.58%`

### Formula Reference
1. `target_valid_count = ceil(total_batch * target_rate)`
2. `actual_valid_success_rate = actual_valid_count / total_batch`
3. `gap_to_target = max(target_valid_count - actual_valid_count, 0)`
4. `progress_to_target = actual_valid_count / target_valid_count`

## Important Context
`scripts/parser_kpi_loop.sh` currently auto-resets statuses in this batch:
1. `paused -> pending`
2. `captcha -> pending`
3. stale `processing -> pending`
4. selected transient `error -> pending`

Это ускоряет попытки, но скрывает "чистую" структуру статусов (paused/captcha/error) в моменте.
