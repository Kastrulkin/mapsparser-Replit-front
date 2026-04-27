# Parsing 96% Daily Report Template

Используй этот шаблон ежедневно для D1-D14. Он рассчитан на один главный эксперимент в день и жёсткий `Ship / Rollback / Continue` decision.

---

## Header

- Date:
- Day: `D1` ... `D14`
- Experiment ID:
- Owner:
- Batch / cohort:
- Rollout: `10% / 20% / 50% / 100%`
- Control baseline file: [docs/PARSING_96_BASELINE.md](/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/docs/PARSING_96_BASELINE.md)

## Hypothesis

- Main hypothesis:
- Why this hypothesis now:
- Change scope:
- Non-goals for this day:

## Commands Run

```bash
psql "$DATABASE_URL" -v batch_id='<BATCH_ID>' -f scripts/sql/parsing96/d0_batch_baseline.sql
psql "$DATABASE_URL" -v batch_id='<BATCH_ID>' -f scripts/sql/parsing96/d0_top_failure_reasons.sql
psql "$DATABASE_URL" -f scripts/sql/parsing96/d0_proxy_layer.sql
psql "$DATABASE_URL" -v days=30 -f scripts/sql/parsing96/d0_ai_learning_baseline.sql
```

При ручной сверке golden set:

```bash
psql "$DATABASE_URL" -v batch_id='<BATCH_ID>' -v valid_limit=80 -v partial_limit=60 -v failed_limit=60 -f scripts/sql/parsing96/d0_golden_set_candidates.sql
```

## KPI Gate

| KPI | Control | Today | Gate | Result |
|---|---:|---:|---:|---|
| valid_strict_rate |  |  | `>= control` |  |
| segment_valid_rate_min |  |  | `>= 92%` |  |
| captcha_rate |  |  | `<= control` |  |
| proxy_fail_rate |  |  | `<= control` |  |
| cost_per_valid_card |  |  | `<= control + 15%` |  |
| p95_latency |  |  | `<= control + 20%` |  |
| throughput_per_hour |  |  | `>= control` |  |
| unknown_failure_share |  |  | `< 5%` |  |

## Failure Pareto

| Reason | Count | % of failures | Trend vs control |
|---|---:|---:|---|
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

## Golden Set Audit

- Sample audited:
- Valid true positives:
- False successes:
- Typical wrong fields:
- New rule needed:

## Ralph Loop / AI Learning

| Capability | Generated | Accepted | Rejected | Edited before accept | Prompt winner |
|---|---:|---:|---:|---:|---|
| services.optimize |  |  |  |  |  |
| reviews.reply |  |  |  |  |  |
| news.generate |  |  |  |  |  |
| outreach / partnership |  |  |  |  |  |

## Operational Notes

- Proxy state:
- Retry / DLQ state:
- Captcha behavior:
- Unexpected regressions:
- Logs / bundles to keep:

## Decision

- Decision: `Ship / Rollback / Continue`
- Why:
- Next hypothesis:
- Rollout for tomorrow:

## Close-out

- Files changed today:
- Checks run:
- Residual risks:

---

## Minimal Rule

Если в течение дня изменилось больше одной основной гипотезы, отчёт считается невалидным для продуктового решения. Один день = одна главная гипотеза.
