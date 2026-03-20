# Profile: Parsing Network Stability

Use this profile only for parsing/network data refresh tasks.

## A) Domain Objectives
- No garbage values in parsed fields.
- CAPTCHA must not stall the entire batch.
- Source metrics (rating/reviews/etc.) must remain reliable.
- One failed point must not stop full network processing.

## B) Domain Safety Guards
- Validate extracted payload before persist.
- Reject malformed/low-quality payloads.
- Preserve last known good values when new payload is suspicious.
- Persist reason codes for quality rejection/fallback paths.

## C) CAPTCHA Policy
- Manual action is not default behavior.
- On CAPTCHA:
  - set delayed status (for example `captcha_delayed`)
  - schedule retry with backoff + jitter
  - apply cooldown and auto-resume attempts
- If retry budget is exhausted:
  - keep explicit error status for the point
  - continue remaining points

## D) Completion for Parsing Tasks
- At least 2 consecutive successful full runs on target network without manual intervention.
- Failed points, if any, are isolated with explicit statuses and reasons.
- Parsed values pass domain quality checks.
