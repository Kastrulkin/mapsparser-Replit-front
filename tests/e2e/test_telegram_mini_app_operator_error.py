import os
import signal
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_URL = "http://127.0.0.1:4187/telegram/control?preview=1"


def _wait_for_app() -> None:
    for _ in range(80):
        try:
            with urlopen(APP_URL, timeout=0.25) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("Vite preview did not start")


def test_operator_hides_raw_json_parse_errors_from_the_user():
    server = subprocess.Popen(
        ["npm", "--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1", "--port", "4187"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        _wait_for_app()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 393, "height": 852})
            page.route(
                "**/api/operator/chat",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="Internal gateway response",
                ),
            )
            page.goto(APP_URL)
            page.get_by_placeholder("Например: подготовь ответы").fill("Что ты умеешь")
            page.get_by_label("Отправить").click()

            expect(page.get_by_text("Сервис временно вернул некорректный ответ. Попробуйте ещё раз.")).to_be_visible()
            expect(page.get_by_text("Unexpected token", exact=False)).to_have_count(0)
            browser.close()
    finally:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=10)
