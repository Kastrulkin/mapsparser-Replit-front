from pathlib import Path
import gzip
import os
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "postgres-restore-latest.sh"


def _archive(tmp_path):
    path = tmp_path / "fixture.sql.gz"
    output = gzip.open(path, "wb")
    try:
        output.write(b"fixture")
    finally:
        output.close()
    return path


def _environment(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "docker-called"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == *\" -T \"* ]]; then echo invalid-docker-exec-flag >&2; exit 99; fi\n"
        "if [[ \"$*\" == *\"context inspect\"* ]]; then echo \"$FAKE_DOCKER_HOST\"; exit 0; fi\n"
        "if [[ \"$*\" == *\".State.Running\"* ]]; then echo \"$FAKE_IDENTITY\"; exit 0; fi\n"
        "if [[ \"$*\" == *\"NetworkSettings.Ports\"* ]]; then printf '%s\\n' \"$FAKE_PORTS\"; exit 0; fi\n"
        "if [[ \"$*\" == *\"SELECT EXISTS\"* ]]; then echo \"$FAKE_TARGET_EXISTS\"; exit 0; fi\n"
        "printf '%s\\n' \"$*\" >> \"$RESTORE_DOCKER_MARKER\"\n"
        "cat >/dev/null\n"
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["RESTORE_DOCKER_MARKER"] = str(marker)
    environment["FAKE_DOCKER_HOST"] = "unix:///tmp/fake.sock"
    environment["FAKE_IDENTITY"] = "true localos-readiness-test postgres"
    environment["FAKE_PORTS"] = "127.0.0.1:15417"
    environment["FAKE_TARGET_EXISTS"] = "f"
    return environment, marker


def _arguments(archive):
    target = "localos_restore_test"
    return [
        "--backup", str(archive),
        "--target-db", target,
        "--confirm-target", target,
        "--trusted-archive",
        "--docker-context", "local",
        "--container", "fake-postgres",
        "--compose-project", "localos-readiness-test",
        "--pg-user", "test-user",
    ]


def _run(arguments, environment):
    return subprocess.run(
        ["bash", str(HELPER), *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize(
    "mutation, environment_key, environment_value",
    [
        (("remove", "--trusted-archive", ""), "", ""),
        (("replace", "--confirm-target", "localos_restore_other"), "", ""),
        (("replace", "--target-db", "local"), "", ""),
        (("remove", "--pg-user", "test-user"), "", ""),
        (("keep", "", ""), "FAKE_DOCKER_HOST", "tcp://remote.example:2376"),
        (("keep", "", ""), "FAKE_IDENTITY", "true wrong-project postgres"),
        (("keep", "", ""), "FAKE_IDENTITY", "true localos-readiness-test worker"),
        (("keep", "", ""), "FAKE_IDENTITY", "false localos-readiness-test postgres"),
        (("keep", "", ""), "FAKE_PORTS", "127.0.0.1:15417\n0.0.0.0:15418"),
        (("keep", "", ""), "FAKE_TARGET_EXISTS", "t"),
    ],
)
def test_unsafe_restore_admission_never_creates_or_streams(tmp_path, mutation, environment_key, environment_value):
    archive = _archive(tmp_path)
    arguments = _arguments(archive)
    kind, flag, value = mutation
    if kind == "remove":
        index = arguments.index(flag)
        del arguments[index]
    elif kind == "replace":
        arguments[arguments.index(flag) + 1] = value
    environment, marker = _environment(tmp_path)
    if environment_key:
        environment[environment_key] = environment_value

    result = _run(arguments, environment)

    assert result.returncode != 0
    command = marker.read_text() if marker.exists() else ""
    assert "CREATE DATABASE" not in command
    assert "-d localos_restore_test" not in command
    assert "-T" not in command


def test_confirmed_local_empty_target_uses_valid_docker_exec_flags(tmp_path):
    archive = _archive(tmp_path)
    environment, marker = _environment(tmp_path)
    result = _run(_arguments(archive), environment)

    assert result.returncode == 0, result.stderr or result.stdout
    command = marker.read_text()
    assert "CREATE DATABASE" in command
    assert "exec -i fake-postgres psql" in command
    assert "-d localos_restore_test" in command
    assert "-T" not in command
