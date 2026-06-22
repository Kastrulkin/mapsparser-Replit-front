#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"
SINCE="${SMOKE_SINCE:-30m}"
ROOT_DIR="${SOCIAL_RUNTIME_SMOKE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVER_HOST="${DEPLOY_HOST:-root@80.78.242.105}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-https://localos.pro}"
SMOKE_ALLOW_UNSCOPED="${SOCIAL_SMOKE_ALLOW_UNSCOPED:-0}"
SMOKE_BUSINESS_ID="${SOCIAL_RUNTIME_SMOKE_BUSINESS_ID:-}"
SSH_OPTS=(
  -i "$SSH_KEY"
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

run_local() {
  cd "$ROOT_DIR"

  echo "[social-runtime] docker compose ps"
  docker compose ps

  echo
  echo "[social-runtime] app health"
  curl -I --max-time "${SMOKE_CURL_TIMEOUT:-10}" http://localhost:8000

  echo
  echo "[social-runtime] unauthenticated runtime-status is guarded"
  tmp_body="$(mktemp)"
  status="$(curl -sS -o "$tmp_body" -w "%{http_code}" http://localhost:8000/api/social-posts/runtime-status)"
  echo "runtime_status_http=${status}"
  if [[ "$status" != "401" ]]; then
    echo "Expected /api/social-posts/runtime-status to require auth" >&2
    cat "$tmp_body" >&2
    exit 1
  fi

  echo
  echo "[social-runtime] runtime safety payload"
  docker compose exec -T app python3 - <<PY
import json
import os
import sys

from api.social_posts_api import social_post_runtime_status_payload

payload = social_post_runtime_status_payload()
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

if payload.get("approval_required") is not True:
    print("approval_required invariant failed", file=sys.stderr)
    sys.exit(1)
if payload.get("browser_final_click_allowed") is not False:
    print("browser_final_click_allowed invariant failed", file=sys.stderr)
    sys.exit(1)

allow_unscoped_for_smoke = str(os.getenv("SOCIAL_SMOKE_ALLOW_UNSCOPED") or "${SMOKE_ALLOW_UNSCOPED}").lower() in {"1", "true", "yes", "on"}
for key in ("dispatch", "metrics"):
    section = payload.get(key) if isinstance(payload.get(key), dict) else {}
    enabled = bool(section.get("enabled"))
    scoped = bool(section.get("scoped"))
    allow_unscoped = bool(section.get("allow_unscoped"))
    blocked_without_scope = bool(section.get("blocked_without_scope"))
    if enabled and not scoped and not allow_unscoped and not blocked_without_scope:
        print(f"{key} enabled without scope but not blocked", file=sys.stderr)
        sys.exit(1)
    if enabled and allow_unscoped and not allow_unscoped_for_smoke:
        print(f"{key} unscoped allow-all is enabled; set SOCIAL_SMOKE_ALLOW_UNSCOPED=1 to acknowledge", file=sys.stderr)
        sys.exit(1)
PY

  if [[ -n "${SMOKE_BUSINESS_ID}" ]]; then
    echo
    echo "[social-runtime] scoped launch preflight dry-run"
    SOCIAL_RUNTIME_SMOKE_BUSINESS_ID="${SMOKE_BUSINESS_ID}" docker compose exec -T app python3 - <<'PY'
import json
import os
import sys

from core.helpers import get_business_owner_id
from database_manager import DatabaseManager
from services.social_post_service import get_social_launch_preflight

business_id = str(os.getenv("SOCIAL_RUNTIME_SMOKE_BUSINESS_ID") or "").strip()
if not business_id:
    print("SOCIAL_RUNTIME_SMOKE_BUSINESS_ID is empty", file=sys.stderr)
    sys.exit(1)

db = DatabaseManager()
cursor = db.conn.cursor()
try:
    owner_id = str(get_business_owner_id(cursor, business_id) or "").strip()
finally:
    db.close()

if not owner_id:
    print(f"Could not resolve owner for business {business_id}", file=sys.stderr)
    sys.exit(1)

payload = get_social_launch_preflight(owner_id, business_id, batch_size=10)
summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
runbook = payload.get("launch_runbook") if isinstance(payload.get("launch_runbook"), dict) else {}
preview = payload.get("dispatch_preview") if isinstance(payload.get("dispatch_preview"), dict) else {}

print(json.dumps({
    "business_id": payload.get("business_id"),
    "status": payload.get("status"),
    "safe_to_enable_scoped_dispatch": payload.get("safe_to_enable_scoped_dispatch"),
    "summary": summary,
    "runbook_ready": runbook.get("ready"),
    "dry_run": preview.get("dry_run"),
    "next_action_ru": payload.get("next_action_ru"),
}, ensure_ascii=False, sort_keys=True))

if preview.get("dry_run") is not True:
    print("launch preflight must be dry-run", file=sys.stderr)
    sys.exit(1)
if safety.get("approval_required") is not True:
    print("launch preflight approval invariant failed", file=sys.stderr)
    sys.exit(1)
if safety.get("browser_final_click_allowed") is not False:
    print("launch preflight browser final click invariant failed", file=sys.stderr)
    sys.exit(1)
if safety.get("maps_are_supervised_or_manual") is not True:
    print("launch preflight maps supervision invariant failed", file=sys.stderr)
    sys.exit(1)
if int(summary.get("skipped_no_access") or 0) != 0:
    print("launch preflight skipped_no_access must be 0 for resolved owner", file=sys.stderr)
    sys.exit(1)
PY
  else
    echo
    echo "[social-runtime] scoped launch preflight dry-run"
    echo "Skipped: set SOCIAL_RUNTIME_SMOKE_BUSINESS_ID to verify a concrete business without publishing."
  fi

  echo
  echo "[social-runtime] runtime source markers"
  docker compose exec -T app sh -lc \
    "grep -n 'result_summaries_ru' /app/src/services/social_post_service.py | head -n 1 && grep -n 'social.post.publish_supervised_browser' /app/src/services/social_post_service.py | head -n 1"

  echo
  echo "[social-runtime] worker social loop logs"
  worker_logs="$(docker compose logs --since "$SINCE" worker || true)"
  if echo "$worker_logs" | grep -F "[SOCIAL_POST_DISPATCH]" >/dev/null; then
    echo "$worker_logs" | grep -F "[SOCIAL_POST_DISPATCH]" | tail -n 3
  else
    echo "No [SOCIAL_POST_DISPATCH] line in worker logs since ${SINCE}; acceptable when dispatch is disabled or interval has not elapsed."
  fi
  if echo "$worker_logs" | grep -F "[SOCIAL_POST_METRICS]" >/dev/null; then
    echo "$worker_logs" | grep -F "[SOCIAL_POST_METRICS]" | tail -n 3
  else
    echo "No [SOCIAL_POST_METRICS] line in worker logs since ${SINCE}; acceptable when metrics collection is disabled or interval has not elapsed."
  fi

  echo
  echo "[social-runtime] live frontend social cockpit chunk"
  curl -sS --max-time "${SMOKE_CURL_TIMEOUT:-10}" "$PUBLIC_DOMAIN/" | grep -n "/assets/index-" | head -n 1
  current_index_js="$(grep -o '/assets/index-[^"]*\.js' frontend/dist/index.html | tail -n 1 | sed 's#^/##')"
  current_news_js=""
  if [[ -n "$current_index_js" && -f "frontend/dist/${current_index_js}" ]]; then
    current_news_js="$(grep -o 'NewsGenerator-[A-Za-z0-9_-]*\.js' "frontend/dist/${current_index_js}" | tail -n 1 || true)"
  fi
  if [[ -n "$current_news_js" && -f "frontend/dist/assets/${current_news_js}" ]]; then
    cockpit_chunk="frontend/dist/assets/${current_news_js}"
  else
    cockpit_chunk="$(grep -R -l "OpenClaw не нажимает финальную кнопку публикации" frontend/dist/assets 2>/dev/null | head -n 1 || true)"
  fi
  if [[ -z "$cockpit_chunk" ]]; then
    echo "Could not find current social OpenClaw readiness copy in frontend/dist/assets" >&2
    exit 1
  fi
  echo "cockpit_chunk=${cockpit_chunk}"
  grep -F "Быстрый запуск публикаций" "$cockpit_chunk" >/dev/null
  grep -F "Первый запуск publishing loop" "$cockpit_chunk" >/dev/null
  grep -F "контроль/вручную" "$cockpit_chunk" >/dev/null
  grep -F "Безопасная проверка: LocalOS ничего не публикует" "$cockpit_chunk" >/dev/null
  if grep -F "Яндекс/2ГИС controlled/manual" "$cockpit_chunk" >/dev/null; then
    echo "Current social cockpit chunk contains old mixed-language Yandex/2GIS copy" >&2
    exit 1
  fi
  if grep -F "Карты идут через controlled/manual" "$cockpit_chunk" >/dev/null; then
    echo "Current social cockpit chunk contains old mixed-language maps copy" >&2
    exit 1
  fi

  echo
  echo "social posting runtime smoke: ok"
}

run_server() {
  ssh "${SSH_OPTS[@]}" "$SERVER_HOST" "
    set -euo pipefail
    cd /opt/seo-app
    SMOKE_SINCE='${SINCE}' \
    PUBLIC_DOMAIN='${PUBLIC_DOMAIN}' \
    SOCIAL_SMOKE_ALLOW_UNSCOPED='${SMOKE_ALLOW_UNSCOPED}' \
    SOCIAL_RUNTIME_SMOKE_BUSINESS_ID='${SMOKE_BUSINESS_ID}' \
    SOCIAL_RUNTIME_SMOKE_ROOT='/opt/seo-app' \
    bash -s local
  " < "$ROOT_DIR/scripts/smoke_social_posting_runtime.sh"
}

case "$MODE" in
  local)
    run_local
    ;;
  server)
    run_server
    ;;
  *)
    echo "Usage: $0 [local|server]" >&2
    exit 2
    ;;
esac
