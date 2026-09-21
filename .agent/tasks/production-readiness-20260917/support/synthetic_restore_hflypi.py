#!/usr/bin/env python3
"""Verify one explicitly owned, synthetic PostgreSQL backup/restore rehearsal.

This verifier is deliberately fixed to the hflypi audit resources.  It refuses
to select a Compose project, container, database, archive, or evidence path
from the environment or command line.  It neither reads .env nor starts,
stops, removes, or prunes Docker resources.

Run only after the root audit coordinator has created and migrated the source
database in the named isolated PostgreSQL container.  It creates one clearly
named audit probe table in that source database and delegates creation of the
fresh restore target to the repository's guarded restore helper. The explicit
``--verify-existing`` mode only reads that fixed database pair and archive,
then writes verification evidence; it does not recreate or change database data.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
SOURCE_ROOT = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source")
EVIDENCE_DIR = SOURCE_ROOT.parent / "evidence"
EVIDENCE_PATH = EVIDENCE_DIR / "synthetic-restore-hflypi.json"
ARCHIVE_PATH = SOURCE_ROOT.parent / "synthetic-restore-hflypi-source.sql.gz"
ARCHIVE_PART_PATH = SOURCE_ROOT.parent / "synthetic-restore-hflypi-source.sql.gz.part"

DOCKER_CONTEXT = "desktop-linux"
COMPOSE_PROJECT = "localos-readiness-hflypi"
POSTGRES_CONTAINER = "localos-readiness-hflypi-postgres-1"
INTERNAL_NETWORK = "localos-readiness-hflypi_internal"
INGRESS_NETWORK = "localos-readiness-hflypi_pg_ingress"
POSTGRES_VOLUME = "localos-readiness-hflypi-pgdata"
AUDIT_OWNER_LABEL = "production-readiness-20260917-hfLYPi"
SOURCE_DATABASE = "readiness_hflypi"
TARGET_DATABASE = "localos_readiness_restore_hflypi"
PG_USER = "audit_owner"
SYNTHETIC_PASSWORD = "hflypi-local-only"
APP_IMAGE = "localos-audit-20260921:99849935-hflypi"
EXPECTED_HEAD = "20260907_001"
PROBE_TABLE = "audit_restore_probe"
MAX_DUMP_BYTES = 512 * 1024 * 1024
MAX_CAPTURE_BYTES = 128 * 1024


class VerificationError(RuntimeError):
    """An admission or semantic comparison condition failed."""


def _redacted_command(arguments: list[str]) -> list[str]:
    redacted = list(arguments)
    for index, value in enumerate(redacted):
        if value == SYNTHETIC_PASSWORD:
            redacted[index] = "<synthetic-password>"
    return redacted


def run(
    arguments: list[str],
    *,
    timeout: int = 60,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            env={
                "PATH": "/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                "HOME": str(Path.home()),
                "TMPDIR": str(SOURCE_ROOT.parent),
                "LANG": "C",
            },
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        error = sys.exception()
        raise VerificationError(
            "command timed out after " + str(timeout) + "s: " + " ".join(_redacted_command(arguments))
        ) from error
    if check and completed.returncode != 0:
        stdout = completed.stdout[:MAX_CAPTURE_BYTES].decode("utf-8", "replace")
        stderr = completed.stderr[:MAX_CAPTURE_BYTES].decode("utf-8", "replace")
        raise VerificationError(
            "command failed: "
            + " ".join(_redacted_command(arguments))
            + "\nstdout:\n"
            + stdout
            + "\nstderr:\n"
            + stderr
        )
    return completed


def docker(*arguments: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return run(["docker", "--context", DOCKER_CONTEXT, *arguments], timeout=timeout, check=check)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def decode(completed: subprocess.CompletedProcess[bytes]) -> str:
    return completed.stdout.decode("utf-8", "replace").strip()


def inspect_json(*arguments: str) -> Any:
    payload = decode(docker(*arguments))
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        error = sys.exception()
        raise VerificationError("Docker inspect returned invalid JSON") from error


def psql(database: str, query: str) -> str:
    result = docker(
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        PG_USER,
        "-d",
        database,
        "-At",
        "-c",
        query,
        timeout=90,
    )
    return decode(result)


def query_lines(database: str, query: str) -> list[str]:
    output = psql(database, query)
    return [] if not output else output.splitlines()


def verify_fixed_inputs(verify_existing: bool = False) -> None:
    require(SOURCE_ROOT.is_dir(), "frozen source directory is missing")
    require((SOURCE_ROOT / "Dockerfile").is_file(), "frozen source has no Dockerfile")
    require((SOURCE_ROOT / "scripts" / "postgres-restore-latest.sh").is_file(), "frozen source has no restore helper")
    require(not (SOURCE_ROOT / ".env").exists(), "frozen source must not contain .env")
    require(not EVIDENCE_PATH.exists(), "refusing to overwrite existing evidence")
    if verify_existing:
        require(ARCHIVE_PATH.is_file(), "existing verification requires the retained archive")
    else:
        require(not ARCHIVE_PATH.exists(), "refusing to overwrite existing trusted archive")
    require(not ARCHIVE_PART_PATH.exists(), "refusing to overwrite unfinished archive")
    require(APP_IMAGE == "localos-audit-20260921:99849935-hflypi", "unexpected application image")
    require(SYNTHETIC_PASSWORD == "hflypi-local-only", "unexpected synthetic credential")


def verify_container_ownership() -> dict[str, Any]:
    context_host = decode(run(["docker", "context", "inspect", DOCKER_CONTEXT, "--format", "{{.Endpoints.docker.Host}}"])).strip()
    require(context_host.startswith("unix://"), "Docker context must resolve to a local Unix socket")

    inspected = inspect_json("inspect", POSTGRES_CONTAINER)
    require(isinstance(inspected, list) and len(inspected) == 1, "expected exactly one PostgreSQL inspect object")
    container = inspected[0]
    require(container.get("Name") == "/" + POSTGRES_CONTAINER, "unexpected PostgreSQL container name")
    require(container.get("State", {}).get("Running") is True, "owned PostgreSQL container is not running")
    labels = container.get("Config", {}).get("Labels", {})
    require(labels.get("com.docker.compose.project") == COMPOSE_PROJECT, "container has wrong Compose project label")
    require(labels.get("com.docker.compose.service") == "postgres", "container is not Compose postgres service")
    require(labels.get("localos.audit.owner") == AUDIT_OWNER_LABEL, "container has wrong audit ownership label")

    bindings = container.get("NetworkSettings", {}).get("Ports", {}).get("5432/tcp")
    require(isinstance(bindings, list) and bindings, "owned PostgreSQL must publish 5432")
    for binding in bindings:
        require(binding.get("HostIp") == "127.0.0.1", "PostgreSQL must publish only to loopback")
        require(binding.get("HostPort") == "35418", "PostgreSQL must publish the fixed audit loopback port 35418")

    networks = container.get("NetworkSettings", {}).get("Networks", {})
    require(set(networks) == {INTERNAL_NETWORK, INGRESS_NETWORK}, "PostgreSQL network set differs from the fixed audit topology")
    network_details: dict[str, Any] = {}
    for network_name, internal in ((INTERNAL_NETWORK, True), (INGRESS_NETWORK, False)):
        network = inspect_json("network", "inspect", network_name)
        require(isinstance(network, list) and len(network) == 1, "expected exactly one owned network")
        network_data = network[0]
        network_labels = network_data.get("Labels", {})
        require(network_labels.get("com.docker.compose.project") == COMPOSE_PROJECT, "network has wrong Compose project label")
        require(network_labels.get("localos.audit.owner") == AUDIT_OWNER_LABEL, "network has wrong audit ownership label")
        require(network_data.get("Internal") is internal, "network internal setting differs from fixed audit topology")
        network_details[network_name] = {"internal": internal, "id": network_data.get("Id")}

    mounts = container.get("Mounts", [])
    require(len(mounts) == 1 and mounts[0].get("Type") == "volume", "PostgreSQL must use exactly one named volume")
    volume_name = mounts[0].get("Name", "")
    require(volume_name == POSTGRES_VOLUME, "PostgreSQL volume name differs from fixed audit volume")
    require(mounts[0].get("Destination") == "/var/lib/postgresql/data", "PostgreSQL volume has unexpected destination")
    volume = inspect_json("volume", "inspect", volume_name)
    require(isinstance(volume, list) and len(volume) == 1, "expected exactly one PostgreSQL volume")
    volume_labels = volume[0].get("Labels", {})
    require(volume_labels.get("com.docker.compose.project") == COMPOSE_PROJECT, "PostgreSQL volume has wrong Compose project label")
    require(volume_labels.get("localos.audit.owner") == AUDIT_OWNER_LABEL, "PostgreSQL volume has wrong audit ownership label")
    return {
        "docker_context_host": context_host,
        "postgres_volume": volume_name,
        "loopback_bindings": bindings,
        "networks": network_details,
    }


def verify_database_admission(verify_existing: bool = False) -> dict[str, Any]:
    source_exists = psql("postgres", "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'readiness_hflypi')")
    target_exists = psql("postgres", "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'localos_readiness_restore_hflypi')")
    require(source_exists == "t", "synthetic source database is absent")
    require(target_exists == ("t" if verify_existing else "f"), "restore target existence differs from requested mode")
    source_owner = psql(
        "postgres",
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'readiness_hflypi'",
    )
    require(source_owner == PG_USER, "synthetic source database must be owned by audit_owner")
    versions = query_lines(SOURCE_DATABASE, "SELECT version_num FROM alembic_version ORDER BY version_num")
    require(versions == [EXPECTED_HEAD], "source schema revision must be exactly " + EXPECTED_HEAD)
    return {
        "source_alembic_versions": versions,
        "source_database_owner": source_owner,
        "target_preexisting": target_exists,
    }


def add_and_verify_probe() -> dict[str, Any]:
    psql(
        SOURCE_DATABASE,
        "CREATE TABLE audit_restore_probe ("
        "id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
        "payload TEXT NOT NULL"
        ")",
    )
    psql(
        SOURCE_DATABASE,
        "INSERT INTO audit_restore_probe(payload) VALUES ('duplicate-payload'), ('duplicate-payload')",
    )
    rows = psql(
        SOURCE_DATABASE,
        "SELECT payload || '|' || COUNT(*) FROM audit_restore_probe GROUP BY payload ORDER BY payload",
    )
    sequence = psql(
        SOURCE_DATABASE,
        "SELECT last_value || '|' || is_called FROM audit_restore_probe_id_seq",
    )
    require(rows == "duplicate-payload|2", "source audit probe did not preserve duplicate rows")
    require(sequence == "2|true", "source audit probe sequence is unexpected")
    return {"probe_rows": rows, "probe_sequence": sequence}


def dump_source_archive() -> dict[str, Any]:
    command = [
        "docker",
        "--context",
        DOCKER_CONTEXT,
        "exec",
        POSTGRES_CONTAINER,
        "pg_dump",
        "-U",
        PG_USER,
        "-d",
        SOURCE_DATABASE,
        "-Fp",
    ]
    completed = run(command, timeout=180)
    require(len(completed.stdout) <= MAX_DUMP_BYTES, "source dump exceeded fixed 512 MiB bound")
    digest = hashlib.sha256(completed.stdout)
    output = gzip.open(ARCHIVE_PART_PATH, "wb")
    try:
        output.write(completed.stdout)
    finally:
        output.close()
    archive = gzip.open(ARCHIVE_PART_PATH, "rb")
    try:
        while archive.read(1024 * 1024):
            pass
    finally:
        archive.close()
    os.replace(ARCHIVE_PART_PATH, ARCHIVE_PATH)
    archive_digest = hashlib.sha256()
    archive = ARCHIVE_PATH.open("rb")
    try:
        while True:
            chunk = archive.read(1024 * 1024)
            if not chunk:
                break
            archive_digest.update(chunk)
    finally:
        archive.close()
    return {
        "archive_path": str(ARCHIVE_PATH),
        "archive_bytes": ARCHIVE_PATH.stat().st_size,
        "archive_sha256": archive_digest.hexdigest(),
        "plain_dump_sha256": digest.hexdigest(),
    }


def run_restore_helper() -> None:
    helper = SOURCE_ROOT / "scripts" / "postgres-restore-latest.sh"
    run(
        [
            "bash",
            str(helper),
            "--backup",
            str(ARCHIVE_PATH),
            "--target-db",
            TARGET_DATABASE,
            "--confirm-target",
            TARGET_DATABASE,
            "--trusted-archive",
            "--docker-context",
            DOCKER_CONTEXT,
            "--container",
            POSTGRES_CONTAINER,
            "--compose-project",
            COMPOSE_PROJECT,
            "--pg-user",
            PG_USER,
        ],
        timeout=240,
    )


def normalized_dump(database: str, *, data_only: bool) -> bytes:
    options = ["--data-only", "--inserts"] if data_only else ["--schema-only"]
    result = docker(
        "exec",
        POSTGRES_CONTAINER,
        "pg_dump",
        "-U",
        PG_USER,
        "-d",
        database,
        "-Fp",
        *options,
        timeout=180,
    )
    lines = result.stdout.splitlines(keepends=True)
    normalized = [line for line in lines if not line.startswith(b"\\restrict ") and not line.startswith(b"\\unrestrict ")]
    payload = b"".join(normalized)
    require(len(payload) <= MAX_DUMP_BYTES, "comparison dump exceeded fixed 512 MiB bound")
    return payload


def catalog_manifest(database: str) -> list[str]:
    return query_lines(
        database,
        "WITH objects(kind, amount) AS ("
        " SELECT 'tables', COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        " WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema') "
        " UNION ALL SELECT 'indexes', COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        " WHERE c.relkind='i' AND n.nspname NOT IN ('pg_catalog','information_schema') "
        " UNION ALL SELECT 'sequences', COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        " WHERE c.relkind='S' AND n.nspname NOT IN ('pg_catalog','information_schema') "
        " UNION ALL SELECT 'views', COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        " WHERE c.relkind='v' AND n.nspname NOT IN ('pg_catalog','information_schema') "
        " UNION ALL SELECT 'functions', COUNT(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        " WHERE n.nspname NOT IN ('pg_catalog','information_schema')"
        " UNION ALL SELECT 'constraints', COUNT(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace "
        " WHERE n.nspname NOT IN ('pg_catalog','information_schema')"
        " UNION ALL SELECT 'triggers', COUNT(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        " JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal "
        " AND n.nspname NOT IN ('pg_catalog','information_schema')"
        " UNION ALL SELECT 'extensions', COUNT(*) FROM pg_extension"
        ") SELECT kind || '|' || amount FROM objects ORDER BY kind",
    )


def quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quoted_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def logical_data(database: str) -> dict[str, str]:
    """Stable multisets of complete typed rows; preserve duplicate multiplicity."""
    objects = json.loads(psql(
        database,
        "SELECT COALESCE(json_agg(json_build_array(n.nspname,c.relname,c.relkind) "
        "ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.relkind IN ('r','S') AND n.nspname NOT LIKE 'pg_%' "
        "AND n.nspname <> 'information_schema'",
    ))
    tables = []
    sequences = []
    for schema, name, kind in objects:
        qualified = quoted_identifier(schema) + '.' + quoted_identifier(name)
        identity = quoted_literal(qualified)
        if kind == 'r':
            tables.append(
                "SELECT " + identity + " object_name, row_to_json(audit_row)::text row_value FROM "
                + qualified + " audit_row"
            )
        else:
            sequences.append(
                "SELECT " + identity + " object_name, last_value::text || '|' || is_called::text row_value FROM "
                + qualified
            )
    payloads = {'objects': json.dumps(objects, ensure_ascii=False)}
    for label, queries in (('rows', tables), ('sequences', sequences)):
        payloads[label] = psql(
            database,
            "SELECT object_name || '|' || row_value FROM (" + " UNION ALL ".join(queries)
            + ') audit_values ORDER BY object_name COLLATE "C", row_value COLLATE "C"',
        ) if queries else ''
    return payloads


def compare_logical_data(source: dict[str, str], target: dict[str, str]) -> None:
    require(source['objects'] == target['objects'], 'table/sequence identities differ after restore')
    require(source['rows'] == target['rows'], 'complete row multisets differ after restore')
    require(source['sequences'] == target['sequences'], 'sequence values/is_called differ after restore')


def verify_restored_target() -> dict[str, Any]:
    target_owner = psql(
        "postgres",
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'localos_readiness_restore_hflypi'",
    )
    require(target_owner == PG_USER, "restored target database must be owned by audit_owner")
    versions = query_lines(TARGET_DATABASE, "SELECT version_num FROM alembic_version ORDER BY version_num")
    require(versions == [EXPECTED_HEAD], "restored target schema revision must be exactly " + EXPECTED_HEAD)
    rows = psql(
        TARGET_DATABASE,
        "SELECT payload || '|' || COUNT(*) FROM audit_restore_probe GROUP BY payload ORDER BY payload",
    )
    sequence = psql(
        TARGET_DATABASE,
        "SELECT last_value || '|' || is_called FROM audit_restore_probe_id_seq",
    )
    require(rows == "duplicate-payload|2", "restored target lost duplicate probe rows")
    require(sequence == "2|true", "restored target probe sequence is unexpected")

    source_schema = normalized_dump(SOURCE_DATABASE, data_only=False)
    target_schema = normalized_dump(TARGET_DATABASE, data_only=False)
    require(source_schema == target_schema, "schema dumps differ after removing only pg_dump restrict tokens")
    source_data = logical_data(SOURCE_DATABASE)
    target_data = logical_data(TARGET_DATABASE)
    compare_logical_data(source_data, target_data)
    source_manifest = catalog_manifest(SOURCE_DATABASE)
    target_manifest = catalog_manifest(TARGET_DATABASE)
    require(source_manifest == target_manifest, "catalog object counts differ after restore")
    return {
        "target_alembic_versions": versions,
        "target_database_owner": target_owner,
        "target_probe_rows": rows,
        "target_probe_sequence": sequence,
        "schema_dump_sha256": hashlib.sha256(source_schema).hexdigest(),
        "logical_data_sha256": {
            key: hashlib.sha256(value.encode('utf-8')).hexdigest()
            for key, value in source_data.items()
        },
        "data_comparison": "Exact ordered complete row_to_json text multisets via UNION ALL; all sequence last_value/is_called; no duplicate removal.",
        "catalog_manifest": source_manifest,
    }


def write_evidence(payload: dict[str, Any]) -> None:
    EVIDENCE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not EVIDENCE_PATH.exists(), "refusing to overwrite existing evidence")
    temporary = EVIDENCE_PATH.with_suffix(".json.part")
    require(not temporary.exists(), "refusing to overwrite unfinished evidence")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, EVIDENCE_PATH)


def main() -> int:
    require(sys.argv[1:] in ([], ['--verify-existing']), 'only fixed --verify-existing mode is supported')
    verify_existing = sys.argv[1:] == ['--verify-existing']
    started = time.time()
    evidence: dict[str, Any] = {
        "kind": "synthetic_postgres_backup_restore",
        "source_root": str(SOURCE_ROOT),
        "docker_context": DOCKER_CONTEXT,
        "compose_project": COMPOSE_PROJECT,
        "postgres_container": POSTGRES_CONTAINER,
        "internal_network": INTERNAL_NETWORK,
        "ingress_network": INGRESS_NETWORK,
        "postgres_volume": POSTGRES_VOLUME,
        "source_database": SOURCE_DATABASE,
        "target_database": TARGET_DATABASE,
        "application_image": APP_IMAGE,
        "expected_head": EXPECTED_HEAD,
        "normalization": "Schema: only pg_dump \\restrict/\\unrestrict lines removed. Data: ordered complete row multisets and sequence state.",
        "mode": 'read_only_verify_existing_restore' if verify_existing else 'create_and_verify_restore',
        "probe_table": PROBE_TABLE,
    }
    verify_fixed_inputs(verify_existing)
    evidence["ownership"] = verify_container_ownership()
    evidence["admission"] = verify_database_admission(verify_existing)
    if verify_existing:
        evidence['archive'] = {
            'archive_path': str(ARCHIVE_PATH), 'archive_bytes': ARCHIVE_PATH.stat().st_size,
            'archive_sha256': hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest(),
        }
        archive = gzip.open(ARCHIVE_PATH, 'rb')
        try:
            while archive.read(1024 * 1024):
                pass
        finally:
            archive.close()
    else:
        evidence["source_probe"] = add_and_verify_probe()
        evidence["archive"] = dump_source_archive()
        run_restore_helper()
    evidence["restore"] = verify_restored_target()
    evidence["elapsed_seconds"] = round(time.time() - started, 3)
    write_evidence(evidence)
    print("Synthetic restore verification passed: " + str(EVIDENCE_PATH))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError:
        error = sys.exception()
        print("Synthetic restore verification failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
