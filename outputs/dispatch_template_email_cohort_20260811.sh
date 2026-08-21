#!/usr/bin/env bash
set -euo pipefail

cohort="${1:?cohort index is required}"
cd /opt/seo-app
docker compose cp debug_data/dispatch_template_email_cohort_20260811.py app:/app/debug_data/dispatch_template_email_cohort_20260811.py
docker compose cp debug_data/localos-template-email-launch-20260811.json app:/app/debug_data/localos-template-email-launch-20260811.json
docker compose cp debug_data/localos-template-review-v12-20260811.json app:/app/debug_data/localos-template-review-v12-20260811.json
exec docker compose exec -T -w /app app python3 /app/debug_data/dispatch_template_email_cohort_20260811.py --cohort "${cohort}"
