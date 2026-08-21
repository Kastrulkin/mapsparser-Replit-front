#!/usr/bin/env python3
"""Select exactly 20 reviewed drafts and freeze batch 01 for user approval."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


PRIMARY = Path("/app/debug_data/localos-followup-batch-01-review-20260820.json")
SUPPLEMENT = Path("/app/debug_data/localos-followup-batch-01-supplement-review-20260820.json")
OUTPUT = Path("/app/debug_data/localos-followup-batch-01-final-20260820.json")
SELECTED_NAMES = [
    "Позитивмед",
    "Алс-Мед",
    "NuAnce",
    "stomatologicheskiy kompleks novoperedelkino",
    "Гера",
    "Лазерта",
    "Ликс",
    "Newme",
    "Ультраклиника",
    "Медика Стар",
    "Общество Чистых Лиц",
    "Центр семейной медицины Тельмана",
    "Кристина",
    "ЛюбиЗуб",
    "Профессор",
    "Медикал Он Груп",
    "Аетерна",
    "Мими Клиник",
    "Дентал",
    "Мир семьи",
]


def main():
    source = []
    for path in (PRIMARY, SUPPLEMENT):
        source.extend(json.loads(path.read_text(encoding="utf-8")).get("items") or [])
    by_name = {item.get("name"): item for item in source}
    items = []
    for name in SELECTED_NAMES:
        item = by_name.get(name)
        if not item or item.get("status") != "ready_for_user_approval":
            raise RuntimeError(f"selected_item_not_ready:{name}")
        item = json.loads(json.dumps(item, ensure_ascii=False))
        public_name = str((item.get("evidence", {}).get("research") or {}).get("title") or "")
        display_name = public_name if name == "stomatologicheskiy kompleks novoperedelkino" else name
        draft = item.get("draft") or {}
        if public_name and display_name and public_name != display_name:
            for key in ("subject", "text", "observation"):
                draft[key] = str(draft.get(key) or "").replace(public_name, display_name)
        item["display_name"] = display_name
        item["planned_send_date"] = "2026-08-21"
        item["approval"] = {"content_status": "pending_user_approval", "delivery_authorized": False}
        word_count = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", draft.get("text") or ""))
        if word_count > 120 or str(draft.get("text") or "").count("?") != 1:
            raise RuntimeError(f"draft_guardrail_failed:{name}")
        item["quality"]["word_count"] = word_count
        items.append(item)
    if len(items) != 20 or len({item["lead_id"] for item in items}) != 20 or len({item["recipient"].lower() for item in items}) != 20:
        raise RuntimeError("final_batch_uniqueness_failed")
    payload = {
        "schema_version": "localos_followup_batch_final_v1",
        "base_manifest_canonical_sha256": "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386",
        "batch_id": "followup-batch-01-20260820",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_send_date": "2026-08-21",
        "state": "draft_for_user_approval",
        "delivery_authorized": False,
        "queued": False,
        "sent": False,
        "ready_count": len(items),
        "items": items,
    }
    payload["review_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "ready": len(items), "review_sha256": payload["review_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
