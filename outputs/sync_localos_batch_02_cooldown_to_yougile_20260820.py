#!/usr/bin/env python3
"""Move the three too-fresh YouGile deals to August 24 without new tasks."""

import json
import subprocess
import sys


API = "/Users/alexdemyanov/.codex/skills/yougile-operations/scripts/yougile_api.py"
DEADLINE = 1787562000000
TASKS = {
    "Ли́ца": "9e405d5a-0433-4700-b16d-95a03f5c0788",
    "Милано": "9fe34cb5-d646-43e5-8b29-c8022cbc0d2c",
    "Петергоф-Мед": "e0e05f0c-0390-4b90-82a0-e8e3cc2a4e6d",
}


def call(method, path, payload=None):
    wrapper = "import ssl,certifi,runpy;ssl._create_default_https_context=lambda:ssl.create_default_context(cafile=certifi.where());runpy.run_path(%r,run_name='__main__')" % API
    cmd = [sys.executable, "-c", wrapper, "request", method, path]
    if payload is not None:
        cmd += ["--apply", "--data", json.dumps(payload, ensure_ascii=False)]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)


def main():
    updated = []
    for name, task_id in TASKS.items():
        task = call("GET", f"/tasks/{task_id}")
        note = (
            "Касание 21 августа заблокировано: фактическое первое письмо отправлено 20 августа, "
            "интервал менее 72 часов. Черновик не утверждён, не поставлен в очередь и не отправлен. "
            "Самая ранняя рабочая дата - 24 августа; перед отправкой нужен новый preflight."
        )
        description = str(task.get("description") or "")
        if note not in description:
            description = f"{description}\n\n{note}".strip()
        call("PUT", f"/tasks/{task_id}", {
            "title": task.get("title"), "description": description,
            "assigned": task.get("assigned") or ["095560dc-9f48-4150-b479-0310ebf0d1ad"],
            "deadline": {"deadline": DEADLINE, "withTime": False},
        })
        check = call("GET", f"/tasks/{task_id}")
        if (check.get("deadline") or {}).get("deadline") != DEADLINE or note not in str(check.get("description") or ""):
            raise RuntimeError(f"readback_failed:{name}")
        updated.append({"name": name, "task_id": task_id})
    print(json.dumps({"updated_existing_deals": len(updated), "created_tasks": 0, "items": updated}, ensure_ascii=False))


if __name__ == "__main__":
    main()
