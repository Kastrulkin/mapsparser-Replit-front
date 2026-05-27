#!/usr/bin/env python3
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE_URL = "https://localos.pro"
EMAIL = "smoke-wizard-agent-b7e6d31942@example.invalid"
PASSWORD = os.environ["SMOKE_UI_PASSWORD"]
OUT_DIR = Path(__file__).resolve().parent


SCENARIOS = [
    {
        "name": "email",
        "title": "Письма",
        "prompt": "Smoke wizard email: подготовь письмо клиенту по контексту и не отправляй наружу",
        "source_name": "Контекст письма",
        "source_text": "Адресат: Мария. Услуга: консультация по уходу. Цель: пригласить на запись без скидок.",
        "data_sources": "ручной контекст, профиль бизнеса",
        "extraction": "адресат, услуга, цель письма, ограничения по обещаниям",
        "processing": "коротко, дружелюбно, без внешней отправки",
        "output": "тема письма, черновик, чеклист проверки",
        "manual_control": "перед использованием и перед любой отправкой",
        "path_label": "Путь письма-агента",
        "expected": ["Тема письма", "Внешняя отправка", "Ручной контроль"],
    },
    {
        "name": "tables",
        "title": "Таблицы",
        "prompt": "Smoke wizard tables: проверь CSV клиентов, найди дубли и пустые поля",
        "source_name": "clients.csv",
        "source_text": "name,email,phone\nАнна,anna@example.com,+1\nАнна,anna@example.com,+1\nБорис,,+2\n",
        "data_sources": "CSV, ручной контекст",
        "extraction": "пустые email, дубли, строки к проверке",
        "processing": "не менять данные, только подготовить отчёт",
        "output": "summary, exceptions, rows_to_review, recommendations",
        "manual_control": "перед импортом или отправкой отчёта",
        "path_label": "Путь таблицы-агента",
        "expected": ["Исключений", "Строк к проверке", "Внешняя отправка"],
    },
    {
        "name": "reviews",
        "title": "Отзывы",
        "prompt": "Smoke wizard reviews: подготовь ответы на отзывы в стиле бизнеса и не публикуй",
        "source_name": "reviews.csv",
        "source_text": "author_name,rating,text\nАнна,5,Очень понравился сервис\nИван,2,Долго ждал администратора\n",
        "data_sources": "отзывы, ручной контекст, профиль бизнеса",
        "extraction": "тональность, проблема клиента, безопасный ответ",
        "processing": "не обещать компенсацию, негативные отзывы помечать отдельно",
        "output": "reply_drafts, manual_review_reasons, checklist",
        "manual_control": "публикация только вручную после проверки",
        "path_label": "Путь отзывы-агента",
        "expected": ["Черновиков ответов", "Причин ручной проверки", "Публикация"],
    },
]


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


def visible_open_pre_count(page):
    return page.evaluate("() => document.querySelectorAll('details[open] pre').length")


def login(page):
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.locator('input[type="email"]').fill(EMAIL)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_function("() => window.location.href.includes('/dashboard')", timeout=20000)
    page.wait_for_function(
        "() => document.body && document.body.innerText.includes('Smoke Wizard Agent Business')",
        timeout=20000,
    )


def open_agents(page):
    page.goto(f"{BASE_URL}/dashboard/agents", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    text = page.locator("body").inner_text(timeout=10000)
    if "Центр управления системными и пользовательскими агентами." not in text:
        page.screenshot(path=str(OUT_DIR / "debug-open-agents-timeout.png"), full_page=True)
        (OUT_DIR / "debug-open-agents-timeout.txt").write_text(f"url={page.url}\n\n{text}", encoding="utf-8")
        raise AssertionError("agents page did not load expected header")


def fill_labeled_textarea(dialog, label, value):
    field = dialog.locator("label").filter(has_text=label).locator("textarea")
    expect(field).to_be_visible(timeout=10000)
    field.fill(value)


def create_agent(page, scenario):
    page.get_by_role("button", name="Создать агента").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Создать агента")).to_be_visible(timeout=10000)

    dialog.get_by_text("Открыть ручной мастер").click()
    scenario_button = dialog.locator("button").filter(has_text=scenario["title"])
    scenario_button.first.click()

    dialog.get_by_placeholder("Опишите, какого агента хотите создать").fill(scenario["prompt"])
    dialog.get_by_role("button", name="Далее").click()

    fill_labeled_textarea(dialog, "Какие данные использовать", scenario["data_sources"])
    dialog.get_by_placeholder("Название источника").fill(scenario["source_name"])
    dialog.get_by_placeholder("Вставьте текст, CSV или контекст задачи").fill(scenario["source_text"])
    dialog.get_by_role("button", name="Далее").click()

    fill_labeled_textarea(dialog, "Что агент должен извлечь или понять", scenario["extraction"])
    fill_labeled_textarea(dialog, "Какие правила применить", scenario["processing"])
    fill_labeled_textarea(dialog, "Где нужен ручной контроль", scenario["manual_control"])
    dialog.get_by_role("button", name="Далее").click()

    fill_labeled_textarea(dialog, "Какой результат подготовить", scenario["output"])
    dialog.get_by_role("button", name="Создать агента").click()
    page.wait_for_function(
        "(prompt) => document.body && document.body.innerText.includes(prompt) && !document.querySelector('[role=\"dialog\"]')",
        arg=scenario["prompt"],
        timeout=30000,
    )


def run_created_agent(page, scenario):
    card = page.locator("button").filter(has_text=scenario["prompt"])
    expect(card.first).to_be_visible(timeout=20000)
    card.first.click()
    page.get_by_role("button", name="Запуск", exact=True).click()
    run_button = page.locator("button").filter(has_text="Запустить").last
    run_button.click()
    page.wait_for_function(
        "(label) => document.body && document.body.innerText.includes(label)",
        arg=scenario["path_label"],
        timeout=60000,
    )
    for expected in scenario["expected"]:
        page.wait_for_function(
            "(label) => document.body && document.body.innerText.includes(label)",
            arg=expected,
            timeout=60000,
        )
    text = readable_page_text(page)
    missing = [item for item in [scenario["path_label"], "Входные данные", "Что понял", "Результат", *scenario["expected"]] if item not in text]
    if missing:
        raise AssertionError(f"{scenario['name']}: missing visible review text: {missing}")
    if visible_open_pre_count(page) != 0:
        raise AssertionError(f"{scenario['name']}: technical JSON is open by default")
    page.screenshot(path=str(OUT_DIR / f"browser-{scenario['name']}-created-run.png"), full_page=True)
    return {
        "name": scenario["name"],
        "prompt": scenario["prompt"],
        "path_label": scenario["path_label"],
        "checked_text": [scenario["path_label"], "Входные данные", "Что понял", "Результат", *scenario["expected"]],
        "visible_open_pre_count": visible_open_pre_count(page),
        "screenshot": f"browser-{scenario['name']}-created-run.png",
    }


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()
        login(page)
        results = []
        for scenario in SCENARIOS:
            open_agents(page)
            create_agent(page, scenario)
            results.append(run_created_agent(page, scenario))
        context.close()
        browser.close()
    print(json.dumps({"success": True, "base_url": BASE_URL, "email": EMAIL, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
