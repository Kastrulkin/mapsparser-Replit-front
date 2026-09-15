# Operator recovery — 15 September 2026

The interrupted post-rewrite deployment left worker and operator-worker exited (137), with OOMKilled=false. Its runner exited 143 before reporting completion. PostgreSQL and the app were later running, but the two stopped workers had not resumed. This does not establish the root cause of the host/network interruption.

Restored the existing two worker containers without rebuild or queue data edits. PostgreSQL accepts connections. No outstanding non-completed/non-cancelled async jobs were present. Available memory after startup was about 1.45 GiB; root disk had about 3 GiB free. Both workers remained running during verification; recent app/worker/bot logs had zero tracebacks and Telegram NetworkError occurrences.

Replaced the Telegram process-only healthcheck with a read-only getMe probe through the configured Telegram proxy. It verifies the bot process and an actual successful Telegram response, with bounded timeout, three failures before unhealthy, and no token/error payload logging. It does not consume updates or send messages. Only the bot was recreated for this healthcheck; three local regression tests passed and the live probe exited successfully.

Production post-generation probe used Riderra context and a Phuket editorial brief. The real provider returned valid JSON with a 530-character post in 11.5 seconds. No plan writes were performed. GigaChat still returns HTTP 402; the existing fallback completed generation. GigaChat billing remains an external limitation, not a repaired credential or quota.

Evidence: server `/opt/seo-app/.deploy/operator-restore-20260915/` and `/opt/seo-app/.deploy/post-rewrite-20260915/restore.exit` (0). Local tests `/tmp/operator-restore/tests.log`. Physical-device and full incoming-voice command tests are not substituted by this text generation probe.
