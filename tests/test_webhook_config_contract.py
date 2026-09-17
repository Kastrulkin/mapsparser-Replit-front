"""Keep webhook authentication configuration wired through Docker environments."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_passes_whatsapp_signing_secret_and_staging_blanks_it():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    app = compose.split("\n  app:\n", 1)[1].split("\n  worker:\n", 1)[0]
    assert "WHATSAPP_APP_SECRET: ${WHATSAPP_APP_SECRET:-}" in app
    staging = (ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    assert 'WHATSAPP_APP_SECRET: ""' in staging


def test_staging_validator_rejects_provider_signing_secret():
    spec = importlib.util.spec_from_file_location(
        "staging_isolation_webhook_contract", ROOT / "scripts/check_staging_isolation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failures = module.validate({
        "services": {"app": {"environment": {"WHATSAPP_APP_SECRET": "synthetic-test-secret"}}}
    })
    assert "app: WHATSAPP_APP_SECRET must be blank" in failures
