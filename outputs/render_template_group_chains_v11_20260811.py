"""Render the current 50-chain LocalOS review artifact as readable Markdown."""

from __future__ import annotations

import json
from pathlib import Path


SOURCE = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Obsidian/Obsidian Vault/outputs/"
    "localos-template-review-v12-20260811.json"
)
OUTPUT = Path(
    "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Obsidian/Obsidian Vault/outputs/"
    "localos-template-chains-v12-20260811.md"
)


payload = json.loads(SOURCE.read_text(encoding="utf-8"))
results = sorted(payload["results"], key=lambda item: str(item.get("name") or "").lower())


def touch_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "касание"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "касания"
    return "касаний"


touch_count = sum(len(item.get("touches") or []) for item in results)
passed_count = sum(
    bool((touch.get("quality_gate") or {}).get("passed"))
    for item in results
    for touch in item.get("touches") or []
)

lines = [
    "# Цепочки LocalOS: слабые карточки на Яндекс Картах",
    "",
    f"- Цепочек: {len(results)}",
    f"- Касаний: {touch_count}",
    f"- Прошли проверку: {passed_count}/{touch_count}",
    "- Состояние: черновики",
    "- Одобрено / в очереди / отправлено: 0 / 0 / 0",
    f"- Версия шаблонов: {payload.get('template_library_version')}",
    f"- Контрольная сумма: `{payload.get('canonical_sha256')}`",
    "",
    "## Содержание",
    "",
]
for index, item in enumerate(results, start=1):
    item_touch_count = len(item.get("touches") or [])
    lines.append(f"{index}. {item['name']} - {item_touch_count} {touch_word(item_touch_count)}")

for index, item in enumerate(results, start=1):
    lines.extend(
        [
            "",
            f"## {index}. {item['name']}",
            "",
            f"- Lead ID: `{item.get('lead_id')}`",
            f"- Workstream ID: `{item.get('workstream_id')}`",
            f"- Состояние цепочки: {item.get('classification')}",
            f"- Каналы: {' -> '.join(item.get('channels') or [])}",
            "",
        ]
    )
    for touch_index, touch in enumerate(item.get("touches") or [], start=1):
        gate = touch.get("quality_gate") or {}
        selection = touch.get("template_selection") or {}
        template_key = (
            touch.get("outreach_template_key")
            or touch.get("template_key")
            or selection.get("key")
            or "individual"
        )
        reason_codes = gate.get("reason_codes") or []
        lines.extend(
            [
                f"### Касание {touch_index} - {touch.get('channel')}",
                "",
                f"- Шаблон: `{template_key}`",
                f"- Проверка: {'PASS' if gate.get('passed') else 'REVISE'} ({gate.get('total_score', 0)}/18)",
                f"- Причины: {', '.join(reason_codes) if reason_codes else 'нет'}",
            ]
        )
        if touch.get("subject"):
            lines.append(f"- Тема: {touch['subject']}")
        if touch.get("source_url"):
            lines.append(f"- Источник: {touch['source_url']}")
        lines.extend(["", touch.get("text") or "", ""])

OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "output": str(OUTPUT),
            "chains": len(results),
            "touches": touch_count,
            "passed": passed_count,
        },
        ensure_ascii=False,
    )
)
