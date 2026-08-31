#!/usr/bin/env python3
"""Fail closed when the rendered LocalOS staging Compose config can reach real integrations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.staging.yml")
RUNTIME_SERVICES = ("app", "worker", "telegram-bot")
DISABLED_FLAGS = (
    "AGENT_ASYNC_RUNS_ENABLED",
    "AGENT_SCHEDULE_DISPATCH_ENABLED",
    "INFLUENCER_OUTREACH_ENABLED",
    "JOURNEY_NOTIFICATIONS_ENABLED",
    "OPERATOR_APIFY_REFRESH_ENABLED",
    "OUTREACH_DISPATCH_ENABLED",
    "OUTREACH_EMAIL_THREAD_SYNC_ENABLED",
    "OUTREACH_TELEGRAM_THREAD_SYNC_ENABLED",
    "SOCIAL_POST_DISPATCH_ENABLED",
)
PROVIDER_CREDENTIALS = (
    "APIFY_TOKEN",
    "APIFY_ACTOR_ID",
    "APIFY_YANDEX_ACTOR_ID",
    "APIFY_2GIS_ACTOR_ID",
    "APIFY_TWOGIS_ACTOR_ID",
    "APIFY_PROXY_URL",
    "APIFY_HTTP_PROXY",
    "APIFY_HTTPS_PROXY",
    "CRYPTO_PAY_API_TOKEN",
    "CRYPTO_PAY_WEBHOOK_SECRET",
    "DEEPSEEK_API_KEY",
    "GIGACHAT_KEYS",
    "GIGACHAT_CLIENT_ID",
    "GIGACHAT_CLIENT_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH_STATE_SECRET",
    "GOOGLE_SHEETS_CLIENT_ID",
    "GOOGLE_SHEETS_CLIENT_SECRET",
    "HUNTER_API_KEY",
    "MEDIA_S3_ACCESS_KEY_ID",
    "MEDIA_S3_SECRET_ACCESS_KEY",
    "META_OAUTH_APP_ID",
    "META_OAUTH_APP_SECRET",
    "META_OAUTH_CONFIG_ID",
    "META_OAUTH_STATE_SECRET",
    "OPENCLAW_LOCALOS_TOKEN",
    "OPENCLAW_SANDBOX_BRIDGE_TOKEN",
    "OPENCLAW_TOKEN",
    "OUTBOUND_HTTP_PROXY",
    "OUTREACH_VK_SECRET_KEY",
    "SALES_ROOM_S3_ACCESS_KEY_ID",
    "SALES_ROOM_S3_SECRET_ACCESS_KEY",
    "TELEGRAM_HTTP_PROXY",
    "TELEGRAM_PROXY_URL",
    "TELEGRAM_REVIEWS_BOT_TOKEN",
    "TELEGRAM_USERBOT_MTPROXY_HOST",
    "TELEGRAM_USERBOT_MTPROXY_PORT",
    "TELEGRAM_USERBOT_MTPROXY_SECRET",
    "TELEGRAM_USERBOT_PROXY",
    "VK_OAUTH_CLIENT_ID",
    "VK_OAUTH_STATE_SECRET",
    "WHATSAPP_VERIFY_TOKEN",
    "YANDEX_AI_API_KEY",
    "YANDEX_WORDSTAT_API_KEY",
    "YANDEX_WORDSTAT_CLIENT_ID",
    "YANDEX_WORDSTAT_CLIENT_SECRET",
    "YANDEX_WORDSTAT_OAUTH_TOKEN",
    "YOOKASSA_SHOP_ID",
    "YOOKASSA_SECRET_KEY",
)


def rendered_config() -> dict[str, Any]:
    command = ["docker", "compose"]
    for compose_file in COMPOSE_FILES:
        command.extend(("-f", compose_file))
    command.extend(("config", "--format", "json"))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def validate(config: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    services = config.get("services") if isinstance(config.get("services"), dict) else {}

    for service_name in RUNTIME_SERVICES:
        service = services.get(service_name) if isinstance(services.get(service_name), dict) else {}
        environment = service.get("environment") if isinstance(service.get("environment"), dict) else {}
        mounts = service.get("volumes") if isinstance(service.get("volumes"), list) else []

        if environment.get("APP_ENV") != "staging":
            failures.append(f"{service_name}: APP_ENV must be staging")
        database_url = str(environment.get("DATABASE_URL") or "")
        if "localos_staging" not in database_url or "@postgres:5432/localos_staging" not in database_url:
            failures.append(f"{service_name}: DATABASE_URL is not isolated staging")
        if mounts:
            failures.append(f"{service_name}: host mounts are forbidden in staging")
        for credential in PROVIDER_CREDENTIALS:
            if str(environment.get(credential) or "").strip():
                failures.append(f"{service_name}: {credential} must be blank")
        for flag in DISABLED_FLAGS:
            if str(environment.get(flag) or "false").strip().lower() not in {"0", "false", "no", "off"}:
                failures.append(f"{service_name}: {flag} must be disabled")

    app = services.get("app") if isinstance(services.get("app"), dict) else {}
    app_environment = app.get("environment") if isinstance(app.get("environment"), dict) else {}
    if app_environment.get("TELEGRAM_BOT_TOKEN") != "localos-staging-e2e-bot-token":
        failures.append("app: TELEGRAM_BOT_TOKEN must use the synthetic staging value")
    if app_environment.get("SMTP_SERVER") != "localhost" or str(app_environment.get("SMTP_PORT")) != "1":
        failures.append("app: SMTP transport must be the unreachable local staging sink")
    if app_environment.get("OPERATOR_MAP_REFRESH_SOURCE") != "yandex_maps":
        failures.append("app: map refresh must use the built-in parser")

    postgres = services.get("postgres") if isinstance(services.get("postgres"), dict) else {}
    postgres_environment = postgres.get("environment") if isinstance(postgres.get("environment"), dict) else {}
    if postgres_environment.get("POSTGRES_DB") != "localos_staging":
        failures.append("postgres: database must be localos_staging")

    return failures


def main() -> int:
    try:
        failures = validate(rendered_config())
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Staging isolation check could not render Compose: {type(exc).__name__}", file=sys.stderr)
        return 2
    if failures:
        print("Staging isolation check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Staging isolation check passed: no host mounts or real provider credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
