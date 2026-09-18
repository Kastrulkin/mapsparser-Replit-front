# Opt-in immutable application Compose profile

[`docker-compose.release.yml`](../../docker-compose.release.yml) is a local
immutable application release-profile contract. It is not the default deployment configuration and
does not change a running environment by itself.

## Inputs

Use separate repository and digest variables for the application image and the
Telegram image. The Compose file itself places the literal `@sha256:` between
each pair, so a rendered reference cannot fall back to a mutable tag. This
pins application images only: PostgreSQL and Redis remain the tagged base
Compose infrastructure images and need a separate supply-chain gate.

```sh
LOCALOS_RELEASE_IMAGE_REPOSITORY=registry.example/localos/app \
LOCALOS_RELEASE_IMAGE_DIGEST='<64-lowercase-hex-from-release-manifest>' \
LOCALOS_TELEGRAM_RELEASE_IMAGE_REPOSITORY=registry.example/localos/telegram \
LOCALOS_TELEGRAM_RELEASE_IMAGE_DIGEST='<64-lowercase-hex-from-release-manifest>' \
POSTGRES_USER='<approved-release-db-user>' \
POSTGRES_PASSWORD='<approved-release-db-password>' \
POSTGRES_DB='<approved-release-db-name>' \
docker compose --env-file /dev/null \
  -f docker-compose.yml -f docker-compose.release.yml config --quiet
```

The repository variables can include a registry path. A malformed digest is an
invalid Docker image reference; it is not a request to use a tag. The static
contract proves the rendered malformed value is not mistaken for a digest pin;
Docker performs final image-reference validation when runtime use is approved.
Before that use, the release owner must verify the exact resolved image
identities with the configured registry/runtime tooling. The profile also requires all
three PostgreSQL connection variables explicitly; it does not fall back to the
base profile's local default credentials. Supply approved secrets through the
release environment mechanism; do not paste a real password into shell history
or a command log. `config --quiet` validates the merge without printing the
rendered environment, which can contain inherited provider and database
secrets.

## Runtime roles

Ordinary `app`, `worker`, and `operator-worker` roles use
`LOCALOS_MIGRATION_MODE=schema-check-only`. The only migration owner is the
separate `migrator` service, which is enabled only with the
`release-migrate` profile and uses `migrate-only`. The Telegram bot retains its
existing no-entrypoint behavior and does not run startup migrations.

The profile removes source, migrations, entrypoint, scripts, and frontend bind
mounts. It uses only named runtime data volumes for debug data, uploads, and
operator audio; PostgreSQL and Redis retain their existing named data volumes.

Only the merge of `docker-compose.yml` plus `docker-compose.release.yml` is
covered here. Optional worker, compiled-runner, staging, test, and proxy
fragments are outside this profile contract.

Those new runtime volumes begin empty. Switching an existing environment that
uses host `debug_data`, uploads, or audio bind mounts requires a separately
approved backup and data-transfer plan. Do not apply this profile over a live
environment merely to test it.

## What the static contract proves

[`tests/test_release_compose_contract.py`](../../tests/test_release_compose_contract.py)
renders base Compose plus this override with fake digest values and asserts the
merged service graph has no builds or bind mounts, uses digest-shaped
application image references, and has exactly one profile-gated migrator. It
also demonstrates missing input failure and that malformed input is not a
digest-shaped reference. It does not start containers, pull images, run
migrations, or prove that a release image, rollback, infrastructure images, or
existing data transfer works. Those remain separate approved runtime gates.
