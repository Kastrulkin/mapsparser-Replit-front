#!/bin/sh
# Run the synthetic real-API browser slice on a fresh GitHub-hosted runner only.
set -eu

fail() {
  echo "ci_real_api_staging: $1" >&2
  exit 2
}

if [ "${GITHUB_ACTIONS:-}" != "true" ] || [ "${RUNNER_ENVIRONMENT:-}" != "github-hosted" ]; then
  fail "requires a fresh github-hosted runner"
fi

for key in \
  COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES \
  COMPOSE_DISABLE_ENV_FILE DOCKER_HOST DOCKER_CONTEXT DOCKER_CONFIG STAGING_PROJECT_NAME STAGING_PORT \
  JOURNEY_STAGING_BASE_URL LOCALOS_STAGING_BASE_URL JOURNEY_STAGING_CONTAINER \
  JOURNEY_STAGING_DATABASE_URL PLAYWRIGHT_BROWSERS_PATH \
  PGHOSTADDR PGSERVICE PGSERVICEFILE PGOPTIONS; do
  if [ -n "$(printenv "$key" 2>/dev/null || true)" ]; then
    fail "ambient override is forbidden: $key"
  fi
done

for key in \
  APIFY_TOKEN DEEPSEEK_API_KEY GIGACHAT_KEYS GIGACHAT_CLIENT_SECRET \
  GOOGLE_CLIENT_SECRET META_OAUTH_APP_SECRET OPENCLAW_TOKEN \
  OPENCLAW_LOCALOS_TOKEN OUTREACH_VK_SECRET_KEY TELEGRAM_BOT_TOKEN \
  WHATSAPP_APP_SECRET YANDEX_AI_API_KEY YANDEX_WORDSTAT_OAUTH_TOKEN \
  YOOKASSA_SECRET_KEY; do
  if [ -n "$(printenv "$key" 2>/dev/null || true)" ]; then
    fail "provider or production secret is forbidden: $key"
  fi
done

case "${GITHUB_RUN_ID:-}" in
  ''|*[!0-9]*) fail "GITHUB_RUN_ID must be numeric" ;;
esac
case "${GITHUB_RUN_ATTEMPT:-}" in
  ''|*[!0-9]*) fail "GITHUB_RUN_ATTEMPT must be numeric" ;;
esac

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case "$root" in
  *"\n"*|*"\r"*) fail "unsupported workspace path" ;;
esac
if [ -e "$root/.env" ]; then
  fail "repository .env is forbidden"
fi

project="localos-ci-e2e-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
artifact_dir="${RUNNER_TEMP:?RUNNER_TEMP is required}/localos-ci-real-api-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
docker_home="$artifact_dir/docker-home"
browser_path="$RUNNER_TEMP/ms-playwright"

mkdir -p "$docker_home"
chmod 700 "$docker_home"

compose() {
  env -i \
    PATH="$PATH" \
    HOME="$docker_home" \
    DOCKER_CONFIG="$docker_home/config" \
    COMPOSE_DISABLE_ENV_FILE=1 \
    docker compose --project-name "$project" --env-file /dev/null \
      -f "$root/docker-compose.yml" -f "$root/docker-compose.staging.yml" "$@"
}

docker_command() {
  env -i \
    PATH="$PATH" \
    HOME="$docker_home" \
    DOCKER_CONFIG="$docker_home/config" \
    docker "$@"
}

docker_inventory() {
  output="$(docker_command "$@" 2>/dev/null)" || {
    echo "ci_real_api_staging: Docker inventory failed" >&2
    return 1
  }
  printf '%s' "$output"
}

require_empty_inventory() {
  description="$1"
  shift
  resources="$("$@" 2>/dev/null)" || fail "cannot inspect $description"
  [ -z "$resources" ] || fail "refusing pre-existing $description"
}

verify_resource_label() {
  resource_type="$1"
  resource="$2"
  case "$resource_type" in
    container)
      label="$(docker_inventory inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$resource")" || return 1
      ;;
    volume)
      label="$(docker_inventory volume inspect --format '{{ index .Labels "com.docker.compose.project" }}' "$resource")" || return 1
      ;;
    network)
      label="$(docker_inventory network inspect --format '{{ index .Labels "com.docker.compose.project" }}' "$resource")" || return 1
      ;;
    *) return 1 ;;
  esac
  [ "$label" = "$project" ]
}

verify_exact_owned_name_if_present() {
  resource_type="$1"
  resource="$2"
  case "$resource_type" in
    volume) resources="$(docker_inventory volume ls -q --filter "name=^${resource}$")" || return 1 ;;
    network) resources="$(docker_inventory network ls -q --filter "name=^${resource}$")" || return 1 ;;
    *) return 1 ;;
  esac
  [ -z "$resources" ] || verify_resource_label "$resource_type" "$resource"
}

verify_exact_owned_container_if_present() {
  resource="$1"
  resources="$(docker_inventory ps -aq --filter "name=^/${resource}$")" || return 1
  [ -z "$resources" ] || verify_resource_label container "$resources"
}

verify_labelled_resources() {
  resources="$(docker_inventory ps -aq --filter "label=com.docker.compose.project=$project")" || return 1
  for resource in $resources; do
    verify_resource_label container "$resource" || return 1
  done
  resources="$(docker_inventory volume ls -q --filter "label=com.docker.compose.project=$project")" || return 1
  for resource in $resources; do
    verify_resource_label volume "$resource" || return 1
  done
  resources="$(docker_inventory network ls -q --filter "label=com.docker.compose.project=$project")" || return 1
  for resource in $resources; do
    verify_resource_label network "$resource" || return 1
  done
  verify_exact_owned_name_if_present volume "${project}_pgdata" || return 1
  verify_exact_owned_name_if_present volume "${project}_redisdata" || return 1
  verify_exact_owned_name_if_present network "${project}_default" || return 1
  verify_exact_owned_container_if_present "${project}-app-1" || return 1
  verify_exact_owned_container_if_present "${project}-postgres-1" || return 1
  verify_exact_owned_container_if_present "${project}-redis-1"
}

created_project=0
app_container=""
cancelled_signal=""

write_metadata() {
  mkdir -p "$artifact_dir"
  chmod 700 "$artifact_dir"
  printf '{"project":"%s","app_container_id":"%s","synthetic_only":true}\n' \
    "$project" "$app_container" > "$artifact_dir/metadata.json"
  chmod 600 "$artifact_dir/metadata.json"
}

cleanup() {
  result=$?
  trap - EXIT
  write_metadata
  if [ -n "$cancelled_signal" ]; then
    result=1
  fi
  if [ "$created_project" = "1" ]; then
    if ! verify_labelled_resources; then
      echo "ci_real_api_staging: refusing cleanup of resource outside owned project" >&2
      result=1
    else
      compose down --volumes --remove-orphans >/dev/null 2>&1 || {
        echo "ci_real_api_staging: owned project cleanup failed" >&2
        result=1
      }
    fi
  fi
  exit "$result"
}
on_signal() {
  cancelled_signal="$1"
  trap - INT TERM
  exit 1
}
trap cleanup EXIT
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM

cd "$root"
require_empty_inventory "compose project" compose ps -aq
require_empty_inventory "labelled volume" docker_command volume ls -q --filter "label=com.docker.compose.project=$project"
require_empty_inventory "labelled network" docker_command network ls -q --filter "label=com.docker.compose.project=$project"
require_empty_inventory "same-name pgdata volume" docker_command volume ls -q --filter "name=^${project}_pgdata$"
require_empty_inventory "same-name redisdata volume" docker_command volume ls -q --filter "name=^${project}_redisdata$"
require_empty_inventory "same-name default network" docker_command network ls -q --filter "name=^${project}_default$"
require_empty_inventory "same-name app container" docker_command ps -aq --filter "name=^/${project}-app-1$"
require_empty_inventory "same-name postgres container" docker_command ps -aq --filter "name=^/${project}-postgres-1$"
require_empty_inventory "same-name redis container" docker_command ps -aq --filter "name=^/${project}-redis-1$"

created_project=1
env -i \
  PATH="$PATH" \
  HOME="$docker_home" \
  DOCKER_CONFIG="$docker_home/config" \
  RUNNER_TEMP="$RUNNER_TEMP" \
  GITHUB_ACTIONS=true \
  RUNNER_ENVIRONMENT=github-hosted \
  GITHUB_RUN_ID="$GITHUB_RUN_ID" \
  GITHUB_RUN_ATTEMPT="$GITHUB_RUN_ATTEMPT" \
  COMPOSE_DISABLE_ENV_FILE=1 \
  PYTHON_DOTENV_DISABLED=1 \
  STAGING_PROJECT_NAME="$project" \
  STAGING_PORT=18000 \
  STAGING_SKIP_BUILD=false \
  sh "$root/scripts/staging_journey_up.sh"

app_container="$(compose ps -q app)"
[ -n "$app_container" ] || fail "owned app container is missing"
verify_resource_label container "$app_container" || fail "refusing fixture access outside owned project"
write_metadata

cd "$root/frontend"
env -i \
  PATH="$PATH" \
  HOME="$docker_home" \
  DOCKER_CONFIG="$docker_home/config" \
  RUNNER_TEMP="$RUNNER_TEMP" \
  GITHUB_ACTIONS=true \
  RUNNER_ENVIRONMENT=github-hosted \
  GITHUB_RUN_ID="$GITHUB_RUN_ID" \
  GITHUB_RUN_ATTEMPT="$GITHUB_RUN_ATTEMPT" \
  PLAYWRIGHT_BROWSERS_PATH="$browser_path" \
  JOURNEY_STAGING_BASE_URL="http://127.0.0.1:18000" \
  JOURNEY_STAGING_CONTAINER="$app_container" \
  npx --no-install playwright test \
  --config playwright.journey-staging.config.ts \
  --workers=1 \
  --reporter=line,html \
  e2e/staging/network-tenant.spec.ts \
  e2e/staging/owner-reviews-finance.spec.ts \
  e2e/staging/social-publication-reconciliation.spec.ts
