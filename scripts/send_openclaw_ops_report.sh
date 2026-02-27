#!/usr/bin/env bash
set -euo pipefail

REPORT_FILE="${REPORT_FILE:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
OPENCLAW_SUPERADMIN_TELEGRAM_IDS="${OPENCLAW_SUPERADMIN_TELEGRAM_IDS:-}"

if [[ -z "${TELEGRAM_BOT_TOKEN}" ]]; then
  echo "TELEGRAM_BOT_TOKEN is required"
  exit 1
fi

if [[ -z "${OPENCLAW_SUPERADMIN_TELEGRAM_IDS}" ]]; then
  echo "OPENCLAW_SUPERADMIN_TELEGRAM_IDS is required"
  exit 1
fi

if [[ -n "${REPORT_FILE}" ]]; then
  if [[ ! -f "${REPORT_FILE}" ]]; then
    echo "REPORT_FILE not found: ${REPORT_FILE}"
    exit 1
  fi
else
  REPORT_FILE="$(mktemp "${TMPDIR:-/tmp}/openclaw_ops_report.XXXXXX.txt")"
  cat > "${REPORT_FILE}"
fi

python3 - "${REPORT_FILE}" <<'PY'
import json
import os
import sys
from urllib import request as urllib_request, error as urllib_error

report_path = sys.argv[1]
token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
target_ids = [
    item.strip()
    for item in os.getenv("OPENCLAW_SUPERADMIN_TELEGRAM_IDS", "").split(",")
    if item.strip()
]

with open(report_path, "r", encoding="utf-8") as f:
    text = f.read().strip()

if not text:
    print("Report is empty")
    raise SystemExit(1)

sent = 0
failed = 0
for chat_id in target_ids:
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    req = urllib_request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            code = int(getattr(resp, "status", 500))
            if 200 <= code < 300:
                sent += 1
            else:
                failed += 1
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, ValueError):
        failed += 1

print(f"sent={sent} failed={failed} targets={len(target_ids)}")
raise SystemExit(0 if sent > 0 else 1)
PY
