#!/usr/bin/env python3
import json
import os
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright


BASE_URL = "https://localos.pro"
EMAIL = "smoke-rima-agent-9d8f2a6c31@example.invalid"
PASSWORD = os.environ["SMOKE_UI_PASSWORD"]
BUSINESS_ID = "smoke-rima-agent-business-9d8f2a6c31"
OUT_DIR = Path(__file__).resolve().parent


def request_json(method, path, payload=None, token="", expected_status=200, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(payload)
    response = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)
    try:
        data = response.json() if response.text.strip() else {}
    except Exception as exc:
        raise RuntimeError(f"{method} {path}: non-json {response.status_code}: {response.text[:200]}") from exc
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path}: expected {expected_status}, got {response.status_code}: {data}")
    if data.get("success") is False:
        raise RuntimeError(f"{method} {path}: success=false: {data}")
    return data


def login_api():
    payload = request_json(
        "POST",
        "/api/auth/login",
        {"email": EMAIL, "password": PASSWORD},
        expected_status=200,
    )
    token = payload.get("token")
    if not token:
        raise RuntimeError("login did not return token")
    return token


def login_browser(page):
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.locator('input[type="email"]').fill(EMAIL)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_function("() => window.location.href.includes('/dashboard')", timeout=20000)
    page.wait_for_function(
        "() => document.body && document.body.innerText.includes('Smoke Rima Agent Business')",
        timeout=20000,
    )


def create_dialog_blueprint_in_ui(page):
    page.goto(f"{BASE_URL}/dashboard/agents", wait_until="domcontentloaded")
    page.wait_for_function(
        "() => document.body && document.body.innerText.includes('Центр управления системными и пользовательскими агентами.')",
        timeout=20000,
    )
    page.get_by_role("button", name="Создать агента").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Создать агента")).to_be_visible(timeout=10000)
    dialog.get_by_placeholder("Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт").fill(
        "Нужен агент, который проверяет договоры и ищет риски"
    )
    dialog.get_by_role("button", name="Начать диалог").click()
    expect(dialog.get_by_text("Preview будущего агента")).to_be_visible(timeout=20000)
    expect(dialog.get_by_text("Нужно уточнить", exact=True)).to_be_visible(timeout=20000)
    expect(dialog.get_by_text("Документный агент")).to_be_visible(timeout=20000)
    dialog.get_by_placeholder("Ответьте на уточнение или добавьте правило").fill(
        "Использовать DOCX и PDF договоры. Извлекать суммы, сроки, штрафы и риски. Результат нужен как краткий отчёт, перед использованием проверяет человек."
    )
    dialog.get_by_role("button", name="Ответить").click()
    page.wait_for_function(
        "() => document.body && document.body.innerText.includes('Данных достаточно')",
        timeout=20000,
    )
    dialog.get_by_role("button", name="Создать из preview").click()
    page.wait_for_function(
        "() => !document.querySelector('[role=\"dialog\"]') && document.body.innerText.includes('Нужен агент, который проверяет договоры')",
        timeout=30000,
    )
    page.screenshot(path=str(OUT_DIR / "browser-dialog-builder-created.png"), full_page=True)


def get_created_blueprint(token):
    payload = request_json("GET", f"/api/agent-blueprints?business_id={BUSINESS_ID}", token=token)
    blueprints = payload.get("blueprints") or []
    candidates = [item for item in blueprints if "проверяет договоры" in str(item.get("name") or item.get("description") or "").lower()]
    if not candidates:
        raise RuntimeError(f"dialog blueprint not found: {payload}")
    blueprint = candidates[-1]
    details = request_json("GET", f"/api/agent-blueprints/{blueprint['id']}", token=token)
    metadata = details.get("blueprint", {}).get("metadata_json") or {}
    setup = metadata.get("agent_setup") or {}
    if metadata.get("builder") != "dialog_builder_v1":
        raise RuntimeError(f"dialog builder metadata missing: {metadata}")
    if not setup.get("workflow_description") or "договор" not in setup.get("workflow_description", "").lower():
        raise RuntimeError(f"dialog setup did not persist: {setup}")
    return blueprint, details


def add_datahub_sources(token, blueprint_id):
    text_payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/sources",
        {
            "source_type": "text",
            "name": "Smoke договор контекст",
            "content_text": "Договор: оплата 15000 до 10 июня. Штраф 12% за просрочку. Срок оказания 30 дней.",
        },
        token=token,
        expected_status=201,
    )
    upload_file = {"file": ("smoke-contract.txt", b"Smoke contract upload. Payment 15000. Penalty 12%. Deadline 10 June.", "text/plain")}
    upload_payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/sources/upload",
        token=token,
        expected_status=201,
        files=upload_file,
        data={"name": "Smoke uploaded contract"},
    )
    catalog_payload = request_json("GET", f"/api/agent-blueprints/{blueprint_id}/sources/catalog", token=token)
    catalog = catalog_payload.get("catalog") or []
    connected_sources = [
        item for item in catalog
        if item.get("connected") is True and str(item.get("key") or "").startswith("agent_source:")
    ]
    titles = {str(item.get("title") or "") for item in connected_sources}
    if "Smoke договор контекст" not in titles or "Smoke uploaded contract" not in titles:
        raise RuntimeError(f"Datahub catalog missing sources: {catalog_payload}")
    states = {
        str(item.get("source_type") or ""): str(item.get("state") or "")
        for item in connected_sources
        if str(item.get("title") or "").startswith("Smoke")
    }
    if states.get("text") != "ready" or states.get("file") != "ready":
        raise RuntimeError(f"Datahub sources not ready: {catalog_payload}")
    return {"text_source": text_payload.get("source"), "upload_source": upload_payload.get("source"), "catalog_count": len(catalog)}


def run_review_feedback_version_loop(token, blueprint_id):
    run_payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/runs",
        {"input": {"source": "dialog_datahub_version_smoke"}},
        token=token,
        expected_status=201,
    )
    run = run_payload.get("run") or {}
    if run.get("status") != "waiting_approval":
        raise RuntimeError(f"run did not stop for approval: {run}")
    if [item for item in run.get("steps", []) if item.get("step_type") == "capability"]:
        raise RuntimeError(f"dialog-created run executed capability: {run}")
    output_artifacts = [item for item in run.get("artifacts", []) if item.get("artifact_type") == "agent_output_draft"]
    if not output_artifacts:
        raise RuntimeError(f"run missing output draft: {run}")
    output_payload = output_artifacts[-1].get("payload_json") or {}
    if output_payload.get("external_dispatch_performed") is not False:
        raise RuntimeError(f"external dispatch happened: {output_payload}")
    if output_payload.get("dispatch_state") != "not_dispatched":
        raise RuntimeError(f"unsafe dispatch state: {output_payload}")

    review_payload = request_json("GET", f"/api/agent-blueprints/{blueprint_id}/review", token=token)
    journal = ((review_payload.get("review") or {}).get("journal") or [])
    journal_kinds = {str(item.get("kind") or "") for item in journal if isinstance(item, dict)}
    if not {"input", "extraction", "output", "approval"}.issubset(journal_kinds):
        raise RuntimeError(f"review journal incomplete: {review_payload}")

    details = request_json("GET", f"/api/agent-blueprints/{blueprint_id}", token=token)
    active_before = details.get("active_version_id")
    active_version = next((item for item in details.get("versions", []) if item.get("id") == active_before), {})
    feedback_payload = request_json(
        "POST",
        f"/api/agent-runs/{run['id']}/feedback",
        {"feedback": "В следующей версии отдельно выделяй штрафы, даты и суммы в начале отчёта."},
        token=token,
        expected_status=201,
    )
    new_version = feedback_payload.get("version") or {}
    diff = feedback_payload.get("diff") or {}
    if not new_version.get("id") or new_version.get("id") == active_before:
        raise RuntimeError(f"feedback did not create new version: {feedback_payload}")
    if "output_schema" not in (diff.get("changed_fields") or []):
        raise RuntimeError(f"feedback diff missing output_schema change: {feedback_payload}")

    rollback_payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/versions/{active_before}/rollback",
        {"reason": "rima smoke rollback"},
        token=token,
    )
    if (rollback_payload.get("active_version") or {}).get("id") != active_before:
        raise RuntimeError(f"rollback failed: {rollback_payload}")
    activate_payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/versions/{new_version['id']}/activate",
        {"reason": "rima smoke reactivate"},
        token=token,
    )
    if (activate_payload.get("active_version") or {}).get("id") != new_version.get("id"):
        raise RuntimeError(f"activate failed: {activate_payload}")

    return {
        "run_id": run.get("id"),
        "initial_version": active_version.get("version_number"),
        "feedback_version": new_version.get("version_number"),
        "journal_kinds": sorted(journal_kinds),
        "dispatch_state": output_payload.get("dispatch_state"),
        "external_dispatch_performed": output_payload.get("external_dispatch_performed"),
        "diff_changed_fields": diff.get("changed_fields") or [],
    }


def main():
    token = login_api()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        login_browser(page)
        create_dialog_blueprint_in_ui(page)
        browser.close()

    blueprint, details = get_created_blueprint(token)
    datahub = add_datahub_sources(token, blueprint["id"])
    version_loop = run_review_feedback_version_loop(token, blueprint["id"])
    result = {
        "success": True,
        "base_url": BASE_URL,
        "business_id": BUSINESS_ID,
        "blueprint_id": blueprint["id"],
        "category": blueprint.get("category"),
        "builder": (details.get("blueprint", {}).get("metadata_json") or {}).get("builder"),
        "setup_completed": (details.get("blueprint", {}).get("metadata_json") or {}).get("setup_completed"),
        "datahub": datahub,
        "version_loop": version_loop,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
