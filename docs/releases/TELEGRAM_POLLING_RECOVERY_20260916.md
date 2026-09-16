# Telegram receiver recovery — 2026-09-16

Status: code deployed; stable Telegram connectivity remains blocked.

## Evidence and impact
- Today’s voice had not entered LocalOS audio jobs or conversation processing.
- Initial restart used legacy `drop_pending_updates=True`: two pending Telegram events disappeared without LocalOS processing. This operational mistake was disclosed to the user. Those events cannot be recovered; the voice must be resent after reception is stable.
- Queue clearing is now disabled. Actual successful getUpdates, not only getMe, is required by health monitoring.
- Requests are bounded to 65 seconds; a watchdog exits after 180 seconds without successful polling so Docker can restart the receiver.
- One successful actual poll was observed after deployment, followed by recurring connection failures. This is not stable recovery.
- Three direct Telegram probes timed out; three configured-proxy probes failed (ReadTimeout, ReadError, ConnectError). Three direct example.com control probes returned HTTP 200.
- SSH to the OpenClaw proxy host timed out during banner exchange via both public and private/jump routes. No proxy-host configuration was modified.

## Verification
18 focused polling, healthcheck and voice-autosubmit tests passed. Deployment updated only Telegram source modules and restarted telegram-bot. No schema or business-data changes.

## Remaining work
Restore Grimbird connectivity on OpenClaw, establish sustained fresh getUpdates heartbeat, then verify a resent voice end to end. Do not mark mere process uptime or a single successful poll as resolution.
