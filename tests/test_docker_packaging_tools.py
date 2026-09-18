"""Static contracts for patched Python packaging tools in final images."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_pins_pip_before_resolving_application_dependencies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    base_image = "FROM python:3.11-bookworm"
    assert base_image in dockerfile
    pin = '"pip==26.2"'
    pin_index = dockerfile.index(pin)
    requirements_copy_index = dockerfile.index("COPY requirements.txt .")
    requirements_install_index = dockerfile.index("-r requirements.txt")

    assert "python -m pip install" in dockerfile[:pin_index]
    assert dockerfile.index(base_image) < pin_index < requirements_copy_index < requirements_install_index
    pin_block = dockerfile[pin_index - 500:requirements_copy_index]
    assert "--index-url https://mirrors.aliyun.com/pypi/simple" in pin_block
    assert "--extra-index-url https://pypi.org/simple" in pin_block
    assert "pip==" not in requirements
    packaging_layer = dockerfile[requirements_install_index:]
    assert "pip==" not in packaging_layer


def test_telegram_image_inherits_the_patched_app_image_without_downgrade() -> None:
    telegram = (ROOT / "Dockerfile.telegram").read_text(encoding="utf-8")
    app = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert telegram.splitlines()[0] == "FROM seo-app-app"
    assert '"pip==26.2"' in app
    assert "pip==" not in telegram
