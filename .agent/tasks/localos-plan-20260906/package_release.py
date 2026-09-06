"""Package only committed task runtime files and the locally verified UI build.

Run from the repository root after the scoped commit. This prepares local
artifacts; it never connects to production or applies migrations.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile


ROOT = Path.cwd()
BUNDLE = ROOT / ".agent/tasks/localos-plan-20260906"
DESTINATION = ROOT / "outputs/localos-release-20260906"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def main():
    owned = json.loads((BUNDLE / "owned-files.json").read_text())["files"]
    commit = git("rev-parse", "HEAD").decode().strip()
    for name in owned:
        if name == "docker-compose.yml":
            continue  # Its unrelated Google Cloud hunks stay outside the index.
        if git("show", "HEAD:" + name) != (ROOT / name).read_bytes():
            raise RuntimeError("Owned file differs from committed release: " + name)
    log = (BUNDLE / "raw/frontend-production-build.txt").read_text()
    if not log.rstrip().endswith("EXIT=0"):
        raise RuntimeError("A successful production-flags UI build is required")
    flags = {
        "VITE_BROWSER_COOKIE_AUTH_ENABLED": "false",
        "VITE_GROWTH_PATHS_NAVIGATION_ENABLED": "true",
        "VITE_COMPILED_SCRIPT_PREVIEW_ENABLED": "false",
    }
    build_proof = json.loads((BUNDLE / "raw/frontend-production-build-proof.json").read_text())
    if build_proof["flags"] != flags:
        raise RuntimeError("UI build flags do not match this release")
    for name, expected in {**build_proof["source_hashes"], **build_proof["output_hashes"]}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("UI source/output changed after verified build: " + name)
    source_paths = [name for name in owned if name.startswith(("src/", "alembic_migrations/"))
                    or name in ("entrypoint.sh", "scripts/localos_migrator.py", "scripts/check_content_learning_schema.py")]
    ui_paths = []
    for directory, entrypoint in (("frontend/dist", "index.html"),
                                  ("frontend/public-dist", "public-audit/index.html")):
        if not (ROOT / directory / entrypoint).is_file():
            raise RuntimeError("Missing UI entrypoint: " + directory + "/" + entrypoint)
        ui_paths.extend(str(path.relative_to(ROOT)) for path in (ROOT / directory).rglob("*") if path.is_file())
    DESTINATION.mkdir(parents=True, exist_ok=True)
    archive_path = DESTINATION / "payload.tar.gz"
    archive = tarfile.open(archive_path, "w:gz")
    hashes = {}
    try:
        for name in sorted(source_paths + ui_paths):
            path = ROOT / name
            archive.add(path, arcname=name, recursive=False)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    finally:
        archive.close()
    patch = git("diff", "ffc54c19", "HEAD", "--", "docker-compose.yml")
    if b"GOOGLE_CLOUD_PROJECT_ID" in patch:
        raise RuntimeError("Foreign Compose changes were included in the commit")
    (DESTINATION / "compose.patch").write_bytes(patch)
    manifest = {
        "commit": commit,
        "baseline": "ffc54c19122c86b7d8bf2c25aa7d3c8080c754c0",
        "production_changed": False,
        "schema_before": "20260905_004",
        "schema_after": "20260906_012",
        "build_flags": flags,
        "frontend_verification": "raw/frontend-production-build.txt; source separately typechecked and tested",
        "compiled_preview_execute": False,
        "activity_proposals": False,
        "worker_role": "all (unchanged)",
        "runtime_db_rights": "unchanged",
        "payload": archive_path.name,
        "payload_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "compose_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "files": hashes,
        "deployment": "Requires fresh approval and backup; follow docs/LOCALOS_RELEASE_2026-09-06.md",
    }
    (DESTINATION / "release-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"commit": commit, "runtime_files": len(source_paths), "ui_files": len(ui_paths),
                      "payload_sha256": manifest["payload_sha256"], "production_changed": False}))


if __name__ == "__main__":
    main()
