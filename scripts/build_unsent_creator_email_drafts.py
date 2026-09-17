#!/usr/bin/env python3
"""Build review-only first-touch email drafts for the original unsent cohort."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SUBJECT = "Партнёрство с локальными бизнесами через LocalOS"
SUBJECT_EN = "Collaboration with local businesses via LocalOS"
CTA = "Вам интересен такой формат?"
CTA_EN = "Would this format be of interest to you?"
TEMPLATE_ID = "localos-active-authors-email-first-touch"
TEMPLATE_VERSION = "1.0"

OBSERVATIONS = {
    "EstoniJana": "Увидели, что в семейном видеоблоге вы рассказываете о путешествиях и событиях в Таллинне.",
    "Helge Kalde": "Увидели ваш блог из Таллинна о путешествиях и beauty-тематике.",
    "Jay Influencer - The Luxury Travel Consultant": "Увидели у вас подборку люксовых отелей Санкт-Петербурга.",
    "JUST TANYA / ДЖАСТ ТАНЯ": "Увидели у вас разбор посещения салона красоты в Петербурге.",
    "KATYA travel (KATRIN travel)": "Увидели у вас обзор гостиницы Октябрьская в центре Санкт-Петербурга.",
    "Mallu — Mariann Treimann-Legrant": "Увидели ваш блог из Таллинна с преимущественно женской аудиторией.",
    "Maria Sklezneva": "Увидели у вас видео о поездке в Петербург с ребёнком.",
    "Masha Family Days": "Увидели у вас семейный выпуск о любимых местах и кафе Петербурга.",
    "Must Anna": "Увидели у вас выпуск об отеле, бассейне и любимых местах Петербурга.",
    "Travelholic TV": "Увидели у вас пешеходную экскурсию по Санкт-Петербургу.",
    "АННУШКА САНКТ-ПЕТЕРБУРГ-ВЛОГИ. Здоровье. Дети.": "Увидели у вас городской влог о торговом центре Атмосфера в Санкт-Петербурге.",
    "Валери лайт": "Увидели у вас обзор спа для волос, головы и тела в Петербурге.",
    "Глеб Бауэр": "Увидели у вас обзор тайского массажа в Петербурге.",
    "Давай Двинем!": "Увидели у вас необычный маршрут по Петербургу.",
    "Катерина Давыдова": "Увидели ваш петербургский канал о beauty-тематике.",
    "Любава и Алёша Фитнес - Cемья": "Увидели у вас семейный выпуск о Петергофе и ресторанах Петербурга.",
    "Путешествия Вместе с Нами": "Увидели у вас городской маршрут по достопримечательностям Краснодара.",
    "Путешествия многодетной семьи": "Увидели у вас семейный выпуск об Острове фортов в Кронштадте.",
    "путешествия с aзартом | AZART travels": "Увидели у вас выпуск об Удельном рынке в Петербурге.",
    "Путешествуй со смыслом": "Увидели у вас большой гид для первой поездки в Петербург.",
    "СемейныеПутешествия": "Увидели у вас семейный влог о летней прогулке по Санкт-Петербургу.",
    "Стихи по - чёрному": "Увидели у вас стихотворный фотообзор достопримечательностей Санкт-Петербурга.",
    "Честные распаковки 🛒": "Увидели у вас выпуск о поездке в Санкт-Петербург с отелем, экскурсиями и парком аттракционов.",
}

OBSERVATIONS_EN = {
    "Helge Kalde": "We saw that your Tallinn-based content focuses on travel, beauty and lifestyle.",
    "Jay Influencer - The Luxury Travel Consultant": "We came across your guide to luxury hotels in St Petersburg.",
    "Mallu — Mariann Treimann-Legrant": "We found your Estonian lifestyle and family content.",
    "Travelholic TV": "We came across your walking tour of St Petersburg.",
}

EXCLUSIONS = {
    "Baby Jungle": "business_not_personal_author",
    "Магазин Geek Trip": "retail_business_not_author",
    "«Северный человек» Санкт-Петербург": "organization_not_personal_author",
    "Хоккей в Санкт-Петербурге!": "sports_media_or_organization",
}

QUALITY = [
    {"name": "source_validity", "score": 2, "note": "Public source and public email source are recorded."},
    {"name": "observation_accuracy", "score": 2, "note": "The opener is a restrained paraphrase of the cited evidence."},
    {"name": "freshness", "score": 1, "note": "No claim that the cited publication is recent."},
    {"name": "offer_bridge", "score": 2, "note": "Local content directly supports asking about local offers."},
    {"name": "specificity", "score": 1, "note": "One public content item personalizes a cross-client first touch."},
    {"name": "proof_integrity", "score": 2, "note": "No result or free-service guarantee is promised."},
    {"name": "channel_fit", "score": 1, "note": "Plain-text first-touch email under the channel limit."},
    {"name": "cta_and_length", "score": 2, "note": "One reply request and fewer than 120 words."},
    {"name": "state_safety", "score": 1, "note": "No prior send was found, but final pre-send suppression check remains required."},
]


def template_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    body = text.split("## Body\n\n", 1)[1]
    for marker in ("\n## Ограничения", "\n## Constraints"):
        if marker in body:
            body = body.split(marker, 1)[0]
            break
    return body.strip()


def record_for_validation(item: dict[str, Any], draft: dict[str, Any], generated_at: str) -> dict[str, Any]:
    profile_id = item["creator_profile_id"]
    evidence_id = f"publication:{profile_id}"
    personalization_id = f"opener:{profile_id}"
    email_source = item.get("email_source_url") or item["evidence_url"]
    observation = draft["observation"]
    return {
        "schema_version": "1.0",
        "lead_id": profile_id,
        "motion": "local_creator_partnership",
        "identity": {
            "company_name": item["display_name"],
            "contact_name": item["display_name"],
            "contact_role": "active_creator",
            "public_urls": [email_source, item["evidence_url"]],
        },
        "contacts": [{
            "channel": "email",
            "value": item["email"],
            "source_url": email_source,
            "observed_at": generated_at,
            "confidence": "medium",
            "email_status": "risky",
        }],
        "qualification": {"segment": "active local content author", "icp_score": 70, "disqualifiers": []},
        "evidence": [{
            "evidence_id": evidence_id,
            "kind": "public_creator_post",
            "observation": observation,
            "source_url": item["evidence_url"],
            "source_type": "public_profile",
            "researched_at": generated_at,
            "confidence": "medium",
            "usable_for_outreach": True,
        }],
        "personalization_candidates": [{
            "personalization_id": personalization_id,
            "evidence_ids": [evidence_id],
            "observation": observation,
            "problem_hypothesis": "The author may be open to relevant offers from local businesses.",
            "relevance_to_offer": "The reply establishes city, district, and preferred publishing platform.",
            "personalized_opener": observation,
            "confidence": "medium",
            "usable": True,
            "removal_test_passed": True,
        }],
        "selected_personalization_id": personalization_id,
        "touches": [{
            "touch_no": 1,
            "channel": "email",
            "subject": draft["subject"],
            "body": draft["body"],
            "cta": draft["cta"],
            "angle": "cross-client performance barter introduction",
            "evidence_ids": [evidence_id],
        }],
        "quality_gate": {
            "verdict": "revise",
            "score": sum(item["score"] for item in QUALITY),
            "criteria": QUALITY,
            "review_type": "generator_self_check_only",
        },
        "approval": {"status": "needs_review"},
        "campaign": {"status": "draft", "touch_no": 1},
        "outcome": {"reply_status": "none", "unsubscribe": False, "suppressed": False},
        "risks": ["email_syntax_only", "city_and_district_not_confirmed", "batch_sample_not_approved"],
        "generated_at": generated_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--template-en", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-preview", type=Path, required=True)
    parser.add_argument("--records-dir", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    generated_at = source["generated_at"]
    template = template_body(args.template)
    template_en = template_body(args.template_en)
    template_hash = hashlib.sha256(args.template.read_bytes()).hexdigest()
    template_en_hash = hashlib.sha256(args.template_en.read_bytes()).hexdigest()
    seen_emails: set[str] = set()
    drafts: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []

    for item in source["records"]:
        name = item["display_name"]
        email = str(item["email"]).strip().lower()
        reason = EXCLUSIONS.get(name, "")
        if not reason and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            reason = "invalid_email_shape"
        if not reason and email in seen_emails:
            reason = "duplicate_email"
        seen_emails.add(email)
        if reason:
            excluded.append({"creator_profile_id": item["creator_profile_id"], "display_name": name, "email": email, "reason": reason})
            continue
        if name not in OBSERVATIONS:
            excluded.append({"creator_profile_id": item["creator_profile_id"], "display_name": name, "email": email, "reason": "manual_observation_missing"})
            continue
        language = "en" if name in OBSERVATIONS_EN else "ru"
        observation = OBSERVATIONS_EN.get(name, OBSERVATIONS[name])
        selected_template = template_en if language == "en" else template
        selected_hash = template_en_hash if language == "en" else template_hash
        subject = SUBJECT_EN if language == "en" else SUBJECT
        cta = CTA_EN if language == "en" else CTA
        template_id = f"{TEMPLATE_ID}-en" if language == "en" else TEMPLATE_ID
        body = selected_template.replace("{OBSERVATION_SENTENCE}", observation)
        drafts.append({
            "draft_id": hashlib.sha256(f"{item['creator_profile_id']}:{email}:{selected_hash}".encode()).hexdigest()[:24],
            "creator_profile_id": item["creator_profile_id"],
            "display_name": name,
            "email": email,
            "email_source_url": item.get("email_source_url") or item["evidence_url"],
            "email_validation": "syntax_valid_only",
            "language": language,
            "primary_city": item.get("primary_city"),
            "evidence_url": item["evidence_url"],
            "evidence_summary": item["evidence_summary"],
            "observation": observation,
            "subject": subject,
            "body": body,
            "cta": cta,
            "word_count": len(re.findall(r"\b[\w-]+\b", body)),
            "state": "draft_needs_review",
            "template_id": template_id,
            "template_version": TEMPLATE_VERSION,
            "template_sha256": selected_hash,
            "reason_codes": ["BATCH_SAMPLE_NOT_APPROVED", "SELF_REPORTED_SCORE"],
        })

    payload = {
        "schema_version": "1.0",
        "status": "draft_needs_review_no_messages_sent",
        "generated_at": generated_at,
        "source_profile_count": len(source["records"]),
        "draft_count": len(drafts),
        "excluded_count": len(excluded),
        "messages_sent": 0,
        "templates": [
            {"id": TEMPLATE_ID, "version": TEMPLATE_VERSION, "sha256": template_hash, "language": "ru"},
            {"id": f"{TEMPLATE_ID}-en", "version": TEMPLATE_VERSION, "sha256": template_en_hash, "language": "en"},
        ],
        "records": drafts,
        "excluded": excluded,
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = list(drafts[0].keys())
    with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for draft in drafts:
            row = dict(draft)
            row["reason_codes"] = ",".join(draft["reason_codes"])
            writer.writerow(row)

    args.records_dir.mkdir(parents=True, exist_ok=True)
    for old in args.records_dir.glob("*.json"):
        old.unlink()
    eligible_items = (item for item in source["records"] if item["display_name"] in OBSERVATIONS)
    for index, (draft, item) in enumerate(zip(drafts, eligible_items), start=1):
        validation = record_for_validation(item, draft, generated_at)
        (args.records_dir / f"{index:03d}-{draft['creator_profile_id']}.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    lines = [
        "# Черновики писем авторам с ранее неиспользованными email",
        "",
        f"- Исходная группа: {len(source['records'])}",
        f"- Подготовлено писем: {len(drafts)}",
        f"- Исключено после ручной квалификации: {len(excluded)}",
        "- Статус: `draft / needs_review`",
        "- Отправлено: 0",
        "- Подпись: `LocalOS / Александр`",
        "",
    ]
    for index, draft in enumerate(drafts, start=1):
        lines.extend([
            f"## {index}. {draft['display_name']}",
            "",
            f"- Email: `{draft['email']}`",
            f"- Язык: `{draft['language']}`",
            f"- Источник контакта: {draft['email_source_url']}",
            f"- Доказательство: {draft['evidence_url']}",
            f"- Риск: email проверен синтаксически; город и район требуют подтверждения.",
            "",
            f"Тема: {draft['subject']}",
            "",
            draft["body"],
            "",
        ])
    lines.extend(["## Исключены", ""])
    for item in excluded:
        lines.append(f"- {item['display_name']} (`{item['email']}`): `{item['reason']}`")
    lines.extend([
        "",
        "## Состояние пакета",
        "",
        "Черновики не импортированы, не поставлены в очередь и не отправлены. Перед массовой отправкой нужна независимая проверка разнообразной выборки минимум из 10 писем и отдельное утверждение этой волны.",
    ])
    args.output_preview.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"source": len(source["records"]), "drafts": len(drafts), "excluded": len(excluded), "sent": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
