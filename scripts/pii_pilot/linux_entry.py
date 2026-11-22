"""Run the synthetic test suite and measurements inside a network-isolated container."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-comparison", action="store_true")
    parser.add_argument("--expected-cpus", type=float, default=2.0)
    parser.add_argument("--expected-memory-mib", type=int, default=4096)
    args = parser.parse_args()
    if not (0 < args.expected_cpus <= 2 and 512 <= args.expected_memory_mib <= 4096):
        raise RuntimeError("Pilot profile exceeds supported resource bounds")
    from environment import environment
    import redis
    output = Path("/evidence")
    output.mkdir(exist_ok=True)
    limits = environment()
    if (limits["cpu_quota_cores"] != args.expected_cpus
            or limits["memory_limit_bytes"] != args.expected_memory_mib * 1024 ** 2):
        raise RuntimeError("Kernel-enforced limits do not match the requested pilot profile")
    if os.getenv("PII_PROTECTION_ENABLED", "false") != "false":
        raise RuntimeError("Container default flag must remain off")
    server = subprocess.Popen(["redis-server", "--bind", "127.0.0.1", "--port", "16379",
                               "--save", "", "--appendonly", "no", "--maxmemory", "96mb",
                               "--maxmemory-policy", "noeviction", "--dir", "/tmp"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        client = redis.Redis(host="127.0.0.1", port=16379, db=15)
        for _ in range(100):
            try:
                if client.ping():
                    break
            except redis.ConnectionError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Ephemeral Redis did not start")
        environment_values = {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "src",
                              "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                              "TOKENIZERS_PARALLELISM": "false", "PII_PROTECTION_ENABLED": "false",
                              "PII_TEST_REDIS_URL": "redis://127.0.0.1:16379/15"}
        commands = [
            ("tests", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                       "--junitxml=/evidence/tests.xml", "tests/test_pii_protection.py",
                       "tests/test_llm_budget_boundary.py", "tests/test_operator_tool_loop.py",
                       "tests/test_pii_shared_runtime.py"]),
            ("comparison", [sys.executable, "scripts/pii_pilot/run.py", "--output-dir", "/evidence/comparison"]),
            ("redis-performance", [sys.executable, "scripts/pii_pilot/redis_benchmark.py", "/evidence/redis-performance.json",
                                   "--expected-cpus", str(args.expected_cpus),
                                   "--expected-memory-mib", str(args.expected_memory_mib)]),
        ]
        if args.skip_comparison:
            commands = [item for item in commands if item[0] != "comparison"]
        outcomes = {}
        for label, command in commands:
            run = subprocess.run(command, env=environment_values, capture_output=True, text=True, timeout=600)
            (output / (label + ".log")).write_text(run.stdout + run.stderr)
            outcomes[label] = {"command": command, "exit_code": run.returncode}
            if run.returncode:
                break
        (output / "run.json").write_text(json.dumps({"environment": limits, "default_flag": False,
                                                    "expected_profile": {"cpu_quota_cores": args.expected_cpus,
                                                                         "memory_limit_mib": args.expected_memory_mib},
                                                    "redis_version": client.info("server")["redis_version"],
                                                    "commands": outcomes}, indent=2) + "\n")
        freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
        (output / "environment-freeze.txt").write_text(freeze.stdout)
        return 0 if len(outcomes) == len(commands) and all(value["exit_code"] == 0 for value in outcomes.values()) else 1
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
