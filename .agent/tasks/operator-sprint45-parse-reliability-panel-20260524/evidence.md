# Evidence Bundle: operator-sprint45-parse-reliability-panel-20260524

## Summary
- Overall status: PASS

## Proof
- `build_parse_reliability_state` now returns `technical_details` for parse diagnosis.
- The web Operator reliability panel renders queue status, retry time, captcha state, resume flag, warnings count, and retry attempt markers.
- The change is read/explain only and does not call Apify, retry jobs, release credits, or write to providers.

## Checks
- `14 passed` for focused refresh result/retry tests.
- Frontend production build passed.
- `git diff --check` passed.
