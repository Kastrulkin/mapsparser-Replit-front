#!/usr/bin/env python3
"""Freeze exactly 20 manually reviewed group-two drafts for tomorrow."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path("/app/debug_data/localos-followup-batch-02-candidates-review-20260820.json")
OUTPUT = Path("/app/debug_data/localos-followup-batch-02-final-20260820.json")
SELECTED_NAMES = [
    "АМД Лаборатории", "Монрепо", "Микшель", "D. O. M. Beauty bar", "Dk Clinic",
    "GinkgoLab", "La Clinique", "LuA. Clinic", "Myrtille", "PF&Beauty", "Ботаника",
    "Инскин", "Ли́ца", "Медикор", "Милано", "Модифик", "Петергоф-Мед",
    "Привилегия Здоровья", "Путь к здоровью", "Сирин",
]
CLIENT_WORDING = {"Монрепо", "D. O. M. Beauty bar"}


def main():
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    by_name = {item.get("name"): item for item in payload.get("items") or []}
    items = []
    for name in SELECTED_NAMES:
        item = by_name.get(name)
        if not item or item.get("status") != "ready_for_user_approval":
            raise RuntimeError(f"selected_item_not_ready:{name}")
        item = json.loads(json.dumps(item, ensure_ascii=False))
        public_name = str((item.get("evidence", {}).get("research") or {}).get("title") or "")
        draft = item.get("draft") or {}
        if public_name and public_name != name:
            for key in ("subject", "text", "observation"):
                draft[key] = str(draft.get(key) or "").replace(public_name, name)
        if name in CLIENT_WORDING:
            for key in ("text", "problem_hypothesis"):
                draft[key] = str(draft.get(key) or "").replace("пациенту", "клиенту")
        item["display_name"] = name
        item["planned_send_date"] = "2026-08-21"
        item["approval"] = {"content_status": "pending_user_approval", "delivery_authorized": False}
        words = len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", draft.get("text") or ""))
        if words > 120 or str(draft.get("text") or "").count("?") != 1:
            raise RuntimeError(f"draft_guardrail_failed:{name}")
        item["quality"]["word_count"] = words
        items.append(item)
    if len(items) != 20 or len({x["lead_id"] for x in items}) != 20 or len({x["recipient"].lower() for x in items}) != 20:
        raise RuntimeError("final_batch_uniqueness_failed")
    final = {
        "schema_version": "localos_followup_batch_final_v1",
        "base_manifest_canonical_sha256": "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386",
        "batch_id": "followup-batch-02-20260820",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_send_date": "2026-08-21",
        "state": "draft_for_user_approval",
        "delivery_authorized": False,
        "queued": False,
        "sent": False,
        "ready_count": len(items),
        "excluded_after_manual_review": [
            {"name": "Гормедцентр", "reason": "public_title_and_contact_page_need_identity_review"},
            {"name": "Первая семейная клиника Петербурга", "reason": "recipient_domain_differs_from_current_location_site"},
            {"name": "Стоматолог Пушкин", "reason": "generic_map_identity_and_different_contact_brand_need_review"},
        ],
        "items": items,
    }
    final["review_sha256"] = hashlib.sha256(json.dumps(final, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    OUTPUT.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "ready": len(items), "review_sha256": final["review_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
