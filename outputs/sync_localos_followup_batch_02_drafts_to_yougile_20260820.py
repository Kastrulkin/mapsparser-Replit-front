#!/usr/bin/env python3
"""Update only exact existing YouGile deal cards for batch-two drafts."""

import json
import ssl
import subprocess
import sys
from pathlib import Path

import certifi


ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре")
FINAL = ROOT / "outputs/localos-followup-batch-02-final-20260820.json"
YOUGILE = "/Users/alexdemyanov/.codex/skills/yougile-operations/scripts/yougile_api.py"
DEADLINE = 1787302800000
TASK_IDS = {
    "АМД Лаборатории": "a73e0dc6-e6d6-4bca-a528-2f0080b4a100",
    "Монрепо": "fd871a32-559c-4970-a6bc-a8319e7103bd",
    "Микшель": "34e7c00b-7c59-4908-b864-65d561d8b6cf",
    "D. O. M. Beauty bar": "cab65b45-5f25-47ce-86d8-6be3559b7602",
    "Dk Clinic": "6db17970-66c3-4bb7-bc8e-e14fd106164e",
    "GinkgoLab": "8c20f02c-7b09-4c71-b41d-b0ba63fde969",
    "La Clinique": "403b5da2-3b73-42bc-8e68-ba00dc1c561f",
    "LuA. Clinic": "54b0427b-939d-47cc-8921-e67804408730",
    "Myrtille": "2af09500-5c03-49f0-b01b-49644b40bdf4",
    "PF&Beauty": "714ed779-4bd4-4bb0-9c65-d394090b94fd",
    "Ботаника": "06080f7f-72e0-4f4b-bad4-8de4ec751c81",
    "Инскин": "ad9d0014-09b0-4fba-a941-9fe7a2899108",
    "Ли́ца": "9e405d5a-0433-4700-b16d-95a03f5c0788",
    "Медикор": "df738bec-19b0-4eaa-a6d0-9d7c0ddfad99",
    "Милано": "9fe34cb5-d646-43e5-8b29-c8022cbc0d2c",
    "Модифик": "df53d492-2007-4124-948c-b8ef10f10e80",
    "Петергоф-Мед": "e0e05f0c-0390-4b90-82a0-e8e3cc2a4e6d",
    "Привилегия Здоровья": "10722cab-33f2-481d-81b9-db5731d90245",
    "Путь к здоровью": "f7e0bbf5-c1d7-4f5e-8ae6-547c8ccf00c4",
    "Сирин": "b050b20e-9f3d-4acb-85d0-36944d116dcb",
}
STALE_TOUCH_IDS = {
    "D. O. M. Beauty bar": "77b0389b-59ac-4e1f-bb4d-9dfb8f03d2e6",
    "Милано": "c550a7bc-5acf-4fc9-942b-d96b55be011e",
    "Петергоф-Мед": "01abda32-5f99-4172-bd2c-4b6ceab5fb8e",
}


def yougile(method, path, payload=None):
    wrapper = (
        "import ssl,certifi,runpy;"
        "ssl._create_default_https_context=lambda:ssl.create_default_context(cafile=certifi.where());"
        f"runpy.run_path({YOUGILE!r},run_name='__main__')"
    )
    command = [sys.executable, "-c", wrapper, "request", method, path]
    if payload is not None:
        command.extend(["--apply", "--data", json.dumps(payload, ensure_ascii=False)])
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    items = final.get("items") or []
    if len(items) != 20 or set(TASK_IDS) != {x.get("name") for x in items}:
        raise RuntimeError("final_to_yougile_mapping_mismatch")
    updated = []
    for item in items:
        name = item["name"]
        task_id = TASK_IDS[name]
        task = yougile("GET", f"/tasks/{task_id}")
        if task.get("completed") or task.get("archived") or task.get("type") != "deal":
            raise RuntimeError(f"yougile_task_not_open_deal:{name}:{task_id}")
        expected_titles = {name.casefold(), f"сделка с {name}".casefold()}
        if str(task.get("title") or "").strip().casefold() not in expected_titles:
            raise RuntimeError(f"yougile_title_mismatch:{name}:{task.get('title')}")
        touch_id = item["proposed_touch_id"]
        note = (
            f"Второе email-касание подготовлено на 21 августа 2026. "
            f"Получатель: {item['recipient']}. touch_id: {touch_id}. "
            "Статус: draft; текст не утверждён, не поставлен в очередь и не отправлен. "
            "Перед отправкой нужны свежий preflight и явное разрешение. "
            "Отдельную задачу проверки ответа не создавать."
        )
        description = str(task.get("description") or "").strip()
        stale_touch_id = STALE_TOUCH_IDS.get(name)
        if stale_touch_id and stale_touch_id != touch_id:
            description = description.replace(stale_touch_id, touch_id)
        if touch_id not in description:
            description = f"{description}\n\n{note}".strip()
        payload = {
            "title": task.get("title"),
            "description": description,
            "assigned": task.get("assigned") or ["095560dc-9f48-4150-b479-0310ebf0d1ad"],
            "deadline": {"deadline": DEADLINE, "withTime": False},
        }
        yougile("PUT", f"/tasks/{task_id}", payload)
        check = yougile("GET", f"/tasks/{task_id}")
        if touch_id not in str(check.get("description") or "") or (check.get("deadline") or {}).get("deadline") != DEADLINE:
            raise RuntimeError(f"yougile_readback_failed:{name}:{task_id}")
        updated.append({"name": name, "task_id": task_id, "touch_id": touch_id})
    print(json.dumps({"updated_existing_deals": len(updated), "created_tasks": 0, "items": updated}, ensure_ascii=False))


if __name__ == "__main__":
    main()
