#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request

import certifi
from playwright.sync_api import sync_playwright


def create_demo_session(base_url: str) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/public-demo/session",
        data=b"",
        method="POST",
    )
    response = urllib.request.urlopen(
        request,
        timeout=20,
        context=ssl.create_default_context(cafile=certifi.where()),
    )
    try:
        return json.load(response)
    finally:
        response.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that the deployed guided-tour frontend and backend use the same version.",
    )
    parser.add_argument("--base-url", default="https://localos.pro")
    args = parser.parse_args()

    session = create_demo_session(args.base_url)
    backend_version = session["tour_version"]
    captured_request: dict = {}

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(locale="ru-RU")
    context.add_init_script(
        """
        window.localStorage.setItem('demo_auth_token', %s);
        window.sessionStorage.setItem('localos_demo_mode', '1');
        """ % json.dumps(session["token"])
    )
    page = context.new_page()

    def capture_progress(request) -> None:
        if request.method != "PUT":
            return
        if "/api/guided-tours/roga-i-kopyta-v1/progress" not in request.url:
            return
        captured_request.update(request.post_data_json or {})

    page.on("request", capture_progress)
    page.goto(f"{args.base_url.rstrip('/')}/dashboard/operator", wait_until="domcontentloaded")
    dialog = page.locator('[role="dialog"]')
    dialog.wait_for(state="visible", timeout=20_000)
    dialog.locator("button").last.click()
    page.wait_for_timeout(500)

    frontend_version = captured_request.get("tour_version")
    print(f"frontend_tour_version={frontend_version}")
    print(f"backend_tour_version={backend_version}")

    context.close()
    browser.close()
    playwright.stop()

    if frontend_version != backend_version:
        raise AssertionError(
            f"guided tour deploy mismatch: frontend={frontend_version}, backend={backend_version}"
        )


if __name__ == "__main__":
    main()
