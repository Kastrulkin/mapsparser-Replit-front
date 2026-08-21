import hashlib
import json
from datetime import datetime, timezone

from services.outreach_human_language import review_human_language


SOURCE = "/app/debug_data/localos-template-review-v5-20260811.json"
OUTPUT = "/app/debug_data/localos-template-antislop-review-v1-20260811"


payload_source = json.load(open(SOURCE, encoding="utf-8"))
leads = [
    item
    for item in payload_source["results"]
    if item["classification"] == "content_ready"
]
results = []
for lead in leads:
    touches = []
    for touch in lead["touches"]:
        base = review_human_language(touch["text"], require_signal_flow=False)
        strict = review_human_language(touch["text"], require_signal_flow=True)
        touches.append(
            {
                "sequence_index": touch["sequence_index"],
                "channel": touch["channel"],
                "template_key": touch.get("template_key"),
                "base_pass": base["passed"],
                "strict_pass": strict["passed"],
                "reason_codes": strict["reason_codes"],
            }
        )
    results.append(
        {
            "name": lead["name"],
            "lead_id": lead["lead_id"],
            "verdict": "pass" if all(touch["strict_pass"] for touch in touches) else "revise",
            "touches": touches,
        }
    )

payload = {
    "schema_version": "localos_template_antislop_review_v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source_sha256": payload_source["canonical_sha256"],
    "chains_reviewed": len(results),
    "touches_reviewed": sum(len(item["touches"]) for item in results),
    "pass_count": sum(item["verdict"] == "pass" for item in results),
    "revise_count": sum(item["verdict"] == "revise" for item in results),
    "database_mutations": 0,
    "queued": 0,
    "sent": 0,
    "results": results,
}
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
payload["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
with open(OUTPUT + ".json", "w", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
    stream.write("\n")

lines = [
    "# Антинейрослоп-проверка готовых цепочек",
    "",
    f"- Проверено цепочек: {payload['chains_reviewed']}",
    f"- Проверено касаний: {payload['touches_reviewed']}",
    f"- PASS: {payload['pass_count']}",
    f"- REVISE: {payload['revise_count']}",
    "- Изменений БД / очередей / отправок: 0 / 0 / 0",
    "",
]
for verdict in ("pass", "revise"):
    lines.extend((f"## {verdict.upper()}", ""))
    for item in results:
        if item["verdict"] != verdict:
            continue
        reasons = sorted(
            {
                code
                for touch in item["touches"]
                for code in touch["reason_codes"]
            }
        )
        suffix = f" - {', '.join(reasons)}" if reasons else ""
        lines.append(f"- {item['name']}{suffix}")
    lines.append("")
with open(OUTPUT + ".md", "w", encoding="utf-8") as stream:
    stream.write("\n".join(lines))

print(
    json.dumps(
        {
            key: payload[key]
            for key in (
                "chains_reviewed",
                "touches_reviewed",
                "pass_count",
                "revise_count",
                "database_mutations",
                "queued",
                "sent",
                "canonical_sha256",
            )
        },
        ensure_ascii=False,
    )
)
