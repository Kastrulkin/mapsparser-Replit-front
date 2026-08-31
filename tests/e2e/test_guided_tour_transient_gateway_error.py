import os
import re
import signal
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright
import pytest


APP_URL = "http://127.0.0.1:4173/dashboard/operator"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _wait_for_app() -> None:
    for _ in range(80):
        try:
            with urlopen(APP_URL, timeout=0.25) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("Vite preview did not start")


@pytest.fixture(scope="module", autouse=True)
def vite_app():
    server = subprocess.Popen(
        ["npm", "--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "4173"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_for_app()
        yield
    finally:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=10)


def test_guided_tour_advances_and_keeps_local_progress_when_progress_save_gets_502():
    progress_puts = 0
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script(
            """
            window.localStorage.setItem('demo_auth_token', 'test-demo-token');
            window.localStorage.setItem('language', 'ru');
            window.sessionStorage.setItem('localos_demo_mode', '1');
            """
        )
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def handle_api(route):
            nonlocal progress_puts
            request = route.request
            path = request.url.split("/api", 1)[-1].split("?", 1)[0]

            if path == "/auth/me":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    json={
                        "success": True,
                        "user": {
                            "id": "demo-user",
                            "email": "demo@example.test",
                            "name": "Демо",
                            "session_kind": "demo",
                            "demo_mode": True,
                            "demo_scope_business_id": "demo-business",
                            "demo_room_slug": "demo-room",
                        },
                        "businesses": [
                            {
                                "id": "demo-business",
                                "name": "Рога и копыта",
                                "subscription_tier": "demo",
                                "subscription_status": "active",
                            }
                        ],
                    },
                )
                return

            if path == "/guided-tours/roga-i-kopyta-v1/progress" and request.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    json={
                        "success": True,
                        "progress": {
                            "status": "not_started",
                            "step_key": "welcome",
                            "completed_steps": [],
                        },
                    },
                )
                return

            if path == "/guided-tours/roga-i-kopyta-v1/progress" and request.method == "PUT":
                progress_puts += 1
                if progress_puts == 2:
                    route.fulfill(
                        status=502,
                        content_type="text/html",
                        body="<html><body><h1>502 Bad Gateway</h1></body></html>",
                    )
                    return
                route.fulfill(status=200, content_type="application/json", json={"success": True})
                return

            if path == "/guided-tours/roga-i-kopyta-v1/events":
                route.fulfill(status=201, content_type="application/json", json={"success": True})
                return

            if path == "/operator/conversations/current":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    json={"messages": [], "conversation": None},
                )
                return

            route.fulfill(status=200, content_type="application/json", json={"success": True})

        page.route("**/api/**", handle_api)
        page.goto(APP_URL, wait_until="domcontentloaded")

        start_button = page.get_by_role("button", name="Начать знакомство")
        expect(start_button).to_be_visible()
        start_button.click()

        step_indicator = page.get_by_text("Шаг 2 из 44", exact=True)
        expect(step_indicator).to_be_visible()
        page.get_by_role("button", name="Дальше").click()

        page.wait_for_timeout(100)
        rendered_step = page.get_by_text(re.compile(r"^Шаг \d+ из 44$"))
        assert not page_errors, f"Unexpected unhandled errors: {page_errors}"
        expect(rendered_step).to_have_text("Шаг 3 из 44")
        expect(page.get_by_text("Не удалось сохранить прогресс. Попробуйте ещё раз.", exact=True)).to_have_count(0)
        local_progress = page.evaluate("Object.values(sessionStorage).find(value => value.includes('today-overview'))")
        assert local_progress

        context.close()
        browser.close()
