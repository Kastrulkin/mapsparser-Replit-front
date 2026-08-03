#!/usr/bin/env python3
"""Apply the operator-approved LocalOS founder context for beauty outreach.

Dry-run is the default. The script updates the existing canonical platform
sender profile; it does not create a second profile or any campaigns.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from pg_db_utils import get_db_connection


COMPETENCE_STORY = (
    "За десять лет предпринимательства я видел малый бизнес как основатель и как "
    "разработчик систем автоматизации. Владельцы редко говорят системными терминами - "
    "чаще говорят: \"нет клиентов\", \"не знаю, что публиковать\", \"всё держится на мне\". "
    "Поэтому я создал LocalOS - чтобы превращать повторяющиеся задачи в понятные "
    "рабочие сценарии."
)

PROOF_POINT = {
    "id": "localos-240-points",
    "fact": "LocalOS уже применяется более чем в 240 точках малого бизнеса.",
    "status": "approved",
    "source": "operator_approved_2026-08-03",
}

ALLOWED_OFFER = {
    "id": "public-card-short-review",
    "text": (
        "Короткий разбор публичной карточки: что уже работает, что мешает клиенту "
        "быстро понять предложение и какой первый шаг можно проверить без "
        "автоматических изменений."
    ),
    "status": "approved",
    "source": "operator_approved_2026-08-03",
}

VOICE_EXAMPLES = [
    {
        "id": "beauty-email-opening",
        "text": (
            "Здравствуйте! Я Александр Демьянов, основатель LocalOS. Посмотрел вашу "
            "публичную карточку и увидел одну конкретную точку, которую можно проверить. "
            "Могу прислать короткий разбор?"
        ),
        "status": "approved",
    },
    {
        "id": "beauty-email-close",
        "text": (
            "Здравствуйте! Коротко закрою тему. Если разбор карточки сейчас неактуален, "
            "больше напоминать не буду. Вернуться к этому позже?"
        ),
        "status": "approved",
    },
]

PAIN_FRAMEWORK = {
    "source": "operator_research_2026-08-03",
    "status": "approved",
    "measurement": "share_of_mentions_not_unique_owners",
    "rule": (
        "Это язык рынка, а не факт о конкретном получателе. Использовать только как "
        "опыт основателя или гипотезу, никогда как диагноз салону."
    ),
    "themes": [
        {"key": "marketing_and_clients", "mentions": 1618, "share_pct": 26.0, "phrasing": "клиентов нет; реклама не приводит записи; не хватает времени на контент"},
        {"key": "team", "mentions": 1135, "share_pct": 18.3, "phrasing": "мастера уходят; трудно найти сотрудников; команда не соблюдает правила"},
        {"key": "service_and_reputation", "mentions": 1040, "share_pct": 16.7, "phrasing": "плохой отзыв; конфликт с клиентом; риск для репутации"},
        {"key": "prices_and_average_check", "mentions": 634, "share_pct": 10.2, "phrasing": "страшно поднять цену; скидки съедают маржу; средний чек низкий"},
        {"key": "owner_overload", "mentions": 444, "share_pct": 7.1, "phrasing": "всё держится на владельце; нет времени; выгорание"},
        {"key": "retention", "mentions": 300, "share_pct": 4.8, "phrasing": "клиенты не возвращаются; уходят за мастером"},
        {"key": "profit", "mentions": 298, "share_pct": 4.8, "phrasing": "выручка есть, а прибыли нет"},
        {"key": "cancellations", "mentions": 264, "share_pct": 4.2, "phrasing": "отмены, переносы и пустые окна"},
        {"key": "seasonality", "mentions": 253, "share_pct": 4.1, "phrasing": "то густо, то пусто; мёртвый сезон"},
        {"key": "analytics", "mentions": 228, "share_pct": 3.7, "phrasing": "непонятны прибыль, возвратность и источники клиентов"},
    ],
}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _merge_by_id(existing: Any, additions: list[dict[str, Any]]) -> list[Any]:
    merged = _list(existing)
    addition_ids = {str(item.get("id") or "") for item in additions}
    merged = [
        item
        for item in merged
        if not isinstance(item, dict) or str(item.get("id") or "") not in addition_ids
    ]
    return merged + additions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT *
            FROM outreach_sender_profiles
            WHERE workstream_type = 'localos_sales'
              AND client_business_id IS NULL
              AND is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        profile = cursor.fetchone()
        if not profile:
            raise LookupError("Canonical LocalOS sender profile not found")

        outreach_context = (
            dict(profile.get("outreach_context_json"))
            if isinstance(profile.get("outreach_context_json"), dict)
            else {}
        )
        outreach_context.update({
            "competence_story_status": "approved",
            "competence_story_source": "operator_approved_2026-08-03",
            "beauty_owner_pain_framework": PAIN_FRAMEWORK,
        })
        proof_points = _merge_by_id(profile.get("proof_points_json"), [PROOF_POINT])
        offers = _merge_by_id(profile.get("allowed_offers_json"), [ALLOWED_OFFER])
        voice_examples = _merge_by_id(profile.get("voice_examples_json"), VOICE_EXAMPLES)

        result = {
            "execute": args.execute,
            "profile_id": str(profile.get("id") or ""),
            "display_name": "Александр Демьянов",
            "company_name": "LocalOS",
            "proof_count": len(proof_points),
            "offer_count": len(offers),
            "pain_theme_count": len(PAIN_FRAMEWORK["themes"]),
        }
        if not args.execute:
            conn.rollback()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        cursor.execute(
            """
            UPDATE outreach_sender_profiles
            SET display_name = %s,
                role_title = %s,
                company_name = %s,
                competence_story = %s,
                proof_points_json = %s,
                allowed_offers_json = %s,
                voice_examples_json = %s,
                outreach_context_json = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                "Александр Демьянов",
                "основатель LocalOS",
                "LocalOS",
                COMPETENCE_STORY,
                Json(proof_points),
                Json(offers),
                Json(voice_examples),
                Json(outreach_context),
                profile["id"],
            ),
        )
        conn.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
