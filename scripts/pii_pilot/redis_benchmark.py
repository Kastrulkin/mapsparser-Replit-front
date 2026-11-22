"""Linux benchmark with a real, dedicated loopback Redis in the same cgroup."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--expected-cpus", type=float, default=2.0)
    parser.add_argument("--expected-memory-mib", type=int, default=4096)
    args = parser.parse_args()
    if not (0 < args.expected_cpus <= 2 and 512 <= args.expected_memory_mib <= 4096):
        raise RuntimeError("Pilot profile exceeds supported resource bounds")
    from cryptography.fernet import Fernet
    import psutil
    from services.pii_protection.engines import make_engine
    from services.pii_protection.gateway import ProtectionService, RedisStore, Scope
    from benchmark import percentile
    from environment import environment
    from public_inputs import public_context_for_case

    original_connect = socket.socket.connect
    original_lookup = socket.getaddrinfo

    def local_connect(connection, address):
        if not isinstance(address, tuple) or address != ("127.0.0.1", 16379):
            raise RuntimeError("PILOT_NETWORK_DISABLED")
        return original_connect(connection, address)

    def local_lookup(host, port, *args, **kwargs):
        if host != "127.0.0.1" or port != 16379:
            raise RuntimeError("PILOT_NETWORK_DISABLED")
        return original_lookup(host, port, *args, **kwargs)

    socket.socket.connect = local_connect
    socket.getaddrinfo = local_lookup
    limits = environment()
    if (limits["cpu_quota_cores"] != args.expected_cpus
            or limits["memory_limit_bytes"] != args.expected_memory_mib * 1024 ** 2):
        raise RuntimeError("Kernel limits do not match the requested measurement profile")
    raw = (ROOT / "tests/fixtures/pii/synthetic_200.jsonl").read_bytes()
    cases = [json.loads(line) for line in raw.decode().splitlines()]
    store = RedisStore("redis://127.0.0.1:16379/15")
    info = store.client.info("server")
    redis_process = psutil.Process(info["process_id"])
    service = ProtectionService(make_engine("piighost_presidio"), store, Fernet.generate_key())
    cpu_begin = time.process_time()
    redis_cpu_begin = sum(redis_process.cpu_times()[:2])

    def process(case):
        started = time.perf_counter()
        scope = Scope("synthetic-business", "synthetic-user", case["id"])
        result = service.protect(case["text"], scope, case["policy"],
                                 public_context=public_context_for_case(case["id"]))
        for item in case["entities"]:
            assert item["value"] not in result.text
        assert all(value in result.text for value in case["allowed_public"])
        if not any(item["type"] == "SECRET" for item in case["entities"]):
            assert result.restore_text(result.text) == case["text"]
        return (time.perf_counter() - started) * 1000

    warmup = [process(case) for case in cases]
    started = time.perf_counter()
    latencies = [process(case) for _ in range(3) for case in cases]
    elapsed = time.perf_counter() - started
    started = time.perf_counter()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        parallel = list(pool.map(process, cases * 3))
    finally:
        pool.shutdown(wait=True)
    parallel_elapsed = time.perf_counter() - started
    process_info = psutil.Process()
    peak = Path("/sys/fs/cgroup/memory.peak")
    report = {"environment": limits, "store": "real_redis_loopback", "redis_version": info["redis_version"],
              "scenario_count": 200, "warmup_requests": len(warmup), "measured_requests": len(latencies),
              "parallel_requests": len(parallel), "concurrent_clients": 4, "model_lanes": 1,
              "corpus_sha256": hashlib.sha256(raw).hexdigest(),
              "p50_ms": percentile(latencies, 50), "p95_ms": percentile(latencies, 95), "p99_ms": percentile(latencies, 99),
              "requests_per_second": round(len(latencies) / elapsed, 2),
              "concurrent_p50_ms": percentile(parallel, 50), "concurrent_p95_ms": percentile(parallel, 95),
              "concurrent_p99_ms": percentile(parallel, 99),
              "concurrent_requests_per_second": round(len(parallel) / parallel_elapsed, 2),
              "cpu_python_seconds": round(time.process_time() - cpu_begin, 3),
              "cpu_redis_seconds": round(sum(redis_process.cpu_times()[:2]) - redis_cpu_begin, 3),
              "python_rss_bytes": process_info.memory_info().rss,
              "redis_rss_bytes": redis_process.memory_info().rss,
              "cgroup_peak_bytes": int(peak.read_text()) if peak.exists() else None,
              "redis_persistence": {"save": store.client.config_get("save")["save"],
                                    "appendonly": store.client.config_get("appendonly")["appendonly"]}}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
