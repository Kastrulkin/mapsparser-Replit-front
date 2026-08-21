"""Bounded ingestion load profile for an explicitly approved test tracker."""

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import threading
import time
import uuid

import requests


def _event(hostname: str, visitor_id: str, session_id: str, malformed: bool) -> dict:
    event = {
        "event_id": f"e_{uuid.uuid4().hex}",
        "visitor_id": visitor_id,
        "session_id": session_id,
        "event": random.choice(("page_view", "scroll_depth", "click", "outbound_click")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "page": {"hostname": hostname, "path": random.choice(("/", "/services", "/prices", "/contacts"))},
    }
    if event["event"] == "scroll_depth":
        event["depth"] = random.choice((25, 50, 75, 100))
    if malformed:
        event["visitor_id"] = "invalid"
    return event


def _request(target: str, sites: list[tuple[str, str]], malformed_ratio: float) -> tuple[int, float]:
    tracker_id, hostname = random.choice(sites)
    visitor_id = f"v_{uuid.uuid4().hex}"
    session_id = f"s_{uuid.uuid4().hex}"
    batch_size = random.randint(5, 15)
    malformed = random.random() < malformed_ratio
    payload = {
        "tracker_id": tracker_id,
        "tracker_version": "load-test-1",
        "schema_version": 2,
        "events": [_event(hostname, visitor_id, session_id, malformed) for _index in range(batch_size)],
    }
    started_at = time.perf_counter()
    try:
        response = requests.post(target, json=payload, timeout=5)
        return response.status_code, (time.perf_counter() - started_at) * 1000
    except requests.RequestException:
        return 0, (time.perf_counter() - started_at) * 1000


def _probe_request(target: str) -> tuple[int, float]:
    started_at = time.perf_counter()
    try:
        response = requests.get(target, timeout=5)
        return response.status_code, (time.perf_counter() - started_at) * 1000
    except requests.RequestException:
        return 0, (time.perf_counter() - started_at) * 1000


def _latency_report(results: list[tuple[int, float]]) -> dict:
    latencies = sorted(latency for _status, latency in results)
    if not latencies:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    positions = {
        name: min(len(latencies) - 1, max(0, round(len(latencies) * percentile) - 1))
        for name, percentile in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
    }
    return {
        "mean": round(statistics.fmean(latencies), 2),
        **{name: round(latencies[position], 2) for name, position in positions.items()},
        "max": round(max(latencies), 2),
    }


def _status_counts(results: list[tuple[int, float]]) -> dict[str, int]:
    statuses: dict[str, int] = {}
    for status, _latency in results:
        statuses[str(status)] = statuses.get(str(status), 0) + 1
    return statuses


def main() -> int:
    parser = ArgumentParser(description="Run a bounded LocalOS web-ingestion load profile.")
    parser.add_argument("--target", default="http://127.0.0.1:8000/api/tracking/events")
    parser.add_argument("--tracker")
    parser.add_argument("--hostname")
    parser.add_argument(
        "--site",
        action="append",
        default=[],
        metavar="TRACKER_ID=HOSTNAME",
        help="Repeat for a multi-site profile; the single --tracker/--hostname pair remains supported.",
    )
    parser.add_argument("--sites-file", help="Text file with one TRACKER_ID=HOSTNAME pair per line.")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--malformed-percent", type=float, default=3.0)
    parser.add_argument("--p95-budget-ms", type=float, default=1000)
    parser.add_argument("--probe-url", help="Main LocalOS URL measured before and during ingestion load.")
    parser.add_argument("--probe-baseline-requests", type=int, default=20)
    parser.add_argument("--probe-interval-ms", type=int, default=50)
    parser.add_argument("--probe-degradation-ratio", type=float, default=2.0)
    parser.add_argument("--confirm-write", action="store_true", help="Required because this creates analytics events.")
    arguments = parser.parse_args()
    if not arguments.confirm_write:
        parser.error("--confirm-write is required")
    sites = []
    if arguments.tracker and arguments.hostname:
        sites.append((arguments.tracker, arguments.hostname))
    configured_sites = list(arguments.site)
    if arguments.sites_file:
        configured_sites.extend(
            line.strip()
            for line in Path(arguments.sites_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    for site in configured_sites:
        tracker_id, separator, hostname = site.partition("=")
        if not separator or not tracker_id.startswith("pub_") or not hostname:
            parser.error(f"invalid --site value: {site}")
        sites.append((tracker_id, hostname))
    if not sites:
        parser.error("provide --tracker with --hostname or at least one --site")
    request_count = max(1, min(arguments.requests, 100000))
    concurrency = max(1, min(arguments.concurrency, 1000))
    malformed_ratio = max(0.0, min(arguments.malformed_percent, 10.0)) / 100
    probe_baseline = []
    probe_during = []
    probe_stop = threading.Event()
    if arguments.probe_url:
        probe_baseline = [
            _probe_request(arguments.probe_url)
            for _index in range(max(1, min(arguments.probe_baseline_requests, 200)))
        ]

    def run_probe() -> None:
        interval_seconds = max(0.01, min(arguments.probe_interval_ms, 5000) / 1000)
        while not probe_stop.is_set():
            probe_during.append(_probe_request(arguments.probe_url))
            probe_stop.wait(interval_seconds)

    probe_thread = threading.Thread(target=run_probe, daemon=True) if arguments.probe_url else None
    results = []
    started_at = time.perf_counter()
    if probe_thread:
        probe_thread.start()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_request, arguments.target, sites, malformed_ratio)
                for _index in range(request_count)
            ]
            for future in as_completed(futures):
                results.append(future.result())
    finally:
        probe_stop.set()
        if probe_thread:
            probe_thread.join(timeout=6)
    elapsed_seconds = max(0.001, time.perf_counter() - started_at)
    statuses = _status_counts(results)
    report = {
        "requests": request_count,
        "sites": len(sites),
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "requests_per_second": round(request_count / elapsed_seconds, 2),
        "status_counts": statuses,
        "latency_ms": _latency_report(results),
    }
    probe_failed = False
    if arguments.probe_url:
        baseline_latency = _latency_report(probe_baseline)
        during_latency = _latency_report(probe_during)
        baseline_p95 = max(1.0, baseline_latency["p95"])
        degradation_ratio = round(during_latency["p95"] / baseline_p95, 2)
        allowed_ratio = max(1.0, arguments.probe_degradation_ratio)
        allowed_probe_p95 = round(max(baseline_p95 * allowed_ratio, baseline_p95 + 100), 2)
        baseline_statuses = _status_counts(probe_baseline)
        during_statuses = _status_counts(probe_during)
        report["main_api_probe"] = {
            "url": arguments.probe_url,
            "baseline_requests": len(probe_baseline),
            "during_requests": len(probe_during),
            "baseline_status_counts": baseline_statuses,
            "during_status_counts": during_statuses,
            "baseline_latency_ms": baseline_latency,
            "during_latency_ms": during_latency,
            "p95_degradation_ratio": degradation_ratio,
            "allowed_degradation_ratio": allowed_ratio,
            "allowed_during_p95_ms": allowed_probe_p95,
        }
        probe_errors = sum(
            count for status, count in during_statuses.items() if status == "0" or int(status) >= 500
        )
        probe_failed = (
            not probe_during
            or probe_errors > 0
            or during_latency["p95"] > allowed_probe_p95
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    unexpected_errors = sum(count for status, count in statuses.items() if status == "0" or int(status) >= 500)
    return 1 if report["latency_ms"]["p95"] > arguments.p95_budget_ms or unexpected_errors or probe_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
