"""Keep CI gates wired to the frontend's referenced TypeScript projects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
TSC = ROOT / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
PACKAGE_JSON = ROOT / "frontend" / "package.json"
GATES = ("scripts/ci_gate_fast.sh", "scripts/ci_gate_nightly.sh")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _typecheck_fixture(tmp_path: Path, broken_project: str | None) -> Path:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    typecheck = package["scripts"]["typecheck"]
    _write(
        frontend / "package.json",
        json.dumps({"scripts": {"typecheck": typecheck}}) + "\n",
    )
    bin_dir = frontend / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "tsc").symlink_to(TSC)
    _write(
        frontend / "tsconfig.json",
        """{
  \"files\": [],
  \"references\": [
    { \"path\": \"./tsconfig.app.json\" },
    { \"path\": \"./tsconfig.node.json\" }
  ]
}
""",
    )
    _write(
        frontend / "tsconfig.app.json",
        """{
  \"compilerOptions\": { \"noEmit\": true, \"strict\": true },
  \"include\": [\"app.ts\"]
}
""",
    )
    _write(
        frontend / "tsconfig.node.json",
        """{
  \"compilerOptions\": { \"noEmit\": true, \"strict\": true },
  \"include\": [\"node.ts\"]
}
""",
    )
    _write(frontend / "app.ts", "const appValue: string = 'healthy';\n")
    _write(frontend / "node.ts", "const nodeValue: string = 'healthy';\n")
    if broken_project == "app":
        _write(frontend / "app.ts", "const appValue: string = 42;\n")
    if broken_project == "node":
        _write(frontend / "node.ts", "const nodeValue: string = 42;\n")
    return frontend


def _write_gate_stubs(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python_stub = bin_dir / "python"
    npm_stub = bin_dir / "npm"
    npx_stub = bin_dir / "npx"
    _write(python_stub, "#!/bin/sh\nexit 0\n")
    _write(npx_stub, "#!/bin/sh\nexit 0\n")
    _write(
        npm_stub,
        """#!/bin/sh
set -eu
if [ "${1:-}" = "--prefix" ] && [ "${2:-}" = "frontend" ] && [ "${3:-}" = "run" ] && [ "${4:-}" = "typecheck" ]; then
  printf '%s\\n' typecheck >> "$CI_TYPECHECK_NPM_LOG"
  "$CI_TYPECHECK_REAL_NPM" --prefix "$CI_TYPECHECK_FRONTEND" run typecheck
fi
exit 0
""",
    )
    return python_stub, npm_stub


def _run_gate(
    gate: str,
    frontend: Path,
    tmp_path: Path,
) -> tuple[subprocess.CompletedProcess[str], str]:
    python_stub, npm_stub = _write_gate_stubs(tmp_path)
    log_path = tmp_path / "npm.log"
    environment = {
        **os.environ,
        "PYTHON_BIN": str(python_stub),
        "CI_TYPECHECK_REAL_NPM": shutil.which("npm") or "",
        "CI_TYPECHECK_FRONTEND": str(frontend),
        "CI_TYPECHECK_NPM_LOG": str(log_path),
        "LOCALOS_TEST_DATABASE_URL": "postgresql://localos_test:localos_test@127.0.0.1:5432/localos_ci_test",
        "PATH": f"{npm_stub.parent}{os.pathsep}{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", gate],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    npm_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return result, npm_log


@pytest.mark.parametrize("gate", GATES)
@pytest.mark.parametrize("broken_project", (None, "app", "node"))
def test_ci_gate_typecheck_compiles_referenced_projects(
    tmp_path: Path,
    gate: str,
    broken_project: str | None,
) -> None:
    if not TSC.is_file() or shutil.which("node") is None or shutil.which("npm") is None:
        pytest.skip("locked frontend TypeScript compiler or npm is unavailable")

    frontend = _typecheck_fixture(tmp_path, broken_project)
    bare_compiler = subprocess.run(
        ["node", str(TSC), "--noEmit"],
        cwd=frontend,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert bare_compiler.returncode == 0

    result, npm_log = _run_gate(gate, frontend, tmp_path)
    if broken_project is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        assert f"{broken_project}.ts" in result.stdout
    assert npm_log == "typecheck\n"
