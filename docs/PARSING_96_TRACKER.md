# Parsing 96% Tracker

## Acceptance Criteria
1. `valid_success_rate >= 96%` на полном batch.
2. По сегментам (провайдер/тип карточки/регион) `>= 92%`.
3. `cost_per_valid_card` не выше baseline более чем на 15%.
4. `p95_latency` не выше baseline более чем на 20%.
5. Два последовательных полных прогона проходят пункты 1-4.

## Definition Of Valid
1. Есть `title` и `address`.
2. Есть `rating` или `reviews_count > 0`.
3. Есть валидные `services` (не мусор, не редакционная подборка).
4. Нет критичной ошибки парсинга в финальном статусе.

## Day 0 (Must-Do Before Changes)
Текущий baseline-срез заполнен в отдельном файле:
`docs/PARSING_96_BASELINE.md`

1. Зафиксировать baseline на последнем полном batch:
   `valid_success_rate`, `captcha_rate`, `proxy_fail_rate`, `cost_per_valid_card`, `p50_latency`, `p95_latency`, `throughput_per_hour`.
2. Включить taxonomy причин фейла:
   `captcha`, `empty_payload`, `parser_mismatch`, `proxy_transport`, `timeout`, `blocked_session`, `invalid_org_url`, `quality_gate_fail`.
3. Собрать `golden_set` (200 карточек) с ручной валидацией.
4. Зафиксировать текущую систему как `control`.

## Daily Experiment Loop (One Hypothesis Per Day)
1. Сформулировать 1 главную гипотезу.
2. Применить изменение на 10% трафика.
3. Сравнить KPI против control.
4. Если ок, расширить до 20%.
5. Снова сравнить KPI.
6. Если ок, full rollout на 100%; иначе rollback.
7. Зафиксировать решение и причину.

## Experiment Register
| ID | Day | Hypothesis | Change | Owner | Rollout | KPI Before | KPI After | Decision | Notes |
|---|---|---|---|---|---|---|---|---|---|
| EXP-00 | D0 | Нужен baseline и taxonomy | KPI + failure reasons + golden set | Alex + AI | 100% (read-only) | - | baseline captured | Ship | Diagnostic foundation |
| EXP-01 | D1 | Proxy score снизит captcha/proxy fail | Health-gate + proxy ranking | AI | 10% -> 20% -> 100% | from D0 | fill | Ship/Rollback |  |
| EXP-02 | D2 | Retry discipline снизит потери | max_attempts + DLQ + TTL + age monitor | AI | 10% -> 20% -> 100% | from D1 | fill | Ship/Rollback |  |
| EXP-03 | D3 | Extraction fix поднимет valid | services/address/rating normalization | AI | 10% -> 20% -> 100% | from D2 | fill | Ship/Rollback |  |
| EXP-04 | D4 | Anti-captcha behavior улучшит проход | concurrency shaping + warmup + jitter | AI | 10% -> 20% -> 100% | from D3 | fill | Ship/Rollback |  |
| EXP-05 | D5 | Fallback orchestration даст прирост | API A/B -> HTML -> retry другой прокси | AI | 10% -> 20% -> 100% | from D4 | fill | Ship/Rollback |  |
| EXP-06 | D6 | Контроль ложных успехов | Audit 100 success + 50 DLQ | Alex | audit | from D5 | fill | Gate pass/fail |  |
| EXP-07 | D7 | Готовность к прод KPI | Full run x2 | Alex + AI | 100% | from D6 | fill | Accept/Not accept |  |

## Daily Report Template
1. `Date:`
2. `Experiment ID:`
3. `Hypothesis:`
4. `Change applied:`
5. `Traffic slice: 10% / 20% / 100%`
6. `KPI: valid_success_rate, captcha_rate, proxy_fail_rate, cost_per_valid_card, p50/p95_latency, throughput_per_hour`
7. `Top-5 failure reasons (count, %):`
8. `Decision: Ship / Rollback / Continue`
9. `Next step (one hypothesis only):`

## Operational Notes
1. Нельзя делать больше одной основной гипотезы за раз.
2. Любое изменение без измерения KPI считается недействительным.
3. Любой рост `valid_success_rate` с деградацией стоимости/latency должен быть отдельно согласован.
4. На D7 решение принимается только по фактам двух последовательных прогонов.
