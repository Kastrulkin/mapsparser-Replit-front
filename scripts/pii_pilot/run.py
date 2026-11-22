"""Reproduce the four comparisons in fresh, credential-free subprocesses."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="docs/pii-protection/results")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1",
                   "OPENBLAS_NUM_THREADS": "1", "TOKENIZERS_PARALLELISM": "false"}
    for engine in ("piighost_presidio", "preserve"):
        for profile in ("native", "localos_rules"):
            command = [sys.executable, str(ROOT / "scripts/pii_pilot/benchmark.py"), "--engine", engine,
                       "--profile", profile, "--output", str(output / f"{engine}-{profile}.json")]
            result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=300)
            if result.returncode:
                raise SystemExit(f"Pilot failed: {engine}/{profile}; no successful result was recorded")
            report = json.loads((output / f"{engine}-{profile}.json").read_text())
            print(json.dumps({"engine": engine, "profile": profile, "totals": report["totals"],
                              "p95_ms": report["performance"]["p95_ms"]}))


if __name__ == "__main__":
    main()
