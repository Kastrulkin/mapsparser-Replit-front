#!/usr/bin/env python3
"""Mirror verified v4 email sends into LocalOS CRM deal cards in YouGile."""

import json
import subprocess
import time
from pathlib import Path


PROJECT_ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре")
YOUGILE = Path("/Users/alexdemyanov/.codex/skills/yougile-operations/scripts/yougile_api.py")
SSH_KEY = Path.home() / ".ssh/localos_prod"
REMOTE_HOST = "root@80.78.242.105"
REMOTE_ROOT = "/opt/seo-app"
REMOTE_LOG = "debug_data/v4-email-dispatch-live-20260820.log"
REMOTE_SESSION = "v4-email-dispatch-20260820"
COLUMN_ID = "e26beae7-d1c8-4017-8020-4458e9069c24"
USER_ID = "095560dc-9f48-4150-b479-0310ebf0d1ad"
STATE_PATH = PROJECT_ROOT / "outputs/yougile-v4-email-sync-state-20260820.json"
LOG_PATH = PROJECT_ROOT / "outputs/yougile-v4-email-sync-20260820.jsonl"


def run_json(command):
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def yougile(method, path, payload=None):
    command = [str(YOUGILE), "request", method, path]
    if payload is not None:
        command.extend(["--apply", "--data", json.dumps(payload, ensure_ascii=False)])
    return run_json(command)


def remote_state():
    command = [
        "ssh", "-i", str(SSH_KEY), "-o", "ConnectTimeout=15", REMOTE_HOST,
        f"cd {REMOTE_ROOT} && cat {REMOTE_LOG} 2>/dev/null || true; "
        f"tmux has-session -t {REMOTE_SESSION} 2>/dev/null && echo __SESSION_RUNNING__ || echo __SESSION_STOPPED__",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    running = "__SESSION_RUNNING__" in lines
    records = []
    for line in lines:
        if not line.startswith("{"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records, running


def write_log(payload):
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def description(item):
    return (
        "Подтверждено касаний: 1. Первое касание — Email, отправлено 20 августа 2026 "
        f"с localosgo@gmail.com на {item['recipient']}. touch_id: {item['touch_id']}. "
        "Статус: ожидание входящего ответа; отдельная задача проверки ответа не создаётся."
    )


def sync_item(item, tasks):
    touch_id = item["touch_id"]
    recipient = item["recipient"]
    name = item["name"]
    exact = next(
        (task for task in tasks if touch_id in str(task.get("description") or "")),
        None,
    )
    if exact:
        return exact["id"], "already_synced"
    candidates = [
        task for task in tasks
        if task.get("type") == "deal"
        and (
            recipient in str(task.get("description") or "")
            or str(task.get("title") or "").strip().casefold() in {
                name.strip().casefold(), f"сделка с {name}".casefold()
            }
        )
    ]
    payload = {
        "title": f"Сделка с {name}",
        "columnId": COLUMN_ID,
        "description": description(item),
        "assigned": [USER_ID],
        "deadline": None,
    }
    if candidates:
        task_id = candidates[0]["id"]
        yougile("PUT", f"/tasks/{task_id}", payload)
        candidates[0].update(payload)
        return task_id, "updated"
    created = yougile("POST", "/tasks", payload)
    task_id = created["id"]
    tasks.append({"id": task_id, "type": "deal", **payload})
    return task_id, "created"


def main():
    tasks = yougile("GET", "/tasks?limit=1000&offset=0").get("content") or []
    synced = set()
    if STATE_PATH.exists():
        synced.update(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("touch_ids") or [])
    while True:
        records, running = remote_state()
        sent_records = [record for record in records if record.get("status") == "sent"]
        for item in sent_records:
            touch_id = str(item.get("touch_id") or "")
            if not touch_id or touch_id in synced:
                continue
            task_id, action = sync_item(item, tasks)
            readback = yougile("GET", f"/tasks/{task_id}")
            if readback.get("type") != "deal" or readback.get("deadline"):
                raise RuntimeError(f"yougile_readback_failed:{task_id}")
            synced.add(touch_id)
            STATE_PATH.write_text(
                json.dumps({"touch_ids": sorted(synced)}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            write_log({"status": "synced", "touch_id": touch_id, "name": item.get("name"), "task_id": task_id, "action": action})
        complete = any(record.get("status") == "complete" for record in records)
        if complete or (not running and sent_records):
            break
        time.sleep(30)
    write_log({"status": "complete", "synced": len(synced)})


if __name__ == "__main__":
    main()
