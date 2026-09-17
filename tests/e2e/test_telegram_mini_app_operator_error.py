from playwright.sync_api import expect, sync_playwright

from tests.e2e.vite_harness import IsolatedViteApp, guard_browser_requests

def test_operator_hides_raw_json_parse_errors_from_the_user():
    app = IsolatedViteApp("/telegram/control?preview=1")
    try:
        app.start()
        app_url = app.url
        port = app.port
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 393, "height": 852})
            def handle_api(route):
                route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="Internal gateway response",
                )

            guard_browser_requests(page, port, handle_api)
            page.goto(app_url)
            page.get_by_placeholder("Например: подготовь ответы").fill("Что ты умеешь")
            page.get_by_label("Отправить").click()

            expect(page.get_by_text("Сервис временно вернул некорректный ответ. Попробуйте ещё раз.")).to_be_visible()
            expect(page.get_by_text("Unexpected token", exact=False)).to_have_count(0)
            browser.close()
    finally:
        app.stop()
