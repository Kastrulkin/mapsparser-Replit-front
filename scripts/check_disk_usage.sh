#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

warning_threshold="${DISK_WARNING_THRESHOLD:-70}"
high_threshold="${DISK_HIGH_THRESHOLD:-80}"
critical_threshold="${DISK_CRITICAL_THRESHOLD:-90}"
state_dir="${DISK_MONITOR_STATE_DIR:-/var/lib/localos-disk-monitor}"
state_file="${state_dir}/level"

usage="$(df -P / | awk 'NR == 2 {gsub("%", "", $5); print $5}')"
available="$(df -hP / | awk 'NR == 2 {print $4}')"
level="ok"
priority="user.info"

if [[ "${usage}" -ge "${critical_threshold}" ]]; then
  level="critical"
  priority="user.crit"
elif [[ "${usage}" -ge "${high_threshold}" ]]; then
  level="high"
  priority="user.err"
elif [[ "${usage}" -ge "${warning_threshold}" ]]; then
  level="warning"
  priority="user.warning"
fi

mkdir -p "${state_dir}"
previous="ok"
if [[ -f "${state_file}" ]]; then
  previous="$(cat "${state_file}")"
fi

if [[ "${level}" != "${previous}" ]]; then
  if [[ "${level}" == "ok" ]]; then
    message="LocalOS: место на сервере восстановлено — занято ${usage}%, свободно ${available}."
  else
    message="LocalOS: заполнение диска ${usage}% (${level}), свободно ${available}. Пороги: ${warning_threshold}/${high_threshold}/${critical_threshold}%."
  fi
  logger -p "${priority}" -t localos-disk-monitor "${message}"

  bot_token="${TELEGRAM_BOT_TOKEN:-}"
  recipients="${DISK_ALERT_TELEGRAM_CHAT_IDS:-${OPENCLAW_SUPERADMIN_TELEGRAM_IDS:-}}"
  if [[ -n "${bot_token}" && -n "${recipients}" ]]; then
    IFS=',' read -r -a chat_ids <<< "${recipients}"
    for chat_id in "${chat_ids[@]}"; do
      clean_chat_id="$(echo "${chat_id}" | xargs)"
      if [[ -n "${clean_chat_id}" ]]; then
        curl -fsS --max-time 10 \
          --data-urlencode "chat_id=${clean_chat_id}" \
          --data-urlencode "text=${message}" \
          "https://api.telegram.org/bot${bot_token}/sendMessage" >/dev/null || \
          logger -p user.err -t localos-disk-monitor "Не удалось отправить Telegram-уведомление о диске"
      fi
    done
  fi
fi

printf '%s\n' "${level}" > "${state_file}"
printf 'usage=%s level=%s available=%s previous=%s\n' "${usage}" "${level}" "${available}" "${previous}"
