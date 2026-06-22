#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"
SINCE="${SMOKE_SINCE:-30m}"
ROOT_DIR="${SOCIAL_RUNTIME_SMOKE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVER_HOST="${DEPLOY_HOST:-root@80.78.242.105}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/localos_prod}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-https://localos.pro}"
SMOKE_ALLOW_UNSCOPED="${SOCIAL_SMOKE_ALLOW_UNSCOPED:-0}"
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
  cockpit_chunk="$(grep -R -l "Быстрый запуск публикаций" frontend/dist/assets 2>/dev/null | head -n 1 || true)"
  if [[ -z "$cockpit_chunk" ]]; then
    echo "Could not find current social cockpit copy in frontend/dist/assets" >&2
    exit 1
  fi
  echo "cockpit_chunk=${cockpit_chunk}"
  grep -F "контроль/вручную" "$cockpit_chunk" >/dev/null
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
