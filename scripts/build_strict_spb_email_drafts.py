#!/usr/bin/env python3
"""Render review-only email drafts from the strict SPb creator contact report."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUBJECT = "Партнёрство с локальными бизнесами через LocalOS"
MANUAL_EXCLUSIONS = {
    "(не)критично | искусство и культура",
    "ahhu. ru - дешёвые туры по россии и миру",
    "ariburo",
    "aver's garage",
    "ecoflow russia",
    "getbig.tv",
    "lapin service",
    "lr west",
    "marketplace_fashion",
    "motorsvideo",
    "san78  монтаж сантехники и отопления в спб",
    "siyanie sily | creative space",
    "skots studio",
    "the welder catherine",
    "азбука строительства",
    "алиса - live",
    "армстайл армянский танцевальный ансамбль",
    "архитектурное бюро \"тектоника\"",
    "архитектурные сезоны",
    "ваш юрист теребенин и партнёры",
    "веселое творчество",
    "живая стройка",
    "жизнь дворца ддют фрунзенского района",
    "ксения спасает жизни",
    "логистика будущего конференции",
    "майская регата",
    "мастердом russia",
    "проект альтарес | ремонт квартир и домов в москве",
    "рекламные видео объектов недвижимости",
    "росперепланировка.рф",
    "спбелт i конвейеры i комплектующие",
    "стартафф",
    "супер-кубок титанов",
    "теплые системы остекления в спб",
    "энергия холода",
}
GEOGRAPHY_EXCLUSIONS = {
    "жизнь в деревне с галиной .",
    "живём и работаем на кубани",
    "игорь гришин – наукоград королёв",
    "семь я из сибири",
}
PILOT_OBSERVATIONS = {
    "anthony show": "Увидели у вас выпуск о тренировке на открытом зале на Крестовском острове.",
    "miss.dariella": "Увидели у вас материал о месте для съёмок на Елагином острове.",
    "spb walks": "Увидели у вас материал о прогулке по Павловскому парку.",
    "аврора белышева": "Увидели у вас материал об уличном выступлении на Литейном проспекте.",
    "лиза виноградова": "Увидели у вас выпуск о заведениях в Купчино и у метро Пролетарская.",
    "оля попова": "Увидели у вас материал о жизни в Мурино.",
    "светланка блог": "Увидели у вас влог с прогулкой по Летнему саду.",
    "altana matveeva": "Увидели у вас влог о неделе в Петербурге, любимых местах и покупках.",
    "anastasia che": "Увидели у вас влог о жизни в Петербурге, доме и покупках.",
    "anya grechkina": "Увидели у вас уютный влог о буднях в Петербурге.",
}


def normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def rows_by_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {row["creator_profile_id"]: row for row in csv.DictReader(stream)}


def sent_recipients(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {normalized(row.get("recipient")) for row in csv.DictReader(stream) if row.get("recipient")}


def template_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "## Body\n\n"
    end_marker = "\n## Ограничения"
    if marker not in text or end_marker not in text:
        raise ValueError("Канонический шаблон не содержит секцию Body")
    return text.split(marker, 1)[1].split(end_marker, 1)[0].strip()


def evidence_title(summary: str) -> str:
    match = re.search(r"«(.+?)»\s+содержит", summary, flags=re.DOTALL)
    if not match:
        return ""
    title = " ".join(match.group(1).split()).rstrip(" .!?")
    return title.replace("—", "-").replace("–", "-").replace("«", "").replace("»", "")


def observation(row: dict[str, str], *, display_name: str) -> str:
    curated = PILOT_OBSERVATIONS.get(normalized(display_name))
    if curated:
        return curated
    title = evidence_title(row.get("evidence_summary") or "")
    if title and len(title) <= 100:
        return f"Увидели у вас публикацию о Петербурге: {title}."
    try:
        geographies = json.loads(row.get("content_geographies_json") or "[]")
    except json.JSONDecodeError:
        geographies = []
    specific = next(
        (
            str(item.get("name") or "").strip()
            for item in geographies
            if isinstance(item, dict)
            and str(item.get("kind") or "") != "city"
            and str(item.get("name") or "").strip()
        ),
        "",
    )
    if specific:
        return f"Увидели у вас публикацию о локации {specific}."
    return "Увидели у вас публикацию о Петербурге и городских местах."


def exclusion_reason(
    *,
    name: str,
    email: str,
    row: dict[str, str],
    seen_emails: set[str],
    already_sent: set[str],
) -> str:
    lowered_name = normalized(name)
    if not email:
        return "email_missing"
    if email in seen_emails:
        return "duplicate_email"
    if email in already_sent:
        return "already_sent"
    if str(row.get("previous_campaign_count") or "0") != "0":
        return "existing_campaign_history"
    if lowered_name in MANUAL_EXCLUSIONS:
        return "organization_or_business_project"
    if lowered_name in GEOGRAPHY_EXCLUSIONS:
        return "explicit_other_geography"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contacts", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--sent", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-preview", type=Path, required=True)
    arguments = parser.parse_args()

    report = json.loads(arguments.contacts.read_text(encoding="utf-8"))
    cohort = rows_by_id(arguments.cohort)
    already_sent = sent_recipients(arguments.sent)
    source_template = template_body(arguments.template)
    template_sha256 = hashlib.sha256(arguments.template.read_bytes()).hexdigest()
    seen_emails: set[str] = set()
    records: list[dict[str, Any]] = []

    for item in report.get("results", []):
        preferred = item.get("preferred_contact") or {}
        validation = preferred.get("validation") or {}
        if validation.get("route_type") != "email" or validation.get("reachable") is not True:
            continue
        profile_id = str(item.get("profile_id") or "")
        row = cohort.get(profile_id)
        if not row:
            continue
        email = normalized(preferred.get("value"))
        reason = exclusion_reason(
            name=str(item.get("display_name") or ""),
            email=email,
            row=row,
            seen_emails=seen_emails,
            already_sent=already_sent,
        )
        seen_emails.add(email)
        observed = observation(row, display_name=str(item.get("display_name") or ""))
        body = source_template.replace("{OBSERVATION_SENTENCE}", observed) if not reason else ""
        word_count = len(body.split())
        if not reason and word_count > 120:
            reason = "channel_limit_exceeded"
            body = ""
        records.append({
            "draft_id": hashlib.sha256(f"{profile_id}:{email}:{template_sha256}".encode()).hexdigest()[:24],
            "creator_profile_id": profile_id,
            "display_name": str(item.get("display_name") or ""),
            "email": email,
            "email_source_url": str(preferred.get("source_url") or ""),
            "email_validation": str(validation.get("status") or ""),
            "evidence_url": row.get("evidence_url") or "",
            "evidence_observed_at": row.get("evidence_observed_at") or "",
            "observation": observed,
            "subject": SUBJECT if not reason else "",
            "body": body,
            "word_count": word_count if body else 0,
            "state": "draft_needs_review" if not reason else "excluded_or_blocked",
            "exclusion_reason": reason,
            "template_id": "localos-active-authors-email-first-touch",
            "template_version": "1.0",
            "template_sha256": template_sha256,
            "quality_state": "validator_not_run_semantic_review_pending",
            "reason_codes": ["VALIDATOR_NOT_RUN", "SELF_REPORTED_SCORE"] if not reason else [],
        })

    payload = {
        "schema_version": "1.0",
        "status": "draft_needs_review_no_messages_sent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "template": {
            "id": "localos-active-authors-email-first-touch",
            "version": "1.0",
            "sha256": template_sha256,
        },
        "email_contact_count": len(records),
        "draft_count": sum(record["state"] == "draft_needs_review" for record in records),
        "excluded_count": sum(record["state"] != "draft_needs_review" for record in records),
        "messages_sent": 0,
        "records": records,
    }
    arguments.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "draft_id", "creator_profile_id", "display_name", "email", "email_source_url",
        "email_validation", "evidence_url", "evidence_observed_at", "observation",
        "subject", "body", "word_count", "state", "exclusion_reason",
        "template_id", "template_version", "template_sha256", "quality_state", "reason_codes",
    ]
    with arguments.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["reason_codes"] = ",".join(record["reason_codes"])
            writer.writerow(row)

    eligible = [record for record in records if record["state"] == "draft_needs_review"]
    excluded = [record for record in records if record["state"] != "draft_needs_review"]
    lines = [
        "# Черновики писем активным авторам Санкт-Петербурга",
        "",
        f"- Email-контактов после дедупликации и проверки: {len(records)}",
        f"- Черновиков: {len(eligible)}",
        f"- Исключено или заблокировано: {len(excluded)}",
        "- Статус: `draft / needs_review`",
        "- Сообщений отправлено: 0",
        "",
        "## Первые 10 черновиков для ручной проверки",
        "",
    ]
    for index, record in enumerate(eligible[:10], start=1):
        lines.extend([
            f"### {index}. {record['display_name']}",
            "",
            f"Email: `{record['email']}`",
            "",
            f"Источник: {record['evidence_url']}",
            "",
            f"Тема: {record['subject']}",
            "",
            record["body"],
            "",
        ])
    lines.extend([
        "## Исключения",
        "",
    ])
    for record in excluded:
        lines.append(f"- {record['display_name']} (`{record['email']}`): `{record['exclusion_reason']}`")
    lines.extend([
        "",
        "## Ограничения",
        "",
        "- Email проверены только синтаксически, без SMTP-пробы.",
        "- Источник подтверждает публикацию о Петербурге, но не место жительства и не географию аудитории.",
        "- Перед пакетом больше 10 писем требуется независимая проверка разнообразной выборки и явное утверждение конкретной волны.",
        "- Ничего не импортировано в очередь и не отправлено.",
    ])
    arguments.output_preview.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({key: value for key, value in payload.items() if key != "records"}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
