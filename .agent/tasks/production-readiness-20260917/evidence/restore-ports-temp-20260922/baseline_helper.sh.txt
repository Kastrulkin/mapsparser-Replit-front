#!/usr/bin/env bash
# Restore a trusted PostgreSQL .sql.gz archive into a fresh local disposable DB.
#
# This helper never starts Docker, never sources .env, and never selects a backup
# implicitly. A .sql.gz archive is executable SQL: use only a trusted archive.
#
# Usage:
#   ./scripts/postgres-restore-latest.sh --backup /absolute/path/archive.sql.gz
#     --target-db localos_restore_<suffix>
#     --confirm-target localos_restore_<suffix>
#     --trusted-archive
#     --docker-context <local-unix-context>
#     --container <owned-postgres-container>
#     --compose-project localos-readiness-<suffix>
#     --pg-user <database-user>

set -euo pipefail
cd "$(dirname "$0")/.."

fail() {
  echo "Restore refused: $*" >&2
  exit 1
}

backup_file=""
target_db=""
confirmed_target=""
docker_context=""
container=""
compose_project=""
pg_user=""
trusted_archive="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup) [[ $# -ge 2 ]] || fail "--backup requires a file"; backup_file="$2"; shift 2 ;;
    --target-db) [[ $# -ge 2 ]] || fail "--target-db requires a database name"; target_db="$2"; shift 2 ;;
    --confirm-target) [[ $# -ge 2 ]] || fail "--confirm-target requires a database name"; confirmed_target="$2"; shift 2 ;;
    --trusted-archive) trusted_archive="true"; shift ;;
    --docker-context) [[ $# -ge 2 ]] || fail "--docker-context requires a context"; docker_context="$2"; shift 2 ;;
    --container) [[ $# -ge 2 ]] || fail "--container requires a container"; container="$2"; shift 2 ;;
    --compose-project) [[ $# -ge 2 ]] || fail "--compose-project requires a project"; compose_project="$2"; shift 2 ;;
    --pg-user) [[ $# -ge 2 ]] || fail "--pg-user requires a user"; pg_user="$2"; shift 2 ;;
    --help|-h) sed -n '1,16p' "$0"; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$backup_file" && -n "$target_db" && -n "$confirmed_target" ]] || fail "explicit backup, target, and confirmation are required"
[[ -n "$docker_context" && -n "$container" && -n "$compose_project" && -n "$pg_user" ]] || fail "explicit local Docker identity and database user are required"
[[ "$trusted_archive" == "true" ]] || fail "--trusted-archive acknowledgment is required"
[[ "$confirmed_target" == "$target_db" ]] || fail "--confirm-target must exactly match --target-db"
[[ -f "$backup_file" && "$backup_file" == *.sql.gz ]] || fail "backup must be an existing .sql.gz archive"
[[ "$target_db" =~ ^(localos_restore_|localos_readiness_restore_)[a-z0-9_]+$ ]] || fail "target database must be disposable"
[[ "$compose_project" =~ ^(localos-readiness-|localos-restore-)[a-z0-9_-]+$ ]] || fail "compose project must be an explicit local restore/readiness project"

docker_host="$(docker context inspect "$docker_context" --format '{{.Endpoints.docker.Host}}')"
[[ "$docker_host" == unix://* ]] || fail "Docker context must use a local Unix socket"
identity="$(docker --context "$docker_context" inspect "$container" --format '{{.State.Running}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}}')"
[[ "$identity" == "true $compose_project postgres" ]] || fail "container identity is not the requested owned postgres service"
ports="$(docker --context "$docker_context" inspect "$container" --format '{{range (index .NetworkSettings.Ports "5432/tcp")}}{{.HostIp}}:{{.HostPort}}{{"\n"}}{{end}}')"
[[ -n "$ports" ]] || fail "owned postgres service must publish PostgreSQL to loopback"
while IFS= read -r binding; do
  [[ "$binding" =~ ^127\.0\.0\.1:[0-9]+$ ]] || fail "owned postgres service must publish only to loopback"
done <<< "$ports"

target_exists="$(docker --context "$docker_context" exec "$container" psql -U "$pg_user" -d postgres -Atqc "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$target_db')")"
[[ "$target_exists" == "f" ]] || fail "fresh disposable target must not already exist"
docker --context "$docker_context" exec "$container" psql -v ON_ERROR_STOP=1 -U "$pg_user" -d postgres -c "CREATE DATABASE \"$target_db\""

echo "Restoring trusted archive into confirmed fresh disposable target $target_db..."
gunzip -c "$backup_file" | docker --context "$docker_context" exec -i "$container" psql -v ON_ERROR_STOP=1 -U "$pg_user" -d "$target_db"
echo "Restore stream completed. Verify schema and data before using the target."
