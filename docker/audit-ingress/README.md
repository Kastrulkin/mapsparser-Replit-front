# Compiled staging ingress

This profile is only for the local, synthetic compiled-table proof. It is not a
production deployment command and must never be pointed at a production
database, container, Compose project, provider credential, or business.

The exact Compose chain is:

```sh
docker compose --env-file /dev/null \
  -f docker-compose.yml \
  -f docker-compose.workers.yml \
  -f docker-compose.staging.yml \
  -f docker/compiled-script-runner/compose.fragment.yml \
  -f docker-compose.compiled-staging.yml
```

Use a fresh project name and an empty environment. Supply only an already
verified immutable runner image reference, its matching digest, and a freshly
generated local shared secret. Do not read `.env` files.

```sh
project_name='localos-compiled-staging-local'
runner_image='registry.example/compiled-runner@sha256:replace_with_verified_digest'
runner_digest='sha256:replace_with_verified_digest'
runner_secret="$(openssl rand -hex 32)"
docker_host="${DOCKER_HOST:-}"
if [ -z "$docker_host" ]; then
  docker_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
fi
case "$docker_host" in
  unix://*) ;;
  *) echo 'A local Unix Docker context is required.' >&2; exit 1 ;;
esac

compose() {
  env -i PATH="$PATH" HOME="$HOME" DOCKER_HOST="$docker_host" \
    COMPILED_SCRIPT_RUNNER_IMAGE="$runner_image" \
    COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST="$runner_digest" \
    COMPILED_SCRIPT_RUNNER_SHARED_SECRET="$runner_secret" \
    COMPILED_STAGING_PORT=18017 \
    COMPILED_STAGING_EXECUTE_ENABLED="${COMPILED_STAGING_EXECUTE_ENABLED:-false}" \
    COMPILED_STAGING_ADVANCED_ENABLED="${COMPILED_STAGING_ADVANCED_ENABLED:-false}" \
    COMPILED_STAGING_PILOT_BUSINESS_IDS="${COMPILED_STAGING_PILOT_BUSINESS_IDS:-}" \
    docker compose --env-file /dev/null -p "$project_name" \
      -f docker-compose.yml \
      -f docker-compose.workers.yml \
      -f docker-compose.staging.yml \
      -f docker/compiled-script-runner/compose.fragment.yml \
      -f docker-compose.compiled-staging.yml "$@"
}
```

There is no bare `up` command in this procedure. Phase one starts exactly the
synthetic database, Redis and app, then seeds the synthetic fixture:

```sh
compose up -d postgres redis app
compose exec -T app python /app/scripts/seed_journey_staging.py
business_id="$(compose exec -T app python -c 'from scripts.staging_fixture_cli import owner_business_id; print(owner_business_id())')"
```

Inspect `business_id` before continuing. It must be one returned synthetic
UUID, never `*`, a comma-separated cohort, or an existing production business.
Phase two enables the exact cohort and recreates only the app before starting
the runner and loopback ingress:

```sh
export COMPILED_STAGING_EXECUTE_ENABLED=true
export COMPILED_STAGING_ADVANCED_ENABLED=true
export COMPILED_STAGING_PILOT_BUSINESS_IDS="$business_id"
compose up -d --force-recreate app compiled-script-runner audit-ingress
```

The only services started by this proof are `postgres`, `redis`, `app`,
`compiled-script-runner` and `audit-ingress`. Worker, dispatcher, operator and
Telegram bot variants are disabled through a profile and must not be enabled.

`audit-ingress` exposes only `127.0.0.1:18017` and its fixed code forwards only
to `app:8000`; it has no credentials or arbitrary-upstream option. Its
host-access network still permits network egress, so this is not a global
no-egress guarantee. The app-to-Postgres and app-to-runner paths are internal
Docker networks; the extra ingress network exists solely for loopback host
access.
