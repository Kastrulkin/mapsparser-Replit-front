#!/usr/bin/env python3
"""Fully audit the large candidate reserve for the 70-lead third batch."""

import json
from pathlib import Path

import prepare_localos_followup_batch_01_20260820


SOURCE = Path("/app/debug_data/localos-followup-batch-03-sql-eligible-20260820.json")
EXCLUDED_NAMES = {
    "HairFcker", "Diadema", "Ремеди", "Отражение", "Эсма", "People's Choice", "Персона Lab",
    "Laser Love", "Лица", "Жидкова", "EMC", "Народная", "Кубик", "Mdl Clinic", "Lilalic",
    "Etalon", "Epilium Clinic", "Генселф", "Moon Clinic", "ForMe", "Смайл Бутик Клиник",
    "Дом Антивозрастной Медицины",
}


source = json.loads(SOURCE.read_text(encoding="utf-8"))
prepare_localos_followup_batch_01_20260820.FIRST_TOUCH_IDS = [
    item["first_touch_id"] for item in source.get("items") or [] if item.get("name") not in EXCLUDED_NAMES
]
prepare_localos_followup_batch_01_20260820.OUTPUT_PATH = Path(
    "/app/debug_data/localos-followup-batch-03-candidates-review-20260820.json"
)


if __name__ == "__main__":
    prepare_localos_followup_batch_01_20260820.main()
