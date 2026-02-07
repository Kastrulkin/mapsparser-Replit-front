"""
Общая конфигурация pytest.
- PYTHONPATH: src в пути для импорта worker, main, pg_db_utils и т.д.
- Детекция Docker: реальная проверка docker daemon (ping); skip только если Docker недоступен.
- Postgres (testcontainers) и запуск миграций для gate-тестов /api/client-info.
"""
import os
import pytest
import subprocess
import sys
from pathlib import Path

# Добавляем src в PYTHONPATH, чтобы можно было `import worker, parser_interception, main`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _docker_available() -> bool:
    """Проверка доступности Docker daemon (реальная, не флаги)."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _run_flask_db_upgrade(project_root: Path, database_url: str) -> None:
    """Выполнить flask db upgrade с заданным DATABASE_URL (для testcontainers)."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env.setdefault("FLASK_APP", "src.main:app")
    env["PYTHONPATH"] = os.pathsep.join([str(project_root / "src"), str(project_root)])
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"flask db upgrade failed (exit {result.returncode}). "
            f"Install: pip install -r requirements.test.txt (flask-migrate, flask-sqlalchemy). "
            f"stderr: {result.stderr or result.stdout}"
        )


@pytest.fixture(scope="module")
def postgres_container():
    """
    PostgreSQL через testcontainers. Один раз на модуль.
    Skip только если Docker реально недоступен (docker.from_env().ping()).
    """
    if not _docker_available():
        pytest.skip("Docker daemon unavailable (docker.from_env().ping() failed)")
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError as e:
        pytest.skip(f"testcontainers not available: {e}")
    with PostgresContainer("postgres:14") as postgres:
        yield postgres


@pytest.fixture(scope="module")
def run_migrations(postgres_container):
    """
    Выполнить flask db upgrade перед тестами, чтобы в БД были
    users, businesses, parsequeue, businessmaplinks и др.
    Зависит от postgres_container (тот же модуль).
    """
    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1) if "postgresql+psycopg2" in raw_url else raw_url
    _run_flask_db_upgrade(PROJECT_ROOT, dsn)
    yield
