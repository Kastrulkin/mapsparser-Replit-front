from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_frontend_dist_integrity.sh"


def _write_dist_fixture(dist_dir: Path, *, include_lazy_chunk: bool) -> None:
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        """<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="/assets/index-fixture.css">
  </head>
  <body>
    <script type="module" src="/assets/index-fixture.js"></script>
  </body>
</html>
""",
        encoding="utf-8",
    )
    (assets_dir / "index-fixture.css").write_text("body {}\n", encoding="utf-8")
    (assets_dir / "index-fixture.js").write_text(
        'const loadDashboard = () => import("./DashboardLayout-fixture.js");\n'
        "void loadDashboard;\n",
        encoding="utf-8",
    )
    if include_lazy_chunk:
        (assets_dir / "DashboardLayout-fixture.js").write_text(
            "export const DashboardLayout = {};\n",
            encoding="utf-8",
        )


def _run_integrity_check(dist_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(VERIFY_SCRIPT), str(dist_dir)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_integrity_check_rejects_missing_dynamic_import(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    _write_dist_fixture(dist_dir, include_lazy_chunk=False)

    result = _run_integrity_check(dist_dir)

    assert result.returncode != 0, (
        "Проверка целостности пропустила отсутствующий динамический модуль.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_integrity_check_accepts_complete_dynamic_import(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    _write_dist_fixture(dist_dir, include_lazy_chunk=True)

    result = _run_integrity_check(dist_dir)

    assert result.returncode == 0, result.stdout + result.stderr
