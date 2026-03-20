#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app

BATCH_ID="${1:-localos_mass_20260319_136}"
LOG_FILE="/opt/seo-app/logs/parser_kpi_loop_${BATCH_ID}.log"
FORCE_RESET_CAPTCHA="${PARSER_KPI_FORCE_RESET_CAPTCHA:-false}"
mkdir -p /opt/seo-app/logs

while true; do
  ts="$(date +%F_%T)"

  reset_sql=""
  if [[ "${FORCE_RESET_CAPTCHA}" == "true" ]]; then
    reset_sql="
    UPDATE parsequeue
       SET status='pending', paused_reason=NULL, retry_after=NULL, updated_at=CURRENT_TIMESTAMP
     WHERE batch_id='${BATCH_ID}' AND status='paused';
    UPDATE parsequeue
       SET status='pending', retry_after=NULL, updated_at=CURRENT_TIMESTAMP
     WHERE batch_id='${BATCH_ID}' AND status='captcha';
    "
  fi

  docker compose exec -T postgres psql -U beautybot -d local -c "
    ${reset_sql}
    UPDATE parsequeue
       SET status='pending', updated_at=CURRENT_TIMESTAMP
     WHERE batch_id='${BATCH_ID}'
       AND status='processing'
       AND updated_at < (CURRENT_TIMESTAMP - INTERVAL '6 minutes');
    UPDATE parsequeue
       SET status='pending', retry_after=NULL, updated_at=CURRENT_TIMESTAMP
     WHERE batch_id='${BATCH_ID}'
       AND status='error'
       AND (
         error_message LIKE 'error: parser_subprocess_exception%'
         OR error_message LIKE 'error: org_api_not_loaded%'
         OR error_message LIKE 'error: parser_returned_none%'
       );
  " >/dev/null 2>&1 || true

  stats="$(docker compose exec -T postgres psql -U beautybot -d local -At -F , -c "
    SELECT
      COALESCE(SUM(CASE WHEN status='completed' THEN 1 END),0),
      COALESCE(SUM(CASE WHEN status='error' THEN 1 END),0),
      COALESCE(SUM(CASE WHEN status='pending' THEN 1 END),0),
      COALESCE(SUM(CASE WHEN status='processing' THEN 1 END),0),
      COALESCE(SUM(CASE WHEN status='captcha' THEN 1 END),0),
      COALESCE(SUM(CASE WHEN status='paused' THEN 1 END),0),
      COUNT(*)
    FROM parsequeue
    WHERE batch_id='${BATCH_ID}';
  " 2>/dev/null | tail -n1)"

  echo "${ts} ${stats}" >> "${LOG_FILE}"

  completed="$(echo "${stats}" | cut -d, -f1)"
  total="$(echo "${stats}" | cut -d, -f7)"
  if [[ -n "${completed}" && -n "${total}" && "${completed}" == "${total}" ]]; then
    echo "${ts} DONE ${stats}" >> "${LOG_FILE}"
    break
  fi
  sleep 60
done
