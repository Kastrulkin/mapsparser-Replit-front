#!/usr/bin/env python3
"""Build four sourced SPb influencer shortlists and review-only first-touch drafts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INPUT = Path("outputs/influencer-spb-1000-base-20260823.json")
OUTPUT_JSON = Path("outputs/influencer-spb-client-shortlists-20260823.json")
OUTPUT_CSV = Path("outputs/influencer-spb-client-shortlists-20260823.csv")
LIMIT = 40

DISQUALIFIERS = (
    "политик", "криминал", "происшеств", "ставки", "казино", "букмекер",
    "18+", "даркнет", "оружие", "военн",
)

SEGMENTS: dict[str, dict[str, Any]] = {
    "organika": {
        "title": "Органика",
        "business": "салон «Органика» на проспекте Испытателей",
        "audience": "петербургская аудитория, интересующаяся уходом, красотой и стилем",
        "offer": "визит на заранее согласованную услугу и один нативный материал",
        "result": "Проверить локальную beauty-коллаборацию и запросить актуальные условия.",
        "keywords": {
            "beauty": 5, "бьюти": 5, "красот": 5, "уход": 4, "волос": 5,
            "парикмах": 5, "стилист": 4, "салон": 3, "маникюр": 4,
            "косметолог": 4, "косметик": 4, "макияж": 4, "мода": 2, "стиль": 2,
            "fashion": 2, "lifestyle": 1, "ugc": 1,
        },
        "name_exclusions": ("салон", "студия", "клиника", "центр красоты", "парикмахерская", "toni&guy", "kosa colour", "трц", "premiumclub", "sharlin beauty"),
        "priority_names": ("BEAUTYHOLIC", "Катерина Давыдова", "Кремом по лицу", "Уходом единым"),
    },
    "oliver": {
        "title": "Оливер",
        "business": "студия массажа тела и лица «Оливер» на Савушкина, 127",
        "audience": "петербургская аудитория, интересующаяся wellness, восстановлением и заботой о себе",
        "offer": "визит на подходящую услугу и честный материал в привычном для автора формате",
        "result": "Проверить локальную wellness-коллаборацию и запросить условия.",
        "keywords": {
            "массаж": 6, "spa": 5, "спа": 5, "wellness": 5, "велнес": 5,
            "здоров": 3, "фитнес": 4, "йога": 4, "спорт": 2, "тело": 3,
            "лицо": 2, "восстанов": 4, "релакс": 4, "косметолог": 2, "уход": 2,
        },
        "name_exclusions": ("массаж", "spa", "спа", "студия", "салон", "клиника", "центр", "terrapia", "laramed", "фотограф", "photographer", "риелтор", "недвижим", "обзор интересных сайтов"),
        "priority_names": (),
    },
    "children": {
        "title": "Детские бизнесы",
        "business": "сеть детских парикмахерских «Весёлая расчёска»",
        "audience": "петербургские родители и семьи с детьми",
        "offer": "обзор визита, нативная рекомендация или включение в тематическую подборку",
        "result": "Проверить семейную локальную интеграцию; затем адаптировать под конкретный детский бизнес.",
        "keywords": {
            "дет": 5, "ребен": 5, "ребён": 5, "родител": 5, "мама": 5,
            "папа": 4, "семей": 5, "семь": 3, "школ": 3, "круж": 4,
            "образован": 3, "kids": 5, "family": 4, "театр": 2, "праздник": 3,
            "куда пойти": 3, "досуг": 3,
        },
        "name_exclusions": ("организация детских", "детские праздники", "праздничное бюро", "агентство", "детский центр", "магазин", "школа"),
        "priority_names": ("Мамы и дети", "Детская Афиша", "Куда пойти в Питере с детьми", "Семейный Санкт-Петербург", "Мамы Санкт-Петербург"),
    },
    "riderra": {
        "title": "Riderra",
        "business": "Riderra, сервис трансферов для путешественников, семей и деловых гостей",
        "audience": "люди, которые планируют поездки в Петербург или путешествуют из него",
        "offer": "полезный материал о планировании поездки или реальный тест трансфера",
        "result": "Проверить travel-интеграцию и запросить формат, цену и географию аудитории.",
        "keywords": {
            "путешеств": 6, "туризм": 6, "travel": 6, "trip": 5, "аэропорт": 6,
            "отел": 5, "экскурс": 5, "гид": 4, "маршрут": 4, "трансфер": 6,
            "транспорт": 3, "поездк": 5, "достопримеч": 4, "прогулк": 3,
            "куда сходить": 3, "места петербурга": 4, "турист": 5, "вокзал": 4,
        },
        "name_exclusions": ("турагентство", "туроператор", "трансфер", "отель", "экскурсионное бюро", "магазин"),
        "priority_names": ("Про Питер и путешествия",),
    },
}

PRIORITY_PROFILES: list[dict[str, Any]] = [
    {"segments": ("organika",), "name": "BEAUTYHOLIC", "url": "https://t.me/your_skin_care", "contact": "https://t.me/vareshka_84", "observation": "Канал описывает себя как петербургский блог о beauty, уходе, моде и спорте и указывает администратора."},
    {"segments": ("organika",), "name": "Катерина Давыдова", "url": "https://t.me/kdvmua", "contact": "kdvmua@gmail.com", "observation": "Автор называет себя бьюти-блогером и визажистом из Санкт-Петербурга и указывает email для рекламы."},
    {"segments": ("organika",), "name": "Кремом по лицу", "url": "https://t.me/kremom_po_litsu", "contact": "https://t.me/Eklllerchik", "observation": "Автор публикует экспертный контент об уходе и указывает отдельный Telegram-контакт для записи или рекламы."},
    {"segments": ("organika",), "name": "Уходом единым", "url": "https://t.me/uhodom_edinym", "contact": "https://t.me/rootsmedia", "observation": "Публичное описание называет автора Юлию Носевич и направляет вопросы сотрудничества представителю Roots Media."},
    {"segments": ("organika",), "name": "Antenna Daily", "url": "https://t.me/antennadaily", "contact": "https://t.me/boris_asgard", "observation": "Городское медиа пишет о моде, красоте, культуре и событиях Петербурга и публикует контакт для сотрудничества."},
    {"segments": ("organika", "children"), "name": "Мамы и дети — Санкт-Петербург", "url": "https://t.me/mamy_piter", "contact": "https://t.me/mama_city_admin", "observation": "Канал публикует советы, афишу и материалы для петербургских семей и прямо указывает контакт для рекламы."},
    {"segments": ("children",), "name": "Детская Афиша — Санкт-Петербург", "url": "https://t.me/deti_spb", "contact": "https://t.me/siarhei22", "observation": "Канал собирает мероприятия для детей в Петербурге и указывает администратора."},
    {"segments": ("children",), "name": "Куда пойти в Питере с детьми", "url": "https://t.me/gokidspeterburg", "contact": "https://t.me/alex_admin_tg", "observation": "Канал публикует афишу, события и места для родителей с детьми и прямо указывает контакт для сотрудничества."},
    {"segments": ("children",), "name": "Мамы Санкт-Петербург — Афиша", "url": "https://t.me/afishaspbmami", "contact": "https://t.me/afishaspbmamibot", "observation": "Канал публикует афишу детских мероприятий Петербурга и указывает контакт для сотрудничества и рекламную площадку."},
]


def clean_text(value: str) -> str:
    return " ".join(value.lower().replace("ё", "е").split())


def candidate_text(entity: dict[str, Any]) -> tuple[str, str]:
    sourced = " ".join([
        str(entity.get("display_name", "")),
        str(entity.get("description", "")),
        " ".join(str(item.get("observed", "")) for item in entity.get("evidence", [])),
    ])
    queries = " ".join(str(item) for item in entity.get("research", {}).get("spb_expansion_queries", []))
    return clean_text(sourced), clean_text(queries)


def relevance(entity: dict[str, Any], segment: dict[str, Any]) -> tuple[int, list[str], bool]:
    sourced, queries = candidate_text(entity)
    matched: list[str] = []
    score = 0
    direct = False
    for raw_keyword, weight in segment["keywords"].items():
        keyword = clean_text(raw_keyword)
        if keyword in sourced:
            score += int(weight) * 3
            matched.append(raw_keyword)
            direct = True
        elif keyword in queries:
            score += int(weight)
            matched.append(raw_keyword)
    return score, sorted(set(matched)), direct


def audience_score(entity: dict[str, Any]) -> int:
    bands = {str(channel.get("audience_band", "unknown")) for channel in entity["channels"]}
    if "nano" in bands:
        return 5
    if "micro" in bands:
        return 4
    if "mid" in bands:
        return 3
    return 2


def extract_observation(entity: dict[str, Any]) -> tuple[str, str, str]:
    evidence = entity.get("evidence", [])
    item = evidence[0] if evidence else {}
    observed = str(item.get("observed") or "Оригинальный публичный профиль открыт.")
    title_match = re.search(r"Видео [«\"](.+?)[»\"]", observed)
    observation = f"В публичном профиле найден материал «{title_match.group(1)}»." if title_match else observed
    source_url = str(item.get("source_url") or entity["channels"][0]["canonical_url"])
    researched_at = str(item.get("researched_at") or datetime.now(timezone.utc).isoformat())
    return observation, source_url, researched_at


def public_contact(entity: dict[str, Any]) -> dict[str, Any]:
    description = str(entity.get("description", ""))
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", description, flags=re.IGNORECASE)
    handles = re.findall(r"(?<![\w.])@([A-Za-z0-9_]{5,})", description)
    channel = entity["channels"][0]
    if emails:
        return {"type": "email", "value": emails[0], "status": "public_profile_contact", "source_url": channel["canonical_url"], "confidence": 0.9}
    if handles:
        return {"type": "telegram", "value": f"https://t.me/{handles[0]}", "status": "public_profile_contact", "source_url": channel["canonical_url"], "confidence": 0.85}
    return {"type": "profile", "value": channel["canonical_url"], "status": "manual_route_needs_contact_check", "source_url": channel["canonical_url"], "confidence": 0.6}


def priority_candidate(segment_key: str, profile: dict[str, Any]) -> dict[str, Any]:
    segment = SEGMENTS[segment_key]
    entity_id = hashlib.sha256(f"priority-profile:{profile['url']}".encode()).hexdigest()[:20]
    candidate_id = hashlib.sha256(f"{segment_key}:{entity_id}".encode()).hexdigest()[:20]
    observation = str(profile["observation"])
    draft = (
        f"Здравствуйте! Обратили внимание на ваш канал ({profile['url']}): {observation} "
        f"Мы представляем {segment['business']}. Хотим обсудить локальный формат: {segment['offer']}. "
        "Подскажите, пожалуйста, актуальные форматы, стоимость, географию аудитории и свежие охваты? "
        "До старта отдельно согласуем маркировку, вознаграждение и права на материал."
    )
    quality_scores = {
        "source_validity": 2, "observation_accuracy": 2, "freshness_and_why_now": 1,
        "offer_bridge": 2, "recipient_specificity": 2, "proof_integrity": 2,
        "channel_fit": 2, "single_cta_and_length": 2, "state_and_suppression_safety": 2,
    }
    return {
        "candidate_id": candidate_id, "entity_id": entity_id, "segment_key": segment_key,
        "segment": segment["title"], "name": profile["name"], "profile_type": "channel",
        "primary_handle": str(profile["url"]).rsplit("/", 1)[-1], "platforms": ["telegram"],
        "canonical_urls": [str(profile["url"]).lower().rstrip("/")],
        "score": 96, "score_breakdown": {"service_compatibility": 5, "audience_fit": 5, "public_reachability": 5, "evidence_quality": 5},
        "stage": "worth_checking", "matched_topics": list(segment["keywords"].keys())[:3],
        "why_now": observation,
        "signals": [{"kind": "social_activity", "observed": observation, "inference": f"Предварительная гипотеза: площадка подходит сегменту «{segment['title']}».", "source_title": profile["name"], "source_url": profile["url"], "source_type": "public_telegram_profile", "published_at": "date unavailable", "researched_at": datetime.now(timezone.utc).isoformat()}],
        "sources": [{"title": profile["name"], "url": profile["url"], "published_at": "проверено 2026-08-23"}],
        "public_contact": {"type": "email" if "@" in str(profile["contact"]) and not str(profile["contact"]).startswith("https://") else "telegram", "value": profile["contact"], "status": "public_profile_contact", "source_url": profile["url"], "confidence": 0.95},
        "message_brief": {"segment": segment["audience"], "buyer_persona": "автор или менеджер площадки", "kpi": "ответ с медиакитом, ценой, географией и свежими охватами", "pain": "", "pain_strength": 0, "awareness": "potential_partner", "signal": observation, "result": segment["result"], "proof": "", "angle": segment["offer"], "cta": "Пришлите актуальные форматы, цену, географию и свежие охваты."},
        "suggested_opener": draft, "opener_source_url": profile["url"],
        "quality": {"scores": quality_scores, "total": sum(quality_scores.values()), "verdict": "approve", "reason_codes": []},
        "approval_state": "draft_not_approved", "campaign_state": "research_only",
        "missing_inputs": ["актуальные охваты и география аудитории", "формат и вознаграждение", "дата размещения и права на материал"],
        "limitations": ["Дата последней публикации не использована как timing-сигнал.", "Черновик не является разрешением на отправку."],
    }


def draft_message(entity: dict[str, Any], segment: dict[str, Any], observation: str, source_url: str) -> str:
    title_match = re.search(r"«(.+?)»", observation)
    topic = title_match.group(1) if title_match else entity["display_name"]
    return (
        f"Здравствуйте! Обратили внимание на ваш материал «{topic}» ({source_url}). "
        f"Мы представляем {segment['business']}. Хотим обсудить локальный формат: {segment['offer']}. "
        "До старта отдельно согласуем формат, вознаграждение, маркировку и права на материал. "
        "Подскажите, рассматриваете ли вы такие сотрудничества и куда лучше прислать условия?"
    )


def score_entity(entity: dict[str, Any], segment_key: str) -> dict[str, Any] | None:
    segment = SEGMENTS[segment_key]
    sourced, _ = candidate_text(entity)
    if any(marker in sourced for marker in DISQUALIFIERS):
        return None
    display_name = clean_text(str(entity.get("display_name", "")))
    if any(clean_text(marker) in display_name for marker in segment.get("name_exclusions", ())):
        return None
    relevance_points, matched, direct = relevance(entity, segment)
    if relevance_points < 5 or not direct:
        return None
    audience = audience_score(entity)
    reachability = 5 if entity.get("contactability") == "advertising_contact" else 4 if entity.get("contactability") == "community_messages" else 2
    evidence_quality = 5 if all(channel.get("verification_status") == "original_profile_opened" for channel in entity["channels"]) else 4
    compatibility = min(5, 1 + relevance_points // 6)
    platforms = {str(channel["platform"]) for channel in entity["channels"]}
    creator_platform_bonus = 5 if platforms & {"instagram", "threads", "tiktok"} else 2 if platforms & {"telegram", "vk"} else 0
    score = min(100, round(compatibility * 9 + audience * 5 + reachability * 3 + evidence_quality * 3 + creator_platform_bonus))
    observation, source_url, researched_at = extract_observation(entity)
    contact = public_contact(entity)
    draft = draft_message(entity, segment, observation, source_url)
    quality_scores = {
        "source_validity": 2,
        "observation_accuracy": 2,
        "freshness_and_why_now": 1,
        "offer_bridge": 2,
        "recipient_specificity": 2,
        "proof_integrity": 2,
        "channel_fit": 2 if contact["status"] == "public_profile_contact" else 1,
        "single_cta_and_length": 2,
        "state_and_suppression_safety": 2,
    }
    quality_total = sum(quality_scores.values())
    reason_codes = [] if contact["status"] == "public_profile_contact" else ["SOURCE_MISSING"]
    verdict = "approve" if quality_total >= 15 and not reason_codes else "revise"
    candidate_id = hashlib.sha256(f"{segment_key}:{entity['entity_id']}".encode()).hexdigest()[:20]
    return {
        "candidate_id": candidate_id,
        "entity_id": entity["entity_id"],
        "segment_key": segment_key,
        "segment": segment["title"],
        "name": entity["display_name"],
        "profile_type": entity["profile_type"],
        "primary_handle": entity.get("primary_handle"),
        "platforms": sorted(platforms),
        "canonical_urls": sorted(str(channel["canonical_url"]).lower().rstrip("/") for channel in entity["channels"]),
        "score": score,
        "score_breakdown": {
            "service_compatibility": compatibility,
            "audience_fit": audience,
            "public_reachability": reachability,
            "evidence_quality": evidence_quality,
        },
        "stage": "worth_checking" if score >= 65 else "potential_fit",
        "matched_topics": matched,
        "why_now": observation,
        "signals": [{
            "kind": "social_activity",
            "observed": observation,
            "inference": f"Предварительная гипотеза: тема может быть релевантна сегменту «{segment['title']}».",
            "source_title": entity["display_name"],
            "source_url": source_url,
            "source_type": "public_profile_or_content",
            "published_at": "date unavailable",
            "researched_at": researched_at,
        }],
        "sources": [{"title": entity["display_name"], "url": source_url, "published_at": "date unavailable"}],
        "public_contact": contact,
        "message_brief": {
            "segment": segment["audience"],
            "buyer_persona": "автор или менеджер площадки",
            "kpi": "ответ с актуальными форматами, стоимостью и географией аудитории",
            "pain": "",
            "pain_strength": 0,
            "awareness": "potential_partner",
            "signal": observation,
            "result": segment["result"],
            "proof": "",
            "angle": segment["offer"],
            "cta": "Рассматриваете ли вы такое сотрудничество и куда прислать условия?",
        },
        "suggested_opener": draft,
        "opener_source_url": source_url,
        "quality": {
            "scores": quality_scores,
            "total": quality_total,
            "verdict": verdict,
            "reason_codes": reason_codes,
        },
        "approval_state": "draft_not_approved",
        "campaign_state": "research_only",
        "missing_inputs": [
            "актуальные охваты и география аудитории",
            "формат и вознаграждение",
            "дата размещения и права на материал",
        ] + (["проверенный публичный рекламный контакт"] if reason_codes else []),
        "limitations": [
            "Дата конкретного материала недоступна; перед контактом проверить последнюю активность.",
            "Локальная тема не доказывает долю петербургской аудитории.",
            "Черновик не является разрешением на отправку.",
        ],
    }


def build() -> dict[str, Any]:
    base = json.loads(INPUT.read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    segment_counts: dict[str, int] = {}
    for segment_key in SEGMENTS:
        ranked = [item for entity in base["entities"] if (item := score_entity(entity, segment_key)) is not None]
        ranked.sort(key=lambda item: (int(item["score"]), item["quality"]["total"], item["name"].lower()), reverse=True)
        shortlist = [priority_candidate(segment_key, profile) for profile in PRIORITY_PROFILES if segment_key in profile["segments"]]
        used_ids: set[str] = set()
        used_ids.update(item["candidate_id"] for item in shortlist)
        used_urls = {url for item in shortlist for url in item["canonical_urls"]}
        for priority_name in SEGMENTS[segment_key].get("priority_names", ()):
            normalized = clean_text(priority_name)
            match = next((item for item in ranked if normalized in clean_text(item["name"])), None)
            if match and match["candidate_id"] not in used_ids and not used_urls.intersection(match["canonical_urls"]):
                shortlist.append(match)
                used_ids.add(match["candidate_id"])
                used_urls.update(match["canonical_urls"])
        for item in ranked:
            if len(shortlist) >= 12:
                break
            if item["candidate_id"] in used_ids or used_urls.intersection(item["canonical_urls"]) or item["platforms"] == ["youtube"]:
                continue
            shortlist.append(item)
            used_ids.add(item["candidate_id"])
            used_urls.update(item["canonical_urls"])
        youtube_count = sum(item["platforms"] == ["youtube"] for item in shortlist)
        for item in ranked:
            if len(shortlist) >= LIMIT:
                break
            if item["candidate_id"] in used_ids or used_urls.intersection(item["canonical_urls"]):
                continue
            if item["platforms"] == ["youtube"] and youtube_count >= 28:
                continue
            shortlist.append(item)
            used_ids.add(item["candidate_id"])
            used_urls.update(item["canonical_urls"])
            if item["platforms"] == ["youtube"]:
                youtube_count += 1
        if len(shortlist) < LIMIT:
            for item in ranked:
                if len(shortlist) >= LIMIT:
                    break
                if item["candidate_id"] not in used_ids and not used_urls.intersection(item["canonical_urls"]):
                    shortlist.append(item)
                    used_ids.add(item["candidate_id"])
                    used_urls.update(item["canonical_urls"])
        selected.extend(shortlist)
        segment_counts[segment_key] = len(shortlist)
    return {
        "schema_version": "1.0",
        "mode": "client-partners",
        "title": "Shortlist инфлюенсеров Санкт-Петербурга для четырёх клиентских сценариев",
        "product": {
            "name": "LocalOS — продвижение через локальных инфлюенсеров",
            "url": "https://localos.pro/dashboard/promotion/influencers",
            "brief": "Отобрать локальных авторов, проверить публичный способ связи и подготовить черновики для ручного согласования.",
        },
        "client_business_id": None,
        "icp": {
            "primary": "Локальные авторы и тематические каналы Санкт-Петербурга с релевантным публичным контентом.",
            "adjacent": ["городские медиа", "семейные каналы", "нишевые эксперты"],
            "disqualifiers": list(DISQUALIFIERS),
        },
        "segment_counts": segment_counts,
        "candidates": selected,
        "limitations": [
            "Shortlist подготовлен для ручной проверки; импорта и отправки не было.",
            "Контакты со статусом manual_route_needs_contact_check нельзя использовать до повторной проверки профиля.",
            "Для детского сегмента черновик использует «Весёлую расчёску» как базовый сценарий и должен быть адаптирован под выбранного клиента.",
            "Канал t.me/semejnyjspb исключён 2026-08-23: прежнее семейное название сменилось на «Путь к себе», текущая тематика не подтверждает исходный fit.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write(report: dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["segment_key", "segment", "candidate_id", "entity_id", "name", "profile_type", "primary_handle", "platforms", "score", "stage", "matched_topics", "contact_type", "contact_value", "contact_status", "source_url", "observation", "draft", "quality_total", "quality_verdict", "reason_codes", "approval_state", "campaign_state"]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in report["candidates"]:
            writer.writerow({
                "segment_key": item["segment_key"], "segment": item["segment"],
                "candidate_id": item["candidate_id"], "entity_id": item["entity_id"],
                "name": item["name"], "profile_type": item["profile_type"],
                "primary_handle": item.get("primary_handle"), "platforms": ", ".join(item["platforms"]), "score": item["score"],
                "stage": item["stage"], "matched_topics": ", ".join(item["matched_topics"]),
                "contact_type": item["public_contact"]["type"], "contact_value": item["public_contact"]["value"],
                "contact_status": item["public_contact"]["status"], "source_url": item["opener_source_url"],
                "observation": item["why_now"], "draft": item["suggested_opener"],
                "quality_total": item["quality"]["total"], "quality_verdict": item["quality"]["verdict"],
                "reason_codes": ", ".join(item["quality"]["reason_codes"]),
                "approval_state": item["approval_state"], "campaign_state": item["campaign_state"],
            })


if __name__ == "__main__":
    result = build()
    write(result)
    print(json.dumps({"segment_counts": result["segment_counts"], "candidate_count": len(result["candidates"])}, ensure_ascii=False))
