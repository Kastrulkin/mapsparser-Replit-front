# Parsing 96% SQL Package

Этот пакет закрывает D0-диагностику для трека `valid_success_rate >= 96%` и даёт один каноничный способ собирать baseline, failure taxonomy, proxy health, Ralph-loop signals и golden set candidates.

## Файлы

| File | Purpose |
|---|---|
| `scripts/sql/parsing96/d0_batch_baseline.sql` | batch KPI: статусы, strict validity, latency |
| `scripts/sql/parsing96/d0_top_failure_reasons.sql` | top-10 причин деградации по taxonomy |
| `scripts/sql/parsing96/d0_proxy_layer.sql` | здоровье proxy pool |
| `scripts/sql/parsing96/d0_ai_learning_baseline.sql` | baseline Ralph loop по capability/prompt |
| `scripts/sql/parsing96/d0_golden_set_candidates.sql` | кандидаты для ручной сборки golden set |

## Команды

Все команды ниже рассчитаны на PostgreSQL runtime.

```bash
psql "$DATABASE_URL" -v batch_id='localos_mass_20260319_136' -f scripts/sql/parsing96/d0_batch_baseline.sql
psql "$DATABASE_URL" -v batch_id='localos_mass_20260319_136' -f scripts/sql/parsing96/d0_top_failure_reasons.sql
psql "$DATABASE_URL" -f scripts/sql/parsing96/d0_proxy_layer.sql
psql "$DATABASE_URL" -v days=30 -f scripts/sql/parsing96/d0_ai_learning_baseline.sql
psql "$DATABASE_URL" -v batch_id='localos_mass_20260319_136' -v valid_limit=80 -v partial_limit=60 -v failed_limit=60 -f scripts/sql/parsing96/d0_golden_set_candidates.sql
```

## Что считать D0 completed

1. Есть baseline по последнему полному batch.
2. Есть top-10 failure reasons с долями от batch и от failures.
3. Есть proxy snapshot.
4. Есть AI learning baseline за 30 дней.
5. Есть выгрузка кандидатов для ручной golden set проверки.

## Как использовать дальше

1. Результаты `d0_batch_baseline.sql` фиксируются как control.
2. `d0_top_failure_reasons.sql` определяет Pareto-причины для следующей гипотезы.
3. `d0_proxy_layer.sql` используется как gate перед rollout 10% -> 20% -> 100%.
4. `d0_ai_learning_baseline.sql` нужен для контроля Ralph loop на услугах, отзывах, новостях и outreach.
5. `d0_golden_set_candidates.sql` даёт сырой shortlist; вручную подтверждённые кейсы становятся golden set.

## Замечание по valid

В SQL-пакете intentionally выводятся две strict-метрики:

- `valid_strict_services`
- `valid_strict_products`

Для operational KPI основным считается `valid_strict_services`, потому что он ближе к реальному пользовательскому результату. `valid_strict_products` оставлен как диагностический cross-check на случай, если карточка содержит products JSON, но услуги не были доведены до `userservices`.
