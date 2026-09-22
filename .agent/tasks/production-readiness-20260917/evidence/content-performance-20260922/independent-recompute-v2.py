#!/usr/bin/env python3
"""Independent, read-only recomputation of the guarded readiness measurement."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import quantiles


RAW = Path("/private/tmp/localos-content-perf.cuey0qa9/driver-output.json")
OUT = Path("/private/tmp/localos-content-perf-deps.7zNvCi/independent-recompute-v2.json")
EXPECTED_STEPS = {
    "auth_tenant": {"login", "me", "business"},
    "service_compression": {"draft", "review", "apply", "apply_replay"},
    "finance_import": {"preview", "apply"},
    "content": {"plan", "draft", "internal_news"},
    "operator": {"propose_refocus", "confirm", "confirm_replay"},
}


def summary(values: list[float]) -> dict[str, float | int]:
    if len(values) != 50:
        raise ValueError(f"expected exactly 50 serial samples, got {len(values)}")
    percentiles = quantiles(values, n=100, method="inclusive")
    return {
        "count": len(values),
        "p50_ms": percentiles[49],
        "p95_ms": percentiles[94],
        "p99_ms": percentiles[98],
    }


payload = json.loads(RAW.read_text(encoding="utf-8"))
if payload.get("valid") is not True or payload.get("executed") is not True:
    raise ValueError("raw measurement is not a valid executed run")
plan = payload.get("plan") or {}
refs = plan.get("refs") or {}
if refs.get("baseline") != "272794a439a76204536480f158e79276ccd7b318":
    raise ValueError("unexpected baseline")
if refs.get("current") != "dc1a6b76821683effe2d949cfcd4a9f3c1e15cef":
    raise ValueError("unexpected current")
limits = plan.get("limits") or {}
if (limits.get("warmups_per_ref"), limits.get("serial_samples_per_ref"), limits.get("load_samples_per_ref")) != (5, 50, 0):
    raise ValueError("unexpected measurement profile")

result: dict[str, object] = {
    "raw_path": str(RAW),
    "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
    "refs": refs,
    "guard": plan.get("guard"),
    "harness_sha256": plan.get("harness_sha256"),
    "driver": plan.get("driver"),
    "method": "stdlib statistics.quantiles(n=100, method='inclusive') over successful serial rows only",
    "sides": {},
}

for phase, expected_count in (("warmup", 10), ("serial", 100)):
    phase_runs = [
        (side, run)
        for side in ("baseline", "current")
        for run in ((payload.get("runs") or {}).get(side) or [])
        if run.get("phase") == phase
    ]
    ordered = sorted(phase_runs, key=lambda item: item[1].get("comparison_order"))
    if [run.get("comparison_order") for _side, run in ordered] != list(range(1, expected_count + 1)):
        raise ValueError(f"{phase} comparison orders are not exact")
    expected_sides = (["baseline", "current", "current", "baseline"] * ((expected_count + 3) // 4))[:expected_count]
    if [side for side, _run in ordered] != expected_sides:
        raise ValueError(f"{phase} comparison order is not ABBA")

for side in ("baseline", "current"):
    side_runs = (payload.get("runs") or {}).get(side) or []
    serial_runs = [run for run in side_runs if run.get("phase") == "serial"]
    warmup_runs = [run for run in side_runs if run.get("phase") == "warmup"]
    if len(serial_runs) != 50 or len(warmup_runs) != 5:
        raise ValueError(f"unexpected run count for {side}")
    samples_by_step: dict[str, list[float]] = {}
    samples_by_journey: dict[str, list[float]] = {journey: [] for journey in EXPECTED_STEPS}
    failures: list[dict[str, object]] = []
    for run in serial_runs:
        if run.get("valid") is not True or run.get("exit_code") != 0 or run.get("termination") != "completed":
            raise ValueError(f"invalid serial run for {side}")
        rows = run.get("samples") or []
        journey_values: dict[str, list[float]] = {journey: [] for journey in EXPECTED_STEPS}
        observed: set[tuple[str, str]] = set()
        for row in rows:
            if row.get("success") is not True:
                failures.append({"order": run.get("comparison_order"), "row": row})
            if row.get("kind") != "request":
                continue
            journey, step = str(row.get("journey")), str(row.get("step"))
            if step not in EXPECTED_STEPS.get(journey, set()):
                raise ValueError(f"unexpected request {journey}/{step}")
            if (journey, step) in observed:
                raise ValueError(f"duplicate request {journey}/{step}")
            observed.add((journey, step))
            if row.get("success") is not True or not isinstance(row.get("duration_ms"), (int, float)):
                raise ValueError(f"failed/non-timed request {journey}/{step}")
            value = row["duration_ms"]
            samples_by_step.setdefault(f"{journey}/{step}", []).append(value)
            journey_values[journey].append(value)
        if observed != {(journey, step) for journey, steps in EXPECTED_STEPS.items() for step in steps}:
            raise ValueError(f"missing request coverage in {side}")
        for journey, values in journey_values.items():
            samples_by_journey[journey].append(sum(values))
    if failures:
        raise ValueError(f"non-success rows in serial runs for {side}")
    result["sides"][side] = {
        "warmup_count_excluded": len(warmup_runs),
        "serial_count": len(serial_runs),
        "request_steps": {key: summary(values) for key, values in sorted(samples_by_step.items())},
        "journey_sums": {key: summary(values) for key, values in sorted(samples_by_journey.items())},
    }

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
