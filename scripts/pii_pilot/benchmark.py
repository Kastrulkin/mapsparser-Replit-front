"""Offline benchmark. Inputs are restricted to the checked-in synthetic corpus."""

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import platform
import resource
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from environment import environment


def deny_network(*args, **kwargs):
    raise RuntimeError("PILOT_NETWORK_DISABLED")


def percentile(values, percent):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, int(len(ordered) * percent / 100) - 1))], 3)


def counts():
    return {"expected": 0, "protected": 0, "critical_missed": 0,
            "detections": 0, "true_detections": 0, "false_positives": 0}


def evaluate(case, result):
    expected = case["entities"]
    findings = result.findings
    values = counts()
    values["expected"] = len(expected)
    values["detections"] = len(findings)
    for item in expected:
        covered = any(f.start <= item["start"] and f.end >= item["end"] for f in findings)
        # Full span coverage AND no original value in what the model would receive.
        protected = covered and item["value"] not in result.text
        values["protected"] += int(protected)
        values["critical_missed"] += int(item["critical"] and not protected)
    for finding in findings:
        overlaps = any(finding.start < item["end"] and finding.end > item["start"] for item in expected)
        values["true_detections"] += int(overlaps)
        values["false_positives"] += int(not overlaps)
    return values


def decorate(values):
    return {**values,
            "recall": round(values["protected"] / values["expected"], 4) if values["expected"] else None,
            "precision": round(values["true_detections"] / values["detections"], 4) if values["detections"] else None}


def run(args):
    # No .env loading, databases, HTTP providers, telemetry or real tools.
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    socket.getaddrinfo = deny_network
    from services.pii_protection.engines import make_engine
    raw = (ROOT / "tests/fixtures/pii/synthetic_200.jsonl").read_bytes()
    cases = [json.loads(line) for line in raw.decode().splitlines()]
    assert len(cases) == 200 and all(item["id"].startswith("synthetic-") for item in cases)
    started = time.perf_counter()
    engine = make_engine(args.engine)
    load_seconds = time.perf_counter() - started

    def scan_case(case):
        result = engine.scan(case["text"])
        if args.profile == "localos_rules":
            from services.pii_protection.rules import protected_findings, render
            from services.pii_protection.public_context import validated_public_spans
            from public_inputs import public_context_for_case
            public_spans = validated_public_spans(case["text"], "synthetic-business", case["policy"],
                                                 public_context_for_case(case["id"]))
            findings = protected_findings(case["text"], result.findings, case["policy"], public_spans)
            return render(case["text"], findings)
        return result
    total = counts()
    languages = {}
    types = {}
    messages = []
    latencies = []
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    for case in cases:
        begin = time.perf_counter()
        result = scan_case(case)
        elapsed = (time.perf_counter() - begin) * 1000
        latencies.append(elapsed)
        values = evaluate(case, result)
        for bucket in (total, languages.setdefault(case["language"], counts())):
            for key, value in values.items():
                bucket[key] += value
        for item in case["entities"]:
            bucket = types.setdefault(item["type"], {"expected": 0, "protected": 0, "critical_missed": 0})
            covered = any(f.start <= item["start"] and f.end >= item["end"] for f in result.findings)
            protected = covered and item["value"] not in result.text
            bucket["expected"] += 1
            bucket["protected"] += int(protected)
            bucket["critical_missed"] += int(item["critical"] and not protected)
        restored = result.text
        # Single-pass native restoration, avoiding cascades in replacement values.
        import re
        if result.replacements:
            pattern = re.compile("|".join(re.escape(token) for token in sorted(result.replacements, key=len, reverse=True)))
            restored = pattern.sub(lambda match: result.replacements[match.group()], restored)
        if result.restored_text is not None:
            restored = result.restored_text
        messages.append({"id": case["id"], "language": case["language"], "kind": case["kind"],
                         **values, "fully_protected": values["protected"] == values["expected"],
                         "round_trip_exact": restored == case["text"],
                         "public_preserved": all(value in result.text for value in case["allowed_public"]),
                         "latency_ms": round(elapsed, 3)})
    wall_seconds = time.perf_counter() - wall_start
    cpu_seconds = time.process_time() - cpu_start
    # A shared instance is serialized deliberately: models have one bounded CPU lane.
    lock = threading.Lock()

    def concurrent_scan(case):
        begin = time.perf_counter()
        with lock:
            result = scan_case(case)
        return (time.perf_counter() - begin) * 1000, bool(result)

    begin = time.perf_counter()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        parallel = list(pool.map(concurrent_scan, cases))
    finally:
        pool.shutdown(wait=True)
    parallel_seconds = time.perf_counter() - begin
    versions = {name: importlib.metadata.version(name) for name in
                ("piighost", "presidio-analyzer", "preserve-pii", "spacy", "en-core-web-sm", "ru-core-news-sm")}
    report = {"engine": args.engine, "profile": args.profile, "corpus_sha256": hashlib.sha256(raw).hexdigest(),
              "scenario_count": len(cases), "versions": versions,
              "environment": environment(),
              "totals": decorate(total), "by_language": {key: decorate(value) for key, value in languages.items()},
              "by_type": {key: {**value, "recall": round(value["protected"] / value["expected"], 4)}
                          for key, value in types.items()},
              "fully_protected_messages": sum(item["fully_protected"] for item in messages),
              "round_trip_exact_messages": sum(item["round_trip_exact"] for item in messages),
              "public_geo_preserved": sum(item["public_preserved"] for item in messages if item["kind"] == "public_geo"),
              "performance": {"load_seconds": round(load_seconds, 3),
                              "p50_ms": percentile(latencies, 50), "p95_ms": percentile(latencies, 95),
                              "p99_ms": percentile(latencies, 99), "wall_seconds": round(wall_seconds, 3),
                              "cpu_seconds": round(cpu_seconds, 3), "requests_per_second": round(len(cases) / wall_seconds, 2),
                              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024),
                              "concurrent_clients": 4, "model_lanes": 1,
                              "concurrent_p95_ms": percentile([item[0] for item in parallel], 95),
                              "concurrent_requests_per_second": round(len(cases) / parallel_seconds, 2)},
              "cases": messages}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("engine", "profile", "totals", "fully_protected_messages", "performance")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("piighost_presidio", "preserve"), required=True)
    parser.add_argument("--profile", choices=("native", "localos_rules"), default="native")
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
