#!/usr/bin/env python3
"""Bounded, reproducible measurement driver for LocalOS readiness journeys.

It runs the same guarded one-sample harness against clean source archives for
two refs. Setup and migrations happen inside each isolated harness process but
are never included in request timings: only ``kind == request`` rows from the
harness output contribute to latency statistics. Failed requests remain in
correctness counts and are excluded from latency percentiles.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HARNESS_SOURCE = ROOT / "scripts" / "readiness_journey_benchmark.py"
BASELINE_REF = "30262a5bf7b468e0a6f5a0e3d8262dbef119e075"
MAX_WARMUPS = 10
MAX_SERIAL_SAMPLES = 50
MAX_LOAD_SAMPLES = 20
ALLOWED_LOAD_CONCURRENCY = {2, 4}
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024
HARNESS_TIMEOUT_SECONDS = 240
TERMINATION_GRACE_SECONDS = 5

EXPECTED_REQUEST_STEPS = {
    "auth_tenant": {"login", "me", "business"},
    "service_compression": {"draft", "review", "apply", "apply_replay"},
    "finance_import": {"preview", "apply"},
    "content": {"plan", "draft", "internal_news"},
    "operator": {"propose_refocus", "confirm", "confirm_replay"},
}


def guarded_dsn(database_url: str) -> str:
    if not database_url:
        raise ValueError("LOCALOS_READINESS_JOURNEY_DATABASE_URL is required")
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE") or os.getenv("PGSERVICEFILE") or os.getenv("PGOPTIONS"):
        raise ValueError("refusing inherited libpq overrides")
    from psycopg2.extensions import parse_dsn
    from urllib.parse import urlsplit

    parsed_url = urlsplit(database_url)
    parameters = parse_dsn(database_url)
    port = str(parameters.get("port") or "")
    if (
        parsed_url.scheme != "postgresql"
        or parsed_url.query
        or parsed_url.fragment
        or str(parameters.get("host") or "") not in {"127.0.0.1", "::1"}
        or not port.isdigit()
        or int(port) < 32768
        or "readiness" not in str(parameters.get("dbname") or "").lower()
        or parameters.get("hostaddr")
        or parameters.get("service")
    ):
        raise ValueError("requires an explicit plain loopback readiness DSN on a high port")
    return database_url


def guard_provenance(pythonpath: str) -> dict[str, str]:
    entries = [entry for entry in pythonpath.split(os.pathsep) if entry]
    if not entries:
        raise ValueError("measurement driver requires guard-first sitecustomize.py")
    candidate = Path(entries[0]) / "sitecustomize.py"
    if not candidate.is_file():
        raise ValueError("measurement driver requires guard-first sitecustomize.py")
    return {"path": str(candidate), "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()}


def validate_limits(warmups: int, serial_samples: int, load_samples: int, load_concurrency: int) -> None:
    if not 0 <= warmups <= MAX_WARMUPS:
        raise ValueError(f"warmups must be 0..{MAX_WARMUPS}")
    if not 1 <= serial_samples <= MAX_SERIAL_SAMPLES:
        raise ValueError(f"serial samples must be 1..{MAX_SERIAL_SAMPLES}")
    if not 0 <= load_samples <= MAX_LOAD_SAMPLES:
        raise ValueError(f"load samples must be 0..{MAX_LOAD_SAMPLES}")
    if load_concurrency not in ALLOWED_LOAD_CONCURRENCY:
        raise ValueError("load concurrency must be 2 or 4")


def resolve_ref(ref: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def archive_source(ref: str, destination: Path) -> str:
    resolved = resolve_ref(ref)
    completed = subprocess.run(
        ["git", "archive", "--format=tar", resolved], cwd=ROOT, capture_output=True, check=False
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).decode("utf-8", errors="replace"))
    archive = tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:")
    try:
        archive.extractall(destination)
    finally:
        archive.close()
    target_harness = destination / "scripts" / HARNESS_SOURCE.name
    target_harness.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HARNESS_SOURCE, target_harness)
    return resolved


def guard_directory(guard_pythonpath: str) -> str:
    return guard_pythonpath.split(os.pathsep)[0]


def safe_environment(database_url: str, source_root: Path, guard_pythonpath: str) -> dict[str, str]:
    path_value = os.environ.get("PATH", "")
    home_value = os.environ.get("HOME", "")
    return {
        "PATH": path_value,
        "HOME": home_value,
        "PYTHONPATH": os.pathsep.join((guard_directory(guard_pythonpath), str(source_root / "src"), str(source_root))),
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "BROWSER_COOKIE_AUTH_ENABLED": "false",
        "LOCALOS_READINESS_JOURNEY_DATABASE_URL": database_url,
    }


def import_origins(source_root: Path, database_url: str, guard_pythonpath: str) -> dict[str, dict[str, str]]:
    environment = safe_environment(database_url, source_root, guard_pythonpath)
    marker = "__LOCALOS_READINESS_IMPORT_ORIGINS__"
    command = [
        sys.executable,
        "-c",
        "import importlib.util; import json; "
        "database_manager = importlib.util.find_spec('database_manager'); "
        "main = importlib.util.find_spec('src.main'); "
        f"print('{marker}' + json.dumps({{'database_manager': database_manager.origin, 'main': main.origin}}))",
    ]
    completed = subprocess.run(
        command,
        cwd=source_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip()[-2000:])
    origin_lines = [line for line in completed.stdout.splitlines() if line.startswith(marker)]
    if len(origin_lines) != 1:
        raise RuntimeError("archive import origin marker was not emitted exactly once")
    origins = json.loads(origin_lines[0][len(marker):])
    expected_original = {
        "database_manager": str(source_root / "src" / "database_manager.py"),
        "main": str(source_root / "src" / "main.py"),
    }
    expected_canonical = {key: str(Path(value).resolve()) for key, value in expected_original.items()}
    observed_canonical = {key: str(Path(value).resolve()) for key, value in origins.items()}
    archive_root = source_root.resolve()
    for value in observed_canonical.values():
        try:
            Path(value).relative_to(archive_root)
        except ValueError:
            raise RuntimeError(f"archive import escaped archive root: {value}")
    if observed_canonical != expected_canonical:
        raise RuntimeError(
            f"archive import isolation failed: original={origins}, canonical={observed_canonical}"
        )
    return {
        "observed_original": origins,
        "observed_canonical": observed_canonical,
        "expected_original": expected_original,
        "expected_canonical": expected_canonical,
    }


def exact_measure_database_name(database_name: str) -> bool:
    return bool(re.fullmatch(r"localos_readiness_measure_[0-9a-f]{32}", database_name))


def owned_database_absent(database_url: str, database_name: str) -> bool:
    if not exact_measure_database_name(database_name):
        raise ValueError("refusing preflight outside this driver's exact owned database name")
    from psycopg2 import connect
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(database_url)
    admin_url = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    connection = connect(admin_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
        return cursor.fetchone() is None
    finally:
        cursor.close()
        connection.close()


def cleanup_owned_database(database_url: str, database_name: str, absent_before_child: bool) -> dict[str, Any]:
    if not absent_before_child:
        return {"database_name": database_name, "skipped": "not_proven_absent_before_child"}
    if not exact_measure_database_name(database_name):
        raise ValueError("refusing cleanup outside this driver's exact owned database name")
    from psycopg2 import connect, sql
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(database_url)
    admin_url = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    connection = connect(admin_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
        existed = bool(cursor.fetchone())
        if existed:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))
        return {"database_name": database_name, "existed_after_child": existed, "removed": existed}
    finally:
        cursor.close()
        connection.close()


def terminate_process_group(process: subprocess.Popen[str]) -> str:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=TERMINATION_GRACE_SECONDS)
            return "sigterm"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return "sigkill"
    except ProcessLookupError:
        return "already_exited"


def validation_reasons(run: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if run.get("exit_code") != 0:
        reasons.append(f"exit_code:{run.get('exit_code')}")
    if run.get("harness_error"):
        reasons.append(str(run["harness_error"]))
    provenance = run.get("harness_provenance") or {}
    if provenance.get("script_sha256") != run.get("expected_harness_script_sha256"):
        reasons.append("harness_script_sha256_mismatch")
    if provenance.get("guard") != run.get("expected_guard"):
        reasons.append("harness_guard_mismatch")
    if sorted(provenance.get("provider_seams") or []) != ["content_text_generation", "operator_planner"]:
        reasons.append("harness_provider_seams_mismatch")
    samples = run.get("samples") or []
    request_counts: dict[tuple[str, str], int] = {}
    for row in samples:
        kind = str(row.get("kind") or "unknown")
        journey = str(row.get("journey") or "")
        step = str(row.get("step") or "")
        if kind == "request":
            key = (journey, step)
            request_counts[key] = request_counts.get(key, 0) + 1
        if row.get("success") is not True:
            reasons.append(f"failed_{kind}:{journey}/{step}:{row.get('error') or 'unspecified'}")
    for journey, steps in EXPECTED_REQUEST_STEPS.items():
        for step in steps:
            count = request_counts.get((journey, step), 0)
            if count != 1:
                reasons.append(f"request_count:{journey}/{step}:{count}")
    expected_keys = {(journey, step) for journey, steps in EXPECTED_REQUEST_STEPS.items() for step in steps}
    for key, count in request_counts.items():
        if key not in expected_keys:
            reasons.append(f"unexpected_request:{key[0]}/{key[1]}:{count}")
    return reasons


def run_harness_once(
    source_root: Path,
    database_url: str,
    guard_pythonpath: str,
    output_path: Path,
    ref: str,
    phase: str,
    sample_number: int,
) -> dict[str, Any]:
    environment = safe_environment(database_url, source_root, guard_pythonpath)
    database_name = "localos_readiness_measure_" + uuid.uuid4().hex
    expected_guard = guard_provenance(guard_pythonpath)
    expected_harness_script_sha256 = hashlib.sha256(
        (source_root / "scripts" / HARNESS_SOURCE.name).read_bytes()
    ).hexdigest()
    command = [
        sys.executable,
        str(source_root / "scripts" / HARNESS_SOURCE.name),
        "--output",
        str(output_path),
        "--database-name",
        database_name,
    ]
    absent_before_child = owned_database_absent(database_url, database_name)
    result = {
        "ref": ref,
        "phase": phase,
        "sample_number": sample_number,
        "exit_code": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "command": command,
        "planned_database_name": database_name,
        "absent_before_child": absent_before_child,
        "expected_guard": expected_guard,
        "expected_harness_script_sha256": expected_harness_script_sha256,
        "samples": [],
    }
    if not absent_before_child:
        result["harness_error"] = "planned owned database already exists"
        result["cleanup"] = {"database_name": database_name, "skipped": "not_proven_absent_before_child"}
        result["invalid_reasons"] = validation_reasons(result)
        result["valid"] = False
        return result
    process = subprocess.Popen(
        command,
        cwd=source_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    termination = "completed"
    try:
        stdout, stderr = process.communicate(timeout=HARNESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        termination = terminate_process_group(process)
        stdout, stderr = process.communicate()
    result["exit_code"] = process.returncode
    result["stdout_tail"] = stdout[-2000:]
    result["stderr_tail"] = stderr[-2000:]
    result["termination"] = termination
    try:
        if output_path.is_file():
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            result["samples"] = payload.get("samples") or []
            result["harness_provenance"] = {
                key: payload.get(key)
                for key in ("guard", "provider_seams", "script_sha256", "sample_type", "worktree_dirty")
            }
        else:
            result["harness_error"] = "harness did not produce an output file"
    except (OSError, json.JSONDecodeError):
        result["harness_error"] = f"invalid harness output:{type(sys.exception()).__name__}"
    finally:
        try:
            result["cleanup"] = cleanup_owned_database(database_url, database_name, absent_before_child)
        except Exception:
            result["cleanup"] = {"database_name": database_name, "error": type(sys.exception()).__name__}
    result["invalid_reasons"] = validation_reasons(result)
    if result["cleanup"].get("error"):
        result["invalid_reasons"].append("owned_database_cleanup_failed")
    result["valid"] = not result["invalid_reasons"]
    return result


def request_rows(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in run.get("samples") or [] if row.get("kind") == "request"]


def quantile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    remainder = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * remainder


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        for row in request_rows(run):
            key = (str(row.get("journey") or ""), str(row.get("step") or ""))
            bucket = buckets.setdefault(key, {"total": 0, "failed": 0, "latencies_ms": []})
            bucket["total"] += 1
            if row.get("success") is True and isinstance(row.get("duration_ms"), (int, float)):
                bucket["latencies_ms"].append(float(row["duration_ms"]))
            else:
                bucket["failed"] += 1
    result: dict[str, Any] = {}
    for key, bucket in sorted(buckets.items()):
        latencies = bucket["latencies_ms"]
        count = len(latencies)
        result["/".join(key)] = {
            "request_count": bucket["total"],
            "success_count": count,
            "failure_count": bucket["failed"],
            "p50_ms": quantile(latencies, 0.50),
            "p95_ms": quantile(latencies, 0.95),
            "p99_ms": quantile(latencies, 0.99),
            "p99_note": "exploratory only when fewer than 100 successful requests" if count < 100 else None,
        }
    return result


def correctness_counts(runs: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for run in runs:
        for row in run.get("samples") or []:
            kind = str(row.get("kind") or "unknown")
            bucket = counts.setdefault(kind, {"total": 0, "failed": 0})
            bucket["total"] += 1
            if row.get("success") is not True:
                bucket["failed"] += 1
    return counts


def run_phase(
    source_root: Path,
    database_url: str,
    guard_pythonpath: str,
    temp_root: Path,
    ref: str,
    phase: str,
    count: int,
    concurrency: int,
) -> list[dict[str, Any]]:
    if count == 0:
        return []
    def invoke(index: int) -> dict[str, Any]:
        output_path = temp_root / f"{ref[:12]}-{phase}-{index}.json"
        return run_harness_once(source_root, database_url, guard_pythonpath, output_path, ref, phase, index)
    if concurrency == 1:
        return [invoke(index) for index in range(count)]
    executor = ThreadPoolExecutor(max_workers=concurrency)
    try:
        return list(executor.map(invoke, range(count)))
    finally:
        executor.shutdown(wait=True)


def run_interleaved(
    source_roots: dict[str, Path],
    database_url: str,
    guard_pythonpath: str,
    temp_root: Path,
    refs: dict[str, str],
    phase: str,
    count: int,
) -> dict[str, list[dict[str, Any]]]:
    runs = {"baseline": [], "current": []}
    indexes = {"baseline": 0, "current": 0}
    sequence = ("baseline", "current", "current", "baseline")
    cursor = 0
    while indexes["baseline"] < count or indexes["current"] < count:
        key = sequence[cursor % len(sequence)]
        cursor += 1
        if indexes[key] >= count:
            continue
        index = indexes[key]
        indexes[key] += 1
        output_path = temp_root / f"{refs[key][:12]}-{phase}-{index}.json"
        run = run_harness_once(
            source_roots[key], database_url, guard_pythonpath, output_path, refs[key], phase, index
        )
        run["comparison_order"] = cursor
        runs[key].append(run)
    return runs


def database_identity(database_url: str) -> dict[str, str]:
    from psycopg2.extensions import parse_dsn

    parameters = parse_dsn(database_url)
    return {
        "host": str(parameters.get("host") or ""),
        "port": str(parameters.get("port") or ""),
        "database": str(parameters.get("dbname") or ""),
    }


def build_plan(
    args: argparse.Namespace,
    resolved_refs: dict[str, str],
    guard: dict[str, str],
    database_url: str,
    guard_pythonpath: str,
) -> dict[str, Any]:
    return {
        "method": "cold-process clean git archives plus identical injected guarded harness",
        "refs": resolved_refs,
        "guard": guard,
        "harness_sha256": hashlib.sha256(HARNESS_SOURCE.read_bytes()).hexdigest(),
        "driver": {
            "path": str(Path(__file__).resolve()),
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "python": sys.executable,
        },
        "database_identity": database_identity(database_url),
        "sanitized_environment": {
            "dotenv": "disabled",
            "bytecode": "disabled",
            "browser_cookie_auth": "disabled",
            "providers": "not inherited",
            "pythonpath": "guard-first, then archive src and root",
            "guard_pythonpath": guard_pythonpath,
            "preserved_keys": ["PATH", "HOME", "PYTHONPATH"],
        },
        "limits": {
            "warmups_per_ref": args.warmups,
            "serial_samples_per_ref": args.serial_samples,
            "load_samples_per_ref": args.load_samples,
            "load_concurrency": args.load_concurrency,
            "max_concurrent_harness_processes": args.load_concurrency,
            "per_child_timeout_seconds": HARNESS_TIMEOUT_SECONDS,
            "fresh_owned_database_per_harness_process": True,
            "minimum_free_bytes": MIN_FREE_BYTES,
        },
        "latency_scope": "serial cold-process request rows only; setup/migration excluded; correctness failures counted but excluded from percentiles",
        "comparison_order": "ABBA repeated for warmup and serial runs",
        "full_harness_stress": "concurrent setup, migration and request activity; status-only stress, never request-latency evidence",
        "p99_caveat": "p99 is exploratory with fewer than 100 successful requests",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=BASELINE_REF)
    parser.add_argument("--current", default="HEAD")
    parser.add_argument("--database-url", default=os.getenv("LOCALOS_READINESS_JOURNEY_DATABASE_URL", ""))
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--serial-samples", type=int, default=50)
    parser.add_argument("--load-samples", type=int, default=20)
    parser.add_argument("--load-concurrency", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    validate_limits(args.warmups, args.serial_samples, args.load_samples, args.load_concurrency)
    database_url = guarded_dsn(args.database_url)
    guard_pythonpath = os.environ.get("PYTHONPATH", "")
    guard = guard_provenance(guard_pythonpath)
    resolved_refs = {"baseline": resolve_ref(args.baseline), "current": resolve_ref(args.current)}
    if resolved_refs["baseline"] == resolved_refs["current"]:
        raise ValueError("baseline and current must resolve to different commits")
    plan = build_plan(args, resolved_refs, guard, database_url, guard_pythonpath)
    payload: dict[str, Any] = {"plan": plan, "executed": bool(args.execute)}
    if args.execute:
        if shutil.disk_usage(ROOT).free < MIN_FREE_BYTES:
            raise RuntimeError("insufficient free disk for bounded measurement")
        temporary_root = Path(tempfile.mkdtemp(prefix="localos-readiness-measure-"))
        try:
            archive_roots = {"baseline": temporary_root / "baseline", "current": temporary_root / "current"}
            archive_roots["baseline"].mkdir()
            archive_roots["current"].mkdir()
            for key, root in archive_roots.items():
                archive_source(resolved_refs[key], root)
            payload["import_origins"] = {
                key: import_origins(root, database_url, guard_pythonpath) for key, root in archive_roots.items()
            }
            run_root = temporary_root / "runs"
            run_root.mkdir()
            warmups = run_interleaved(
                archive_roots, database_url, guard_pythonpath, run_root, resolved_refs, "warmup", args.warmups
            )
            serial = run_interleaved(
                archive_roots, database_url, guard_pythonpath, run_root, resolved_refs, "serial", args.serial_samples
            )
            stress = {"baseline": [], "current": []}
            for key, root in archive_roots.items():
                stress[key] = run_phase(
                    root,
                    database_url,
                    guard_pythonpath,
                    run_root,
                    resolved_refs[key],
                    "full_harness_stress",
                    args.load_samples,
                    args.load_concurrency,
                )
            all_runs = {
                key: warmups[key] + serial[key] + stress[key] for key in ("baseline", "current")
            }
            payload["runs"] = all_runs
            payload["summary"] = {
                key: {
                    "warmup_diagnostics": correctness_counts(warmups[key]),
                    "serial_correctness": correctness_counts(serial[key]),
                    "serial_request_latency": summarize(serial[key]),
                    "full_harness_stress": correctness_counts(stress[key]),
                }
                for key in ("baseline", "current")
            }
            invalid_runs = [run for run_list in all_runs.values() for run in run_list if not run["valid"]]
            payload["valid"] = not invalid_runs
            payload["invalid_reasons"] = [reason for run in invalid_runs for reason in run["invalid_reasons"]]
        except Exception:
            payload["valid"] = False
            payload["invalid_reasons"] = [
                f"setup_failure:{type(sys.exception()).__name__}:{sys.exception()}"
            ]
        finally:
            shutil.rmtree(temporary_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if payload.get("valid", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
