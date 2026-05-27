#!/usr/bin/env python3
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE_URL = "https://localos.pro"
PASSWORD = os.environ["SMOKE_UI_PASSWORD"]
OUT_DIR = Path(__file__).resolve().parent


SCENARIOS = [
    {
        "name": "email",
        "email": "smoke-email-agent-62f874d491@example.invalid",
        "run_id": "88641347-03d6-4d76-8c83-76a0e5b4e581",
        "expected": [
            "Путь письма-агента",
            "Входные данные",
            "Что понял",
            "Результат",
            "Ручной контроль",
            "Тема письма",
            "Внешняя отправка",
            "Технический журнал",
        ],
    },
    {
        "name": "tables",
        "email": "smoke-table-agent-47484062c1@example.invalid",
        "run_id": "3ecbcb2a-3453-4fc9-99a1-4e3a80c4fa2c",
        "expected": [
            "Путь таблицы-агента",
            "Входные данные",
            "Что понял",
            "Результат",
            "Ручной контроль",
            "Исключений",
            "Строк к проверке",
            "Внешняя отправка",
            "Технический журнал",
        ],
    },
    {
        "name": "reviews",
        "email": "smoke-reviews-agent-5c45084913@example.invalid",
        "run_id": "99077fe9-ed66-4256-8094-f1df8ce5b8ef",
        "expected": [
            "Путь отзывы-агента",
            "Входные данные",
            "Что понял",
            "Результат",
            "Ручной контроль",
            "Черновиков ответов",
            "Причин ручной проверки",
            "Публикация",
            "Технический журнал",
        ],
    },
]


def visible_pre_count(page):
    return page.evaluate(
        """
        () => document.querySelectorAll('details[open] pre').length
        """
    )


def readable_page_text(page):
    return page.evaluate(
        """
        () => {
          const clone = document.body.cloneNode(true);
          clone.querySelectorAll('details:not([open])').forEach((details) => {
            Array.from(details.children).forEach((child) => {
              if (child.tagName.toLowerCase() !== 'summary') {
                child.remove();
              }
            });
          });
          return clone.innerText || '';
        }
        """
    )


def login(page, email):
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.locator('input[type="email"]').fill(email)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_url("**/dashboard**", wait_until="domcontentloaded", timeout=20000)


def open_results(page, run_id):
    page.goto(f"{BASE_URL}/dashboard/agents", wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            "() => document.body && document.body.innerText.includes('Центр управления системными и пользовательскими агентами.')",
            timeout=20000,
        )
    except Exception:
        debug_name = f"debug-timeout-{run_id[:8]}"
        page.screenshot(path=str(OUT_DIR / f"{debug_name}.png"), full_page=True)
        (OUT_DIR / f"{debug_name}.txt").write_text(
            f"url={page.url}\n\n{page.locator('body').inner_text(timeout=5000)}",
            encoding="utf-8",
        )
        raise
    page.get_by_role("button", name="Сохранённые результаты").click()
    run_label = f"Запуск {run_id[:8]}"
    run_card = page.locator("button").filter(has_text=run_label).filter(has_text="Ждёт решения")
    expect(run_card).to_be_visible(timeout=20000)
    run_card.click()
    page.get_by_role("button", name="Сохранённые результаты").click()
    page.wait_for_function(
        "() => document.body && document.body.innerText.includes('Технический журнал')",
        timeout=20000,
    )


def run_scenario(browser, scenario):
    print(f"running {scenario['name']}")
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    login(page, scenario["email"])
    open_results(page, scenario["run_id"])

    body_text = readable_page_text(page)
    missing = [item for item in scenario["expected"] if item not in body_text]
    if missing:
        raise AssertionError(f"{scenario['name']}: missing visible text: {missing}")

    technical_noise = ["blueprint_version_id", "payload_json"]
    visible_noise = [item for item in technical_noise if item in body_text]
    if visible_noise:
        raise AssertionError(f"{scenario['name']}: technical noise visible by default: {visible_noise}")

    pre_count_before = visible_pre_count(page)
    if pre_count_before != 0:
        raise AssertionError(f"{scenario['name']}: JSON pre blocks visible before expanding journal: {pre_count_before}")

    page.screenshot(path=str(OUT_DIR / f"browser-{scenario['name']}-results.png"), full_page=True)
    context.close()
    return {
        "name": scenario["name"],
        "email": scenario["email"],
        "run_id": scenario["run_id"],
        "checked_text": scenario["expected"],
        "visible_pre_count_before_technical_journal": pre_count_before,
        "screenshot": f"browser-{scenario['name']}-results.png",
    }


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        results = [run_scenario(browser, scenario) for scenario in SCENARIOS]
        browser.close()
    output = {"success": True, "base_url": BASE_URL, "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
