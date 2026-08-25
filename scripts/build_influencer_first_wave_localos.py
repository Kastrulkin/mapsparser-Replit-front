#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "influencer-first-wave-localos-20260824"
GENERATED_AT = "2026-08-24T18:15:00+03:00"


LEADS = [
    {
        "lead_id": "creator-mallu",
        "segment": "Riderra",
        "score": 82,
        "name": "Mallu - Mariann Treimann-Legrant",
        "profile": "https://www.instagram.com/mallukaz",
        "contact_channel": "email",
        "contact": "marianntreimann@gmail.com",
        "contact_source": "https://www.modash.io/find-influencers/estonia/tallinn",
        "contact_confidence": "medium",
        "email_status": "risky",
        "observation": "A public Tallinn creator directory associates Mallu with Tallinn lifestyle content and a public email.",
        "problem_hypothesis": "Inference: the creator may consider relevant offers from local travel and service businesses.",
        "relevance": "LocalOS can bring a specific local-business brief after the creator confirms formats and terms.",
        "body": "Hello Mariann,\n\nWe at LocalOS help local businesses find relevant creators for partnerships. We noticed your Tallinn-focused lifestyle content. We are mapping current creator terms so we only bring suitable briefs.\n\nCould you share your formats, current rates, audience geography, recent sponsored reach, and preferred contact?\n\nIf a business matches, we will return with a specific brief; timing, disclosure, and usage rights will be agreed separately.",
        "cta": "Could you share your formats, current rates, audience geography, recent sponsored reach, and preferred contact?",
        "verdict": "revise",
        "quality_score": 14,
        "reason_codes": ["SOURCE_MISSING"],
        "risks": ["The directory contact must be reconfirmed before any proposal.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-helge-kalde",
        "segment": "Riderra",
        "score": 86,
        "name": "Helge Kalde",
        "profile": "https://www.instagram.com/helgekalde",
        "contact_channel": "email",
        "contact": "helge.kalde1@gmail.com",
        "contact_source": "https://collabstr.com/helgekalde",
        "contact_confidence": "medium",
        "email_status": "risky",
        "observation": "A current public creator marketplace presents Helge as a Tallinn creator offering influencer and UGC formats and invites brand partnerships.",
        "problem_hypothesis": "Inference: the creator may consider local travel, beauty, fashion, or lifestyle briefs.",
        "relevance": "LocalOS can match confirmed formats with suitable local businesses without promising a placement in advance.",
        "body": "Hello Helge,\n\nWe at LocalOS help local businesses find relevant creators for partnerships. We noticed that you offer both influencer placements and UGC formats from Tallinn. We are mapping current creator terms so we only bring suitable briefs.\n\nCould you share your current packages, rates, audience geography, recent sponsored reach, and preferred contact?\n\nIf a business matches, we will return with a specific brief; timing, disclosure, and usage rights will be agreed separately.",
        "cta": "Could you share your current packages, rates, audience geography, recent sponsored reach, and preferred contact?",
        "verdict": "revise",
        "quality_score": 14,
        "reason_codes": ["SOURCE_MISSING"],
        "risks": ["The email is cross-source and must be confirmed as the preferred partnership route.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-estonijana",
        "segment": "Riderra",
        "score": 74,
        "name": "EstoniJana",
        "profile": "https://t.me/janakristinaestonia",
        "contact_channel": "email",
        "contact": "yanaiter58@gmail.com",
        "contact_source": "https://t.me/janakristinaestonia",
        "contact_confidence": "low",
        "email_status": "risky",
        "observation": "The public channel describes a family video blog from Tallinn about local events, travel, museums, fairs, and everyday life.",
        "problem_hypothesis": "Гипотеза: автор может рассматривать небольшие локальные предложения для семейной аудитории Таллинна.",
        "relevance": "LocalOS сначала собирает условия, а затем возвращается только с конкретным подходящим брифом.",
        "body": "Здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящих авторов для сотрудничества. Обратили внимание на EstoniJana: семейный канал из Таллинна рассказывает о поездках, событиях и городской жизни.\n\nПодскажите, пожалуйста, ваши актуальные форматы, цены, географию аудитории, охваты рекламных размещений и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, ваши актуальные форматы, цены, географию аудитории, охваты рекламных размещений и удобный контакт.",
        "verdict": "revise",
        "quality_score": 13,
        "reason_codes": ["SOURCE_MISSING"],
        "risks": ["The email was found cross-platform and must be confirmed before use.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-mamy-piter",
        "segment": "Весёлая расчёска",
        "score": 94,
        "name": "Мамы и дети - Санкт-Петербург",
        "profile": "https://t.me/mamy_piter",
        "contact_channel": "telegram",
        "contact": "https://t.me/mama_city_admin",
        "contact_source": "https://t.me/mamy_piter",
        "contact_confidence": "high",
        "email_status": "not_applicable",
        "observation": "Публичное описание подтверждает петербургскую аудиторию родителей и прямо называет контакт для рекламы.",
        "problem_hypothesis": "Гипотеза: площадке могут подойти предложения детских и семейных локальных бизнесов.",
        "relevance": "LocalOS может подбирать предложения по аудитории и бюджету после получения актуальных условий канала.",
        "body": "Здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящие площадки для сотрудничества. Обратили внимание на канал Мамы и дети: он работает с петербургской аудиторией родителей и публикует идеи для семей.\n\nПодскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["Content approval is still required before delivery.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-gokids-peterburg",
        "segment": "Весёлая расчёска",
        "score": 96,
        "name": "Куда пойти в Питере с детьми",
        "profile": "https://t.me/gokidspeterburg",
        "contact_channel": "telegram",
        "contact": "https://t.me/alex_admin_tg",
        "contact_source": "https://t.me/gokidspeterburg",
        "contact_confidence": "high",
        "email_status": "not_applicable",
        "observation": "Публичное описание называет канал полезной афишей Петербурга для родителей и указывает отдельный контакт для сотрудничества.",
        "problem_hypothesis": "Гипотеза: площадке подойдут предложения семейных мест и услуг с понятной географией.",
        "relevance": "LocalOS может приносить конкретные локальные брифы после фиксации форматов и коммерческих условий.",
        "body": "Здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящие площадки для сотрудничества. Обратили внимание на Куда пойти в Питере с детьми: канал собирает события, места и полезные идеи для родителей Петербурга.\n\nПодскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["Content approval is still required before delivery.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-afisha-spb-mami",
        "segment": "Весёлая расчёска",
        "score": 92,
        "name": "Мамы Санкт-Петербург - Афиша",
        "profile": "https://t.me/afishaspbmami",
        "contact_channel": "telegram",
        "contact": "https://t.me/afishaspbmamibot",
        "contact_source": "https://t.me/afishaspbmami",
        "contact_confidence": "high",
        "email_status": "not_applicable",
        "observation": "Публичное описание позиционирует канал как афишу детских мероприятий Петербурга и указывает контакт для сотрудничества.",
        "problem_hypothesis": "Гипотеза: площадке могут подойти локальные семейные услуги и тематические подборки.",
        "relevance": "LocalOS может сопоставлять аудиторию площадки с конкретными бизнесами и возвращаться с готовым брифом.",
        "body": "Здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящие площадки для сотрудничества. Обратили внимание на Мамы Санкт-Петербург - Афиша: канал собирает детские события и места для родителей Петербурга.\n\nПодскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных размещений и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["Content approval is still required before delivery.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-beautyholic",
        "segment": "Органика",
        "score": 96,
        "name": "BEAUTYHOLIC - Варвара",
        "profile": "https://t.me/your_skin_care",
        "contact_channel": "telegram",
        "contact": "https://t.me/vareshka_84",
        "contact_source": "https://t.me/your_skin_care",
        "contact_confidence": "high",
        "email_status": "not_applicable",
        "observation": "Публичное описание подтверждает петербургский beauty-блог и прямо указывает администратора.",
        "problem_hypothesis": "Гипотеза: автору могут подойти локальные beauty, wellness и lifestyle-проекты.",
        "relevance": "LocalOS может предложить конкретный бизнес после получения форматов, цен и аудитории.",
        "body": "Здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящих авторов для сотрудничества. Обратили внимание на BEAUTYHOLIC: петербургский канал пишет об уходе, моде, спорте и beauty-находках.\n\nПодскажите, пожалуйста, ваши актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; процедуру, сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, ваши актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["Content approval is still required before delivery.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-katerina-davydova",
        "segment": "Органика",
        "score": 96,
        "name": "Катерина Давыдова",
        "profile": "https://t.me/kdvmua",
        "contact_channel": "email",
        "contact": "kdvmua@gmail.com",
        "contact_source": "https://t.me/kdvmua",
        "contact_confidence": "high",
        "email_status": "verified",
        "observation": "Публичное описание называет Катерину петербургским бьюти-блогером и визажистом и прямо указывает email для рекламы.",
        "problem_hypothesis": "Гипотеза: автору могут подойти локальные beauty-проекты с понятной услугой и измерением результата.",
        "relevance": "LocalOS может вернуться с конкретным брифом после фиксации актуальных условий автора.",
        "body": "Катерина, здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящих авторов для сотрудничества. Обратили внимание на ваш петербургский контент об уходе и beauty-практиках.\n\nПодскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; услугу, сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["Content approval is still required before delivery.", "No external message has been sent."],
    },
    {
        "lead_id": "creator-kremom-po-litsu",
        "segment": "Органика",
        "score": 94,
        "name": "Кремом по лицу - Валерия Скрябина",
        "profile": "https://t.me/kremom_po_litsu",
        "contact_channel": "telegram",
        "contact": "https://t.me/Eklllerchik",
        "contact_source": "https://t.me/kremom_po_litsu",
        "contact_confidence": "high",
        "email_status": "not_applicable",
        "observation": "Публичный профиль связывает Валерию Скрябину с петербургским beauty-каналом и указывает Telegram-контакт для записи.",
        "problem_hypothesis": "Гипотеза: автору могут подойти локальные beauty и wellness-проекты с аккуратным согласованием утверждений.",
        "relevance": "LocalOS может подобрать конкретный проект после получения коммерческих условий и допустимых форматов.",
        "body": "Валерия, здравствуйте!\n\nМы в LocalOS помогаем локальным бизнесам находить подходящих авторов для сотрудничества. Обратили внимание на Кремом по лицу и ваш экспертный контент об уходе.\n\nПодскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.\n\nЕсли найдём подходящий бизнес, вернёмся с конкретным брифом; услугу, сроки, маркировку и права на материал согласуем отдельно.",
        "cta": "Подскажите, пожалуйста, актуальные форматы, цены, географию аудитории, охваты последних рекламных интеграций и удобный контакт.",
        "verdict": "approve",
        "quality_score": 17,
        "reason_codes": [],
        "risks": ["The public contact also handles appointments; confirm that partnership requests are accepted there.", "No external message has been sent."],
    },
]


def record(lead: dict) -> dict:
    evidence_id = f"evidence-{lead['lead_id']}"
    personalization_id = f"personalization-{lead['lead_id']}"
    criteria = [
        {"name": "source_validity", "score": 2, "note": "Original public profile or current public professional source."},
        {"name": "observation_accuracy", "score": 2, "note": "Observation stays within the source."},
        {"name": "freshness_and_why_now", "score": 1, "note": "Current terms still need confirmation."},
        {"name": "bridge_from_signal_to_offer", "score": 2, "note": "The message explains the LocalOS matchmaking role."},
        {"name": "recipient_specificity", "score": 2, "note": "The profile theme changes the outreach reason."},
        {"name": "proof_integrity", "score": 2, "note": "No performance promise is made."},
        {"name": "natural_channel_fit", "score": 2, "note": "Short first touch."},
        {"name": "single_cta_and_length", "score": 2, "note": "One request for current terms."},
        {"name": "state_and_suppression_safety", "score": 2, "note": "Draft only; no delivery state."},
    ]
    if lead["quality_score"] < 15:
        criteria[0] = {"name": "source_validity", "score": 1, "note": "Contact route needs confirmation."}
        criteria[6] = {"name": "natural_channel_fit", "score": 1, "note": "Channel route is cross-source or manual."}
        criteria[8] = {"name": "state_and_suppression_safety", "score": 1, "note": "Keep outside delivery until contact is confirmed."}
    return {
        "schema_version": "1.0",
        "lead_id": lead["lead_id"],
        "motion": "creator_network_intake",
        "identity": {
            "company_name": lead["name"],
            "contact_name": lead["name"],
            "contact_role": "автор или представитель площадки",
            "public_urls": [lead["profile"]],
        },
        "contacts": [{
            "channel": lead["contact_channel"],
            "value": lead["contact"],
            "source_url": lead["contact_source"],
            "observed_at": GENERATED_AT,
            "confidence": lead["contact_confidence"],
            "email_status": lead["email_status"],
        }],
        "qualification": {"segment": lead["segment"], "icp_score": lead["score"], "disqualifiers": []},
        "evidence": [{
            "evidence_id": evidence_id,
            "kind": "social_activity",
            "observation": lead["observation"],
            "source_url": lead["profile"],
            "source_type": "public_professional_profile",
            "source_date": None,
            "researched_at": GENERATED_AT,
            "confidence": "high" if lead["contact_confidence"] == "high" else "medium",
            "usable_for_outreach": True,
        }],
        "personalization_candidates": [{
            "personalization_id": personalization_id,
            "observation": lead["observation"],
            "evidence_ids": [evidence_id],
            "problem_hypothesis": lead["problem_hypothesis"],
            "relevance_to_offer": lead["relevance"],
            "personalized_opener": lead["body"].split("\n\n")[1],
            "confidence": "high" if lead["contact_confidence"] == "high" else "medium",
            "usable": True,
            "removal_test_passed": True,
        }],
        "selected_personalization_id": personalization_id,
        "touches": [{
            "touch_no": 1,
            "channel": lead["contact_channel"],
            "angle": "сбор актуальных условий для сети локальных бизнесов",
            "body": lead["body"],
            "cta": lead["cta"],
            "evidence_ids": [evidence_id],
        }],
        "quality_gate": {
            "score": lead["quality_score"],
            "verdict": lead["verdict"],
            "reason_codes": lead["reason_codes"],
            "criteria": criteria,
        },
        "approval": {"status": "needs_review", "approved_by": None, "approved_at": None},
        "campaign": {"status": "research_only", "sender": "LocalOS", "external_send_performed": False},
        "outcome": {"reply_status": "none", "unsubscribe": False, "suppressed": False},
        "risks": lead["risks"],
        "generated_at": GENERATED_AT,
    }


def render_index(records: list[dict]) -> str:
    lines = [
        "# Первая волна инфлюенсеров от имени LocalOS",
        "",
        "Статус: только черновики. Внешние сообщения не отправлялись.",
        "",
        "Цель первого контакта: получить форматы, цены, географию аудитории, свежие охваты и удобный канал связи. Конкретный бизнес предлагается только после сопоставления условий.",
        "",
    ]
    for segment in ("Riderra", "Весёлая расчёска", "Органика"):
        lines.extend([f"## {segment}", ""])
        for item in [entry for entry in records if entry["qualification"]["segment"] == segment]:
            touch = item["touches"][0]
            lines.extend([
                f"### {item['identity']['contact_name']}",
                "",
                f"- Канал: `{touch['channel']}`",
                f"- Контакт: `{item['contacts'][0]['value']}`",
                f"- Quality: `{item['quality_gate']['verdict']}` ({item['quality_gate']['score']}/18)",
                f"- Источник: {item['evidence'][0]['source_url']}",
                "",
                touch["body"],
                "",
            ])
    lines.extend(["Внешняя отправка: **не выполнялась**.", ""])
    return "\n".join(lines)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = [record(lead) for lead in LEADS]
    for item in records:
        path = OUTPUT_DIR / f"{item['lead_id']}.json"
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "first-wave.json").write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "README.md").write_text(render_index(records), encoding="utf-8")
    print(json.dumps({"records": len(records), "output_dir": str(OUTPUT_DIR)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
