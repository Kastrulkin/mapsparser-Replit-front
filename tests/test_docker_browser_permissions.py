"""Keep build-installed browser binaries immutable for the runtime identity."""
from pathlib import Path


def test_browser_install_does_not_copy_binaries_into_a_second_chown_layer():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text()
    assert "ARG INSTALL_PLAYWRIGHT_BROWSER=true" in dockerfile
    assert "python -m playwright install chromium" in dockerfile
    assert "USER localos:localos" in dockerfile
    ownership_commands = [line for line in dockerfile.splitlines() if "chown -R" in line]
    assert ownership_commands
    assert all("/ms-playwright" not in line for line in ownership_commands)
    assert any("/home/localos" in line and "/app/uploads" in line for line in ownership_commands)
