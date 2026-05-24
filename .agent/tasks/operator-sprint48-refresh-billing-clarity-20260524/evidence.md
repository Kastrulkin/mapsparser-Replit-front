# Evidence Bundle: operator-sprint48-refresh-billing-clarity-20260524

## Summary
- Overall status: PASS

## Proof
- Refresh billing state now includes a plain `explanation` and `user_facing_summary`.
- Web Operator renders the explanation, actual credits, and multiplier near the billing numbers.
- Billing display still reflects existing reservation/settlement data only.

## Checks
- `10 passed` for focused refresh result tests.
- Frontend production build passed.
- `git diff --check` passed.
