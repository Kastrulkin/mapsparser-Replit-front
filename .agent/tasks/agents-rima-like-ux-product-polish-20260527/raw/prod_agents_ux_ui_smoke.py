#!/usr/bin/env python3
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("SMOKE_BASE_URL", "https://localos.pro").rstrip("/")
EMAIL = os.environ["SMOKE_UI_EMAIL"]
PASSWORD = os.environ["SMOKE_UI_PASSWORD"]
OUT_DIR = Path(os.getenv("SMOKE_OUT_DIR", ".agent/tasks/agents-rima-like-ux-product-polish-20260527/raw"))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.locator("input[type='email']").first.fill(EMAIL)
        page.locator("input[type='password']").first.fill(PASSWORD)
        page.locator("form button[type='submit'], button").filter(has_text="Sign in").last.click()
        page.wait_for_timeout(2500)
        page.goto(f"{BASE_URL}/dashboard/agents", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Агенты", exact=True)).to_be_visible(timeout=20000)
        expect(page.get_by_role("button", name="Создать агента", exact=True)).to_have_count(1)

        page.get_by_role("button", name="Создать агента", exact=True).click()
        expect(page.get_by_text("Preview будущего агента")).to_be_hidden(timeout=1000)
        page.get_by_placeholder("Например: мне нужен агент").fill(
            "Мне нужен агент, который готовит письмо клиенту по моему контексту и не отправляет его сам"
        )
        page.get_by_role("button", name="Начать диалог").click()
        expect(page.get_by_text("Preview будущего агента")).to_be_visible(timeout=20000)
        expect(page.get_by_text("Понял задачу так")).to_be_visible()
        expect(page.get_by_text("Данные", exact=True)).to_be_visible()
        expect(page.get_by_text("Ручной контроль", exact=True)).to_be_visible()

        if page.get_by_text("Нужно уточнить", exact=True).count() > 0 and page.get_by_text("Нужно уточнить", exact=True).is_visible():
            page.get_by_placeholder("Ответьте на уточнение").fill(
                "Использовать ручной контекст и профиль бизнеса. Результат: тема и текст письма. Отправку подтверждает человек."
            )
            page.get_by_role("button", name="Ответить").click()
            page.wait_for_timeout(1200)

        page.get_by_role("button", name="Создать из preview").click()
        expect(page.get_by_text("Агент создан")).to_be_visible(timeout=20000)
        expect(page.get_by_role("heading", name="Пользовательские агенты")).to_be_visible()
        expect(page.get_by_role("heading", name="Настройка агента")).to_be_visible()
        expect(page.get_by_text("Версия агента", exact=True)).to_be_visible()
        expect(page.get_by_text("Данные агента", exact=True).first).to_be_visible()
        expect(page.get_by_text("Сначала подключённые источники")).to_be_visible()
        expect(page.get_by_text("Подключено к агенту", exact=True)).to_be_visible()
        expect(page.get_by_text("Доступно в LocalOS", exact=True)).to_be_visible()

        page.screenshot(path=str(OUT_DIR / "prod-agents-ux-ui-smoke.png"), full_page=True)
        body = page.locator("body").inner_text()
        browser.close()

    print(
        json.dumps(
            {
                "success": True,
                "base_url": BASE_URL,
                "checked": [
                    "single create CTA",
                    "dialog builder preview",
                    "created agent banner",
                    "agent settings panel",
                    "version summary",
                    "datahub connected/available split",
                ],
                "technical_words_on_first_screen": {
                    "workflow_agents": "Workflow agents" in body,
                    "blueprint_version_id": "blueprint_version_id" in body,
                    "payload": "payload" in body,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
