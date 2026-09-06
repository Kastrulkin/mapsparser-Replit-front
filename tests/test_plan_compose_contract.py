"""Render the actual Compose merge; do not read local env files or start services."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FLAGS = {
    "LOCALOS_TODAY_PERSONALIZATION_ENABLED": "true",
    "LOCALOS_TODAY_ACTIVITY_ENABLED": "false",
    "LOCALOS_TODAY_PROPOSALS_ENABLED": "false",
}


@pytest.mark.parametrize("override", [False, True])
def test_rendered_compose_passes_today_and_compiled_flags_to_the_actual_owners(override):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI is required to render the release configuration")
    digest = "sha256:" + "a" * 64
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
           "COMPILED_SCRIPT_RUNNER_IMAGE": "registry.example/runner@" + digest,
           "COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST": digest,
           "COMPILED_SCRIPT_RUNNER_SHARED_SECRET": "synthetic-compose-contract-secret"}
    expected = {key: ("false" if value == "true" else "true") for key, value in FLAGS.items()} if override else FLAGS
    if override:
        env.update(expected)
        env.update({"COMPILED_SCRIPT_PREVIEW_ENABLED": "true", "COMPILED_SCRIPT_EXECUTE_ENABLED": "true",
                    "COMPILED_SCRIPT_PILOT_BUSINESS_IDS": "synthetic-business",
                    "LOCALOS_MIGRATION_MODE": "schema-check-only"})
    process = subprocess.run([docker, "compose", "--env-file", "/dev/null",
        "-f", "docker-compose.yml", "-f", "docker-compose.workers.yml",
        "-f", "docker/compiled-script-runner/compose.fragment.yml", "config", "--no-env-resolution", "--format", "json"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
    assert process.returncode == 0, "Compose rendering failed; credentials and rendered config are intentionally omitted"
    config = json.loads(process.stdout)
    for service in ("app", "worker", "worker-agent", "worker-maintenance"):
        actual = config["services"][service]
        assert actual["environment"].get("LOCALOS_MIGRATION_MODE") == ("schema-check-only" if override else "startup")
        mounted = {volume["target"]: volume for volume in actual["volumes"]}
        for script in ("localos_migrator.py", "check_content_learning_schema.py"):
            volume = mounted.get("/app/scripts/" + script)
            assert volume is not None, "Partial deploy must survive recreate of a previously built image"
            assert volume["type"] == "bind" and volume["read_only"] is True
            assert Path(volume["source"]) == ROOT / "scripts" / script
    for service in ("app", "worker", "worker-maintenance"):
        actual = config["services"][service]["environment"]
        assert {key: actual.get(key) for key in FLAGS} == expected
    for service in ("app", "worker", "worker-agent"):
        actual = config["services"][service]["environment"]
        assert actual["COMPILED_SCRIPT_PREVIEW_ENABLED"] == ("true" if override else "false")
        assert actual["COMPILED_SCRIPT_EXECUTE_ENABLED"] == ("true" if override else "false")
        assert actual["COMPILED_SCRIPT_PILOT_BUSINESS_IDS"] == ("synthetic-business" if override else "")
        assert actual["COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST"] == digest
    assert config["networks"]["compiled_script_internal"]["internal"] is True
    runner = config["services"]["compiled-script-runner"]
    assert config["services"]["app"]["environment"]["COMPILED_SCRIPT_ADVANCED_ENABLED"] == "false"
    assert set(runner["networks"]) == {"compiled_script_internal"}
    assert not runner.get("ports") and not runner.get("build")
