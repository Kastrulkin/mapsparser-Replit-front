# Evidence Bundle: operator-sprint47-telegram-refresh-retry-20260524

## Summary
- Overall status: PASS

## Proof
- Telegram client intent recognizes `повтори refresh` and related commands.
- `build_refresh_retry_text` uses `request_refresh_retry` with explicit confirmation, so credits/safety match the web path.
- Telegram status text now tells the user which failed refresh can be retried.
- Retry result text keeps external publication/manual copy limits explicit.

## Checks
- `21 passed` for focused Telegram/retry tests.
- `py_compile` passed.
- `git diff --check` passed.
