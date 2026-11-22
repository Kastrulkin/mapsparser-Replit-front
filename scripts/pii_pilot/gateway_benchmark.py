"""Measure the selected gateway, including encryption and local restoration."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def deny_network(*_, **__):
    raise RuntimeError("PILOT_NETWORK_DISABLED")


def main():
    socket.socket.connect = deny_network
    socket.getaddrinfo = deny_network
    from cryptography.fernet import Fernet
    from services.pii_protection.engines import make_engine
    from services.pii_protection.gateway import ProtectionService, MemoryStore, Scope
    from benchmark import percentile
    from public_inputs import public_context_for_case

    raw = (ROOT / "tests/fixtures/pii/synthetic_200.jsonl").read_bytes()
    cases = [json.loads(line) for line in raw.decode().splitlines()]
    service = ProtectionService(make_engine("piighost_presidio"), MemoryStore(), Fernet.generate_key())

    def process(case):
        started = time.perf_counter()
        scope = Scope("synthetic-business", "synthetic-user", case["id"])
        exchange = service.protect(case["text"], scope, case["policy"], public_context=public_context_for_case(case["id"]))
        exchange.restore_text(exchange.text)
        return (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    cpu_started = time.process_time()
    latencies = [process(case) for case in cases]
    elapsed = time.perf_counter() - started
    cpu_seconds = time.process_time() - cpu_started
    started = time.perf_counter()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        parallel = list(pool.map(process, cases))
    finally:
        pool.shutdown(wait=True)
    parallel_elapsed = time.perf_counter() - started
    result = {"scenario_count": 200, "corpus_sha256": hashlib.sha256(raw).hexdigest(),
              "engine": "piighost_presidio", "store": "encrypted_memory_test_only",
              "environment": {"os": platform.system(), "machine": platform.machine(),
                              "python": platform.python_version(), "host_cpus": os.cpu_count(),
                              "target_2cpu_4gb_measured": False},
              "p50_ms": percentile(latencies, 50), "p95_ms": percentile(latencies, 95),
              "p99_ms": percentile(latencies, 99), "requests_per_second": round(200 / elapsed, 2),
              "cpu_seconds": round(cpu_seconds, 3), "concurrent_clients": 4, "model_lanes": 1,
              "concurrent_p95_ms": percentile(parallel, 95),
              "concurrent_requests_per_second": round(200 / parallel_elapsed, 2),
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
