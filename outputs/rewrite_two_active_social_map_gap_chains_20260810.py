#!/usr/bin/env python3
"""Rewrite two LocalOS draft chains from current public evidence.

Dry-run is the default. ``--apply`` updates the two current research snapshots,
creates draft-only replacement campaigns, and cancels only older unsent drafts.
It never approves, queues, schedules for delivery, or sends anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (str(REPO_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.contact_intelligence_service import upsert_contact_points  # noqa: E402
from services.outreach_campaign_service import _quality_gate, persist_preview  # noqa: E402
from services.outreach_human_language import review_human_language  # noqa: E402
from services.outreach_safety_service import (  # noqa: E402
    research_source_fact_fingerprint,
    strategy_fingerprint,
)


RULES_VERSION = "active_social_map_gap_owner_v1_20260810"
GENERATED_AT = "2026-08-10T20:10:00+03:00"
MAP_ABRIELL = "https://yandex.com/maps/org/abriyell/1038240015/"
MAP_PROKURA = "https://yandex.com/maps/org/doktor_kosmetolog_tatyana_prokura/32816871345/"


COHORT: dict[str, dict[str, Any]] = {
    "b340487b-94aa-4918-8a02-71240cac7986": {
        "lead_id": "4eaa0e32-ef50-4dc8-888f-febf561ab17e",
        "name": "Абриелль",
        "rating": 4.2,
        "reviews": 99,
        "ratings": 230,
        "why_now": "Активно ведёт Telegram; 10 августа 2026 в Яндекс Картах рейтинг 4,2 при 230 оценках и 99 отзывах.",
        "contacts": {
            "email": "info@abriell.ru",
            "telegram": "https://t.me/abriell_admin",
            "vk": "https://vk.com/abriell",
            "phone": "8 (981) 187-87-87",
        },
        "new_contacts": [
            {
                "contact_type": "telegram",
                "value": "https://t.me/abriell_admin",
                "owner_type": "company",
                "source_url": "https://t.me/abriell_clinic/1168",
                "source_type": "official_social",
                "provider": "public",
                "confidence": 0.99,
                "verification_status": "confirmed_source",
                "metadata_json": {"recipient_eligible": True, "messageability": "send_message"},
            }
        ],
        "touches": [
            {
                "channel": "email", "contact_type": "email", "day": 0, "angle": "signal",
                "subject": "Абриелль | ЛокалОС | Сотрудничество",
                "source": "https://t.me/abriell_clinic/1168",
                "observation": "В Telegram Абриелль до 27 июля выходили материалы врачей, а в карточке Яндекс Карт опубликовано 28 новостей.",
                "pain": "Обычно посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
                "solution": "LocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт.",
                "text": """Здравствуйте!\n\nМеня зовут Александр, основатель LocalOS.\n\nВы ведёте несколько площадок: в Telegram до конца июля выходили материалы врачей, а в карточке Яндекс Карт опубликовано 28 новостей.\n\nОбычно посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.\n\nLocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт. Команде останется проверить тексты, а публикация в Картах останется ручной.\n\nВы бы хотели сэкономить время на постах?""",
            },
            {
                "channel": "telegram", "contact_type": "telegram", "day": 4, "angle": "content_operations",
                "source": MAP_ABRIELL,
                "observation": "10 августа 2026 в карточке Абриелль на Яндекс Картах рейтинг 4,2 при 230 оценках и 99 отзывах.",
                "pain": "При таком объёме новые отзывы легко пропустить, а ответы отнимают время команды.",
                "solution": "LocalOS отслеживает новые отзывы и готовит черновики ответов для сотрудника.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nСегодня в карточке Абриелль на Яндекс Картах рейтинг 4,2 при 230 оценках и 99 отзывах.\n\nПри таком объёме новые отзывы легко пропустить, а ответы отнимают время команды.\n\nLocalOS отслеживает новые отзывы и готовит черновики ответов для сотрудника. Если отзыв связан с конкретной процедурой, в ответ можно уместно добавить информацию о ней.\n\nАктуальна ли для Абриелль задача работать с рейтингом и отзывами?""",
            },
            {
                "channel": "vk_manual", "contact_type": "vk", "day": 11, "angle": "average_ticket",
                "source": MAP_ABRIELL,
                "observation": "В карточке Абриелль прайс отмечен обновлённым 22 июня; опубликованы отдельные операции и комплексные услуги с ценами.",
                "pain": "При большом прайсе администратору сложно держать в голове все подходящие сочетания услуг.",
                "solution": "LocalOS по подтверждённому прайсу соберёт матрицу услуг и дополнений, подготовит короткие сценарии и поможет отметить результат.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ карточке Абриелль прайс обновлён 22 июня: опубликованы отдельные операции и комплексные услуги с ценами.\n\nПри большом прайсе администратору сложно держать в голове все подходящие сочетания услуг.\n\nLocalOS по подтверждённому прайсу соберёт матрицу услуг и дополнений, подготовит короткие сценарии и поможет отметить результат. Медицинскую совместимость подтверждает врач.\n\nВам было бы интересно проверить сценарии увеличения среднего чека?""",
            },
            {
                "channel": "phone", "contact_type": "phone", "day": 18, "angle": "integrated_system",
                "source": MAP_ABRIELL,
                "observation": "В карточке Абриелль опубликовано 28 новостей и 99 отзывов.",
                "pain": "Если новые обращения идут в основном из привычных каналов, полезно проверить ещё один источник без большой кампании.",
                "solution": "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ карточке Абриелль опубликовано 28 новостей и 99 отзывов. Это уже заметный объём публичных материалов о клинике.\n\nЕсли новые обращения идут в основном из привычных каналов, полезно проверить ещё один источник без большой кампании.\n\nLocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве. Вы сами решите, кому его отправить.\n\nВам было бы интересно находить новых клиентов через партнёрства?""",
            },
            {
                "channel": "email", "contact_type": "email", "day": 25, "angle": "reviews_service",
                "subject": "Абриелль | ЛокалОС | Сотрудничество",
                "source": MAP_ABRIELL,
                "observation": "В отзывах об Абриелль Яндекс выделяет тему времени ожидания: 73% положительных упоминаний по 12 отзывам.",
                "pain": "Повторяющуюся тему полезно видеть сразу, а не собирать вручную из отзывов.",
                "solution": "LocalOS сгруппирует новые отзывы по темам и подготовит короткую сводку с черновиками ответов.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ отзывах об Абриелль Яндекс отдельно выделяет тему времени ожидания: 73% положительных упоминаний по 12 отзывам.\n\nЭто не вывод о работе клиники, но повторяющуюся тему полезно видеть сразу, а не собирать вручную из отзывов.\n\nLocalOS сгруппирует новые отзывы по темам и подготовит короткую сводку с черновиками ответов. Решения и публикация останутся за сотрудником.\n\nПолезна ли для Абриелль такая сводка?\n\nПоказать, как она может выглядеть?""",
            },
        ],
    },
    "7e3e0f39-3e00-41c6-9343-b5ff054b3103": {
        "lead_id": "d14a0e2b-cc99-41b1-9d89-fee61160b46f",
        "name": "Доктор-косметолог Татьяна Прокура",
        "rating": 4.3,
        "reviews": 5,
        "ratings": 5,
        "why_now": "Активно ведёт Telegram; 10 августа 2026 в Яндекс Картах рейтинг 4,3 при 5 оценках и 5 отзывах, раздела Новости нет.",
        "contacts": {
            "telegram": "https://t.me/Aleksa2884",
            "vk": "https://vk.com/cosmetolog_prokura",
            "phone": "+7 (921) 560-49-03",
        },
        "new_contacts": [],
        "touches": [
            {
                "channel": "telegram", "contact_type": "telegram", "day": 0, "angle": "signal",
                "source": "https://t.me/prokura_cosmetolog/379",
                "observation": "7 августа в Telegram Татьяны Прокуры вышел пост об увеличении губ, а в карточке Яндекс Карт нет раздела Новости.",
                "pain": "Обычно посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.",
                "solution": "LocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт.",
                "text": """Здравствуйте!\n\nМеня зовут Александр, основатель LocalOS.\n\nВы ведёте соцсети: 7 августа в Telegram вышел пост об увеличении губ, а в карточке Яндекс Карт сейчас нет раздела Новости.\n\nОбычно посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время.\n\nLocalOS подготовит из одной согласованной темы отдельные черновики для Telegram, VK и Яндекс Карт. Публикация в Картах останется ручной.\n\nВы бы хотели сэкономить время на постах?""",
            },
            {
                "channel": "vk_manual", "contact_type": "vk", "day": 4, "angle": "content_operations",
                "source": MAP_PROKURA,
                "observation": "10 августа 2026 в карточке Татьяны Прокуры на Яндекс Картах рейтинг 4,3 при 5 оценках и 5 отзывах.",
                "pain": "Когда отзывов немного, каждый новый отзыв заметно влияет на впечатление о карточке, а следить за ними вручную неудобно.",
                "solution": "LocalOS отслеживает новые отзывы и готовит черновики ответов для проверки.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nСегодня в карточке Татьяны Прокуры на Яндекс Картах рейтинг 4,3 при 5 оценках и 5 отзывах.\n\nКогда отзывов немного, каждый новый отзыв заметно влияет на впечатление о карточке, а следить за ними вручную неудобно.\n\nLocalOS отслеживает новые отзывы и готовит черновики ответов для проверки.\n\nАктуальна ли для вас задача работать с рейтингом и отзывами?""",
            },
            {
                "channel": "phone", "contact_type": "phone", "day": 11, "angle": "content_operations",
                "source": "https://t.me/prokura_cosmetolog/378",
                "observation": "В Telegram Татьяна Прокура рассказывает о биоревитализации и увеличении губ, а в карточке Яндекс Карт видны три услуги с ценами.",
                "pain": "Когда услуги на площадках отличаются, клиенту сложнее быстро понять, с чем можно обратиться.",
                "solution": "LocalOS сверит список услуг и подготовит черновики одинаковых описаний для соцсетей и карт.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ Telegram вы рассказываете о биоревитализации, увеличении губ и других процедурах, а в карточке Яндекс Карт видны только три услуги с ценами.\n\nКогда услуги на площадках отличаются, клиенту сложнее быстро понять, с чем к вам можно обратиться.\n\nLocalOS сверит список услуг и подготовит черновики одинаковых описаний для соцсетей и карт. Медицинские формулировки останутся на вашей проверке.\n\nПоказать пример на одной услуге?""",
            },
            {
                "channel": "telegram", "contact_type": "telegram", "day": 18, "angle": "average_ticket",
                "source": "https://t.me/prokura_cosmetolog/378",
                "observation": "В Telegram Татьяны Прокуры отдельно представлены биоревитализация, чистка лица и другие процедуры.",
                "pain": "При большом наборе услуг сложно каждый раз помнить, что уместно предложить дополнительно и когда об этом сказать.",
                "solution": "LocalOS по подтверждённому прайсу соберёт матрицу услуг и дополнений, подготовит короткие сценарии и поможет отметить результат.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ Telegram у вас отдельно представлены биоревитализация, чистка лица и другие процедуры.\n\nПри большом наборе услуг сложно каждый раз помнить, что уместно предложить дополнительно и когда об этом сказать.\n\nLocalOS по подтверждённому прайсу соберёт матрицу услуг и дополнений, подготовит короткие сценарии и поможет отметить результат. Медицинскую совместимость подтверждает врач.\n\nВам было бы интересно проверить сценарии увеличения среднего чека?""",
            },
            {
                "channel": "phone", "contact_type": "phone", "day": 25, "angle": "integrated_system",
                "source": "https://t.me/prokura_cosmetolog/379",
                "observation": "В Telegram Татьяны Прокуры указано, что она принимает в Московском и Фрунзенском районах Санкт-Петербурга.",
                "pain": "Кроме привычных каналов, новых клиентов можно искать через местные бизнесы с похожей аудиторией.",
                "solution": "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве.",
                "text": """Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\nВ Telegram указано, что вы принимаете клиентов в Московском и Фрунзенском районах Санкт-Петербурга.\n\nКроме привычных каналов, новых клиентов можно искать через местные бизнесы с похожей аудиторией.\n\nLocalOS подготовит список таких бизнесов и черновик предложения о партнёрстве. Вы сами решите, кому его отправить.\n\nВам было бы интересно находить новых клиентов через партнёрства?""",
            },
        ],
    },
}


def connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def superadmin_id(cur: Any) -> str:
    cur.execute("SELECT id FROM users WHERE COALESCE(is_superadmin,FALSE)=TRUE AND is_active=TRUE ORDER BY updated_at DESC NULLS LAST LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("active_superadmin_not_found")
    return str(row["id"])


def contact_id(cur: Any, lead_id: str, contact_type: str, value: str) -> str:
    cur.execute(
        """SELECT id FROM lead_contact_points
           WHERE lead_id=%s AND contact_type=%s AND value=%s
           ORDER BY CASE verification_status WHEN 'verified' THEN 0 WHEN 'confirmed_source' THEN 1 WHEN 'found' THEN 2 ELSE 3 END,
                    confidence DESC, updated_at DESC LIMIT 1""",
        (lead_id, contact_type, value),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError(f"contact_not_found:{lead_id}:{contact_type}:{value}")
    return str(row["id"])


def current_sender(cur: Any) -> str:
    cur.execute(
        """SELECT id FROM outreach_sender_accounts
           WHERE sender_identity='localosgo@gmail.com' AND channel='email'
             AND status='connected' AND outreach_enabled=TRUE
           ORDER BY updated_at DESC LIMIT 1"""
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("localosgo_sender_not_ready")
    return str(row["id"])


def update_research(cur: Any, workstream_id: str, item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    researched_at = datetime.now(timezone.utc).isoformat()
    signals = []
    for idx, touch in enumerate(item["touches"]):
        signals.append({
            "evidence_id": f"current:{item['lead_id']}:{idx}",
            "kind": "social_activity" if idx == 0 else "map_issue",
            "observed_fact": touch["observation"],
            "fact": touch["observation"],
            "hypothesis": touch["pain"],
            "relevance": touch["solution"],
            "source_url": touch["source"],
            "source_type": "official_social" if "t.me/" in touch["source"] else "official_map_card",
            "published_at": "2026-07-27" if item["name"] == "Абриелль" and idx == 0 else "2026-08-07" if item["name"].startswith("Доктор") and idx == 0 else None,
            "researched_at": researched_at,
            "freshness": "fresh" if "t.me/" in touch["source"] else "current_snapshot",
            "confidence": 1.0,
            "usable_for_outreach": True,
            "signal_combo": "active_social_with_map_gap" if idx == 0 else None,
        })
    sources = []
    for signal in signals:
        if not any(source["url"] == signal["source_url"] for source in sources):
            sources.append({
                "title": item["name"], "url": signal["source_url"],
                "source_type": signal["source_type"], "observed_at": researched_at,
            })
    brief = {
        "segment": "beauty_medical", "buyer_persona": "владелец или руководитель",
        "kpi": "время на контент, рейтинг карточки, средний чек и новые клиенты",
        "pain": "Гипотезы проверяются вопросом; публичный сигнал не считается доказательством боли.",
        "signal": item["why_now"], "result": "черновики и сценарии на ручную проверку",
        "proof": "", "angle": "active_social_with_map_gap",
        "cta": "один конкретный вопрос в каждом касании",
    }
    report_hash = canonical_hash({"signals": signals, "sources": sources, "brief": brief})
    cur.execute(
        """UPDATE lead_workstream_research
           SET why_now=%s, signals_json=%s, sources_json=%s, message_brief_json=%s,
               evidence_json=%s, report_hash=%s, researched_at=NOW(),
               selected_personalization_id=NULL, outreach_decision_json='{}'::jsonb,
               message_readiness_json=%s
           WHERE id=(SELECT id FROM lead_workstream_research WHERE workstream_id=%s ORDER BY researched_at DESC, created_at DESC LIMIT 1)
           RETURNING *""",
        (item["why_now"], Json(signals), Json(sources), Json(brief), Json(signals), report_hash,
         Json({"status": "draft_review_required", "rules_version": RULES_VERSION}), workstream_id),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError("research_row_not_found")
    cur.execute("UPDATE prospectingleads SET rating=%s, reviews_count=%s, updated_at=NOW() WHERE id=%s", (item["rating"], item["reviews"], item["lead_id"]))
    return dict(row), signals


def build_touch(item: dict[str, Any], touch: dict[str, Any], index: int, cp_id: str, sender_id: str, fingerprint: str) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_id = f"current:{item['lead_id']}:{index}"
    candidate = {
        "id": f"candidate:{item['lead_id']}:{index}", "recipient": item["name"],
        "recipient_segment": "beauty_medical", "sender_mode": "localos",
        "observed_fact": touch["observation"], "evidence_id": evidence_id,
        "evidence_ids": [evidence_id], "source_url": touch["source"],
        "supporting_evidence": [{"evidence_id": evidence_id, "source_url": touch["source"]}],
        "source_type": "official_social" if "t.me/" in touch["source"] else "official_map_card",
        "freshness": "fresh" if "t.me/" in touch["source"] else "current_snapshot",
        "evidence_status": "observed", "evidence_kind": "social_activity" if index == 0 else "map_issue",
        "problem_hypothesis": touch["pain"], "pain_hypothesis": touch["pain"],
        "problem_hypothesis_status": "hypothesis", "relevance_to_offer": touch["pain"],
        "bridge": touch["pain"], "localos_action": touch["solution"],
        "next_step": "Один вопрос из текста.",
        "trust_statement": "LocalOS готовит черновики; публикация и медицинские решения остаются у человека.",
    }
    human = review_human_language(
        touch["text"], pain_hypothesis=touch["pain"],
        require_signal_flow=touch["angle"] == "signal",
    )
    gate = _quality_gate(
        touch["text"], candidate, {"proof": "manual_review", "forbidden_claims": []},
        channel=touch["channel"], channel_status="ready" if touch["channel"] == "email" else "manual",
        suppressed=False, angle=touch["angle"],
    )
    if not human["passed"] or not gate["passed"]:
        raise ValueError(f"quality_failed:{item['name']}:{index}:{human.get('reason_codes')}:{gate.get('reason_codes')}")
    strategy = {"human_edited": True, "content_source": "owner_review_20260810", "rules_version": RULES_VERSION}
    record = {
        "sequence_index": index, "channel": touch["channel"], "day_offset": touch["day"],
        "scheduled_at": datetime.now(timezone.utc) + timedelta(days=touch["day"]),
        "angle": touch["angle"], "subject": touch.get("subject"), "text": touch["text"],
        "quality_gate": gate, "channel_status": "ready" if touch["channel"] == "email" else "manual",
        "contact_point_id": cp_id, "sender_account_id": sender_id if touch["channel"] == "email" else None,
        "evidence_id": evidence_id, "evidence_kind": candidate["evidence_kind"],
        "source_url": touch["source"], "observation": touch["observation"],
        "problem_hypothesis": touch["pain"], "pain_hypothesis": touch["pain"],
        "solution": touch["solution"], "relevance_bridge": touch["pain"],
        "source_fact_fingerprint": fingerprint, "strategy": strategy,
        "strategy_fingerprint": strategy_fingerprint(strategy),
        "generation_source": "manual_product_correction", "human_edited": True,
    }
    return record, candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.environ["OUTREACH_ROOM_SYNC_ENABLED"] = "false"
    conn = connect()
    # Dry-run exercises the exact write path and always rolls the transaction back.
    conn.set_session(readonly=False, autocommit=False)
    result: dict[str, Any] = {"dry_run": not args.apply, "rules_version": RULES_VERSION, "leads": []}
    try:
        cur = conn.cursor()
        actor = superadmin_id(cur)
        sender = current_sender(cur)
        for workstream_id, item in COHORT.items():
            cur.execute("SELECT * FROM lead_workstreams WHERE id=%s FOR UPDATE" if args.apply else "SELECT * FROM lead_workstreams WHERE id=%s", (workstream_id,))
            ws = cur.fetchone()
            if not ws or ws["workstream_type"] != "localos_sales":
                raise RuntimeError(f"workstream_invalid:{workstream_id}")
            cur.execute("SELECT COUNT(*) AS n FROM outreach_suppressions WHERE lead_id=%s AND (expires_at IS NULL OR expires_at>NOW())", (item["lead_id"],))
            if int(cur.fetchone()["n"]):
                raise RuntimeError(f"active_suppression:{item['name']}")
            cur.execute("SELECT COUNT(*) AS n FROM outreach_inbound_events WHERE lead_id=%s AND is_human=TRUE", (item["lead_id"],))
            if int(cur.fetchone()["n"]):
                raise RuntimeError(f"human_inbound:{item['name']}")
            if item.get("new_contacts"):
                upsert_contact_points(cur, item["lead_id"], item["new_contacts"])
            research, evidence = update_research(cur, workstream_id, item)
            fingerprint = research_source_fact_fingerprint(research)
            cur.execute("SELECT sender_profile_id, selected_offer_json, trust_strategy FROM outreach_campaigns WHERE workstream_id=%s ORDER BY version DESC LIMIT 1", (workstream_id,))
            previous = cur.fetchone()
            if not previous:
                raise RuntimeError(f"campaign_context_missing:{item['name']}")
            touches = []
            candidates = []
            for index, touch in enumerate(item["touches"]):
                cp = contact_id(cur, item["lead_id"], touch["contact_type"], item["contacts"][touch["contact_type"]])
                record, candidate = build_touch(item, touch, index, cp, sender, fingerprint)
                touches.append(record)
                candidates.append(candidate)
            preview = {
                "status": "ready", "workstream_id": workstream_id, "lead_id": item["lead_id"],
                "lead": {"name": item["name"]}, "scope_type": "platform", "business_id": None,
                "sender_profile_id": str(previous["sender_profile_id"]), "sender_mode": "localos",
                "sender_scope_type": "platform", "selected_offer": dict(previous.get("selected_offer_json") or {}),
                "selected_trust": {"strategy": previous.get("trust_strategy")},
                "decision": {"action": "draft_only", "reason": "user_requested_current_evidence_rewrite"},
                "evidence": evidence, "personalization_candidates": candidates, "touches": touches,
            }
            lead_result = {
                "lead": item["name"], "workstream_id": workstream_id, "source_fact_fingerprint": fingerprint,
                "touches": [{"channel": t["channel"], "subject": t.get("subject"), "text": t["text"], "score": t["quality_gate"].get("total_score"), "passed": t["quality_gate"]["passed"]} for t in touches],
            }
            if args.apply:
                saved = persist_preview(cur, preview, user_id=actor)
                cur.execute(
                    """UPDATE outreach_campaigns SET status='cancelled', stop_reason=%s, updated_at=NOW()
                       WHERE workstream_id=%s AND status='draft' AND id<>%s""",
                    (f"superseded_by_{RULES_VERSION}", workstream_id, saved["id"]),
                )
                lead_result["saved"] = saved
            result["leads"].append(lead_result)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    result["canonical_sha256"] = canonical_hash(result["leads"])
    result["approved"] = 0
    result["queued"] = 0
    result["sent"] = 0
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
