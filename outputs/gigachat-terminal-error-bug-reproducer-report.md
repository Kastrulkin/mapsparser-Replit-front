# GigaChat terminal error: bug reproducer report

Status: `FIX_PROVEN`

## Reproduced behavior

The direct GigaChat client correctly classified HTTP 402 as
`gigachat_payment_required` with `retryable=False`. The LLM adapter discarded
that classification and returned a generic `provider_error`; the gateway then
raised `RuntimeError: GIGACHAT_REQUEST_FAILED`. Downstream outreach processing
treated that unknown exception as retryable and left work in `retry_wait`.

The focused regression test failed before the fix with one failure and three
passes.

## Minimal fix

- `GigaChatAdapter` now preserves terminal provider failures as a distinct,
  body-free result status with the safe provider error code.
- `analyze_text_with_gigachat` restores a safe `GigaChatProviderError` with
  `retryable=False` instead of producing a generic runtime error.
- Retryable provider failures and existing DeepSeek routing behavior remain
  unchanged.

## Verification

- Focused regression: `4 passed`.
- Combined GigaChat, LLM routing, contact intelligence and outreach safety
  suites: `134 passed`.
- Python compile check: passed.

## Residual operational condition

GigaChat still rejects requests with HTTP 402 until provider billing is
restored. This code change prevents a retry storm and exposes the real blocker;
it does not fabricate a successful generation. Existing production
`retry_wait` rows are not modified by this package.
