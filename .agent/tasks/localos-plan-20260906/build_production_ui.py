"""Build the disabled-pilot UI and bind its evidence to source hashes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess


ROOT = Path.cwd()
BUNDLE = ROOT / ".agent/tasks/localos-plan-20260906"
FLAGS = {"VITE_BROWSER_COOKIE_AUTH_ENABLED": "false", "VITE_GROWTH_PATHS_NAVIGATION_ENABLED": "true",
         "VITE_COMPILED_SCRIPT_PREVIEW_ENABLED": "false"}


def inputs():
    files = [path for directory in ("frontend/src", "frontend/public") for path in (ROOT / directory).rglob("*") if path.is_file()]
    files.extend(path for path in (ROOT / "frontend").iterdir()
                 if path.is_file() and path.suffix in (".html", ".ts", ".js", ".json")
                 and "playwright" not in path.name)
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}


def main():
    before = inputs()
    log = (BUNDLE / "raw/frontend-production-build.txt").open("w")
    try:
        result = subprocess.run(["npm", "run", "build:all"], cwd=ROOT / "frontend",
                                env={**os.environ, **FLAGS}, stdout=log, stderr=subprocess.STDOUT, check=False)
        log.write("\nEXIT=" + str(result.returncode) + "\n")
    finally:
        log.close()
    if result.returncode:
        raise SystemExit(result.returncode)
    if before != inputs():
        raise RuntimeError("Frontend inputs changed during build; rebuild after the source freeze")
    outputs = {}
    for directory in ("frontend/dist", "frontend/public-dist"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file():
                outputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (BUNDLE / "raw/frontend-production-build-proof.json").write_text(json.dumps(
        {"flags": FLAGS, "source_hashes": before, "output_hashes": outputs}, indent=2) + "\n")
    print("Production-flags frontend build passed; source/output hashes recorded.")


if __name__ == "__main__":
    main()
