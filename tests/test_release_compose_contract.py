"""Static contract for the opt-in digest-pinned application release profile."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = ROOT / "docker-compose.release.yml"
APP_REPOSITORY = "registry.invalid/localos/app"
BOT_REPOSITORY = "registry.invalid/localos/telegram"
APP_DIGEST = "a" * 64
BOT_DIGEST = "b" * 64
POSTGRES_USER = "release_test"
POSTGRES_PASSWORD = "release_test_only"
POSTGRES_DATABASE = "release_test"
APP_ROLES = ("app", "worker", "operator-worker")
APP_TARGETS = {
    "/app/debug_data",
    "/app/debug_data/media_uploads",
    "/app/operator_audio",
}
BOT_TARGETS = {
    "/app/debug_data/media_uploads",
    "/app/operator_audio",
}


def environment(tmp_path: Path, values: dict[str, str] | None = None) -> dict[str, str]:
    result = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "COMPOSE_DISABLE_ENV_FILE": "1",
        "LOCALOS_RELEASE_IMAGE_REPOSITORY": APP_REPOSITORY,
        "LOCALOS_RELEASE_IMAGE_DIGEST": APP_DIGEST,
        "LOCALOS_TELEGRAM_RELEASE_IMAGE_REPOSITORY": BOT_REPOSITORY,
        "LOCALOS_TELEGRAM_RELEASE_IMAGE_DIGEST": BOT_DIGEST,
        "POSTGRES_USER": POSTGRES_USER,
        "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        "POSTGRES_DB": POSTGRES_DATABASE,
    }
    if values:
        result.update(values)
    return result


def compose_prefix() -> list[str] | None:
    override = os.environ.get("LOCALOS_COMPOSE_BINARY")
    if override:
        candidate = Path(override)
        if not candidate.is_file():
            pytest.fail("LOCALOS_COMPOSE_BINARY does not name a file")
        return [str(candidate)]
    standalone = shutil.which("docker-compose")
    if standalone:
        return [standalone]
    docker = shutil.which("docker")
    if docker:
        return [docker, "compose"]
    return None


def compose_command(
    tmp_path: Path,
    values: dict[str, str] | None = None,
    include_migrator: bool = False,
) -> subprocess.CompletedProcess[str]:
    prefix = compose_prefix()
    if prefix is None:
        pytest.skip("Docker Compose command is unavailable for the static render contract")
    version = subprocess.run(
        [*prefix, "version"],
        env=environment(tmp_path),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if version.returncode:
        pytest.fail("Docker Compose plugin is unavailable: " + version.stderr[-1000:])
    command = [
        *prefix,
        "--env-file", "/dev/null",
    ]
    if include_migrator:
        command.extend(("--profile", "release-migrate"))
    command.extend(
        [
            "-f", str(ROOT / "docker-compose.yml"),
            "-f", str(RELEASE_FILE),
            "config", "--format", "json",
        ]
    )
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment(tmp_path, values),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def rendered(tmp_path: Path, include_migrator: bool = False) -> dict[str, object]:
    result = compose_command(tmp_path, include_migrator=include_migrator)
    if result.returncode:
        pytest.fail("release Compose render failed: " + result.stderr[-1000:])
    return json.loads(result.stdout)


def service(config: dict[str, object], name: str) -> dict[str, object]:
    services = config.get("services")
    assert isinstance(services, dict)
    value = services.get(name)
    assert isinstance(value, dict)
    return value


def image(repository: str, digest: str) -> str:
    return repository + "@sha256:" + digest


def digest_pinned(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", value) is not None


def volume_targets(item: dict[str, object]) -> set[str]:
    volumes = item.get("volumes", [])
    assert isinstance(volumes, list)
    targets: set[str] = set()
    for volume in volumes:
        assert isinstance(volume, dict)
        assert volume.get("type") == "volume"
        target = volume.get("target")
        assert isinstance(target, str)
        targets.add(target)
    return targets


def test_template_has_literal_digest_separator_not_mutable_image_variable():
    text = RELEASE_FILE.read_text()
    assert "@sha256:${LOCALOS_RELEASE_IMAGE_DIGEST" in text
    assert "@sha256:${LOCALOS_TELEGRAM_RELEASE_IMAGE_DIGEST" in text
    assert "LOCALOS_RELEASE_IMAGE:?" not in text
    assert "LOCALOS_TELEGRAM_RELEASE_IMAGE:?" not in text


@pytest.mark.parametrize("key", ("LOCALOS_RELEASE_IMAGE_DIGEST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"))
def test_compose_rejects_missing_required_release_input(tmp_path: Path, key: str):
    result = compose_command(tmp_path, {key: ""})
    assert result.returncode != 0
    assert key in result.stderr


def test_malformed_digest_is_not_mistaken_for_a_digest_pin(tmp_path: Path):
    result = compose_command(tmp_path, {"LOCALOS_RELEASE_IMAGE_DIGEST": "latest"})
    assert result.returncode == 0
    config = json.loads(result.stdout)
    assert not digest_pinned(service(config, "app").get("image"))


def test_rendered_release_application_roles_have_no_build_or_bind_mount(tmp_path: Path):
    config = rendered(tmp_path)
    for name in APP_ROLES:
        item = service(config, name)
        assert item.get("image") == image(APP_REPOSITORY, APP_DIGEST)
        assert digest_pinned(item.get("image"))
        assert "build" not in item
        assert volume_targets(item) == APP_TARGETS
        environment_values = item.get("environment")
        assert isinstance(environment_values, dict)
        assert environment_values.get("LOCALOS_MIGRATION_MODE") == "schema-check-only"

    bot = service(config, "telegram-bot")
    assert bot.get("image") == image(BOT_REPOSITORY, BOT_DIGEST)
    assert digest_pinned(bot.get("image"))
    assert "build" not in bot
    assert bot.get("entrypoint") == []
    assert volume_targets(bot) == BOT_TARGETS
    bot_environment = bot.get("environment")
    assert isinstance(bot_environment, dict)
    assert "LOCALOS_MIGRATION_MODE" not in bot_environment


def test_rendered_release_has_single_profiled_migrator_and_no_bind_mounts(tmp_path: Path):
    ordinary_config = rendered(tmp_path)
    ordinary_services = ordinary_config.get("services")
    assert isinstance(ordinary_services, dict)
    assert "migrator" not in ordinary_services

    config = rendered(tmp_path, include_migrator=True)
    migrator = service(config, "migrator")
    assert migrator.get("image") == image(APP_REPOSITORY, APP_DIGEST)
    assert "build" not in migrator
    assert migrator.get("profiles") == ["release-migrate"]
    assert migrator.get("command") == ["true"]
    assert "volumes" not in migrator
    migration_environment = migrator.get("environment")
    app_environment = service(config, "app").get("environment")
    assert isinstance(migration_environment, dict)
    assert isinstance(app_environment, dict)
    assert migration_environment.get("LOCALOS_MIGRATION_MODE") == "migrate-only"
    for key in ("DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "FLASK_APP"):
        assert migration_environment.get(key) == app_environment.get(key)

    services = config.get("services")
    assert isinstance(services, dict)
    for name, item in services.items():
        assert isinstance(name, str)
        assert isinstance(item, dict)
        assert "build" not in item
        volume_targets(item)
