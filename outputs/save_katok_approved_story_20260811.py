from __future__ import annotations

import json
import uuid
from datetime import datetime

from database_manager import DatabaseManager
from services.content_plan_service import _score_content_candidate
from services.content_voice_service import load_content_voice_context


PLAN_ID = "20948ec9-34f5-4ae9-8aa3-d99597bdee11"
BUSINESS_ID = "761b0d73-bd35-4f20-9501-2fac1e822f1c"
OWNER_ID = "2ac5d045-6093-4a2f-be82-b659cf0a017b"

APPROVED_TEXT = (
    "В конце августа в «Катке» можно прожить три совершенно разных вечера.\n\n"
    "22 августа классическая музыка станет поводом познакомиться: на «Тиндере Чайковского» "
    "гости будут слушать произведения, узнавать любовные истории композиторов и искать совпавшую пару.\n\n"
    "Уже на следующий день настроение изменится. В «Локстоке» понадобятся чувство числа, "
    "немного смелости и умение вовремя сказать «пас».\n\n"
    "А 28 августа зал будет слушать Вивальди особенно внимательно — музыка подскажет, "
    "что спрятано в «Чёрном ящике».\n\n"
    "Все три события начинаются в 19:00. Осталось выбрать, какой вечер хочется прожить первым."
)

CANDIDATES = [
    {
        "id": "user-story-v1",
        "angle": "Три разных вечера",
        "text": APPROVED_TEXT,
    },
    {
        "id": "story-variant-2",
        "angle": "Смена правил",
        "text": (
            "В конце августа каждый вечер в «Катке» будет жить по своим правилам.\n\n"
            "Сначала, 22 августа, музыка поможет познакомиться на «Тиндере Чайковского»: "
            "гости услышат шесть произведений и выберут совпавшую пару.\n\n"
            "На следующий день в «Локстоке» вместо музыкального слуха пригодится чувство числа — "
            "с двумя подсказками, ставками и правом сказать «пас».\n\n"
            "А 28 августа Вивальди станет подсказкой к «Чёрному ящику». Все события начинаются в 19:00."
        ),
    },
    {
        "id": "story-variant-3",
        "angle": "От знакомства к загадке",
        "text": (
            "Август в «Катке» закончится тремя вечерами, которые совсем не похожи друг на друга.\n\n"
            "Сначала классическая музыка станет поводом для знакомства: «Тиндер Чайковского» "
            "пройдёт 22 августа.\n\n"
            "Уже 23 августа гости «Локстока» будут отвечать числами, пользоваться двумя подсказками "
            "и решать, когда сделать ставку, а когда сказать «пас».\n\n"
            "А 28 августа музыка Вивальди поможет угадать, что находится в «Чёрном ящике». "
            "Начало каждого события — в 19:00."
        ),
    },
]


def main() -> None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, metadata_json
            FROM contentplanitems
            WHERE plan_id = %s AND scheduled_for = '2026-08-11'
            LIMIT 1
            """,
            (PLAN_ID,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Katok plan item was not found")
        row_value = dict(row) if isinstance(row, dict) else {}
        item_id = str(row_value.get("id") or "")
        metadata = row_value.get("metadata_json") or {}
        if not isinstance(metadata, dict):
            metadata = json.loads(metadata or "{}")
        brief = metadata.get("content_brief_v1") or {}
        voice = load_content_voice_context(
            cursor,
            user_id=OWNER_ID,
            business_id=BUSINESS_ID,
            limit=5,
        )
        prepared = [
            {
                **candidate,
                "used_fact_ids": ["event", "owner_detail", "owner_source"],
                "unsupported_facts": [],
            }
            for candidate in CANDIDATES
        ]
        scored = [_score_content_candidate(candidate, brief, voice) for candidate in prepared]
        failures = [
            candidate
            for candidate in scored
            if not candidate.get("quality_passed")
            or not candidate.get("factual_gate_passed")
            or not candidate.get("neuroslop_passed")
            or not candidate.get("editorial_quality_passed")
            or not candidate.get("voice_adherence_passed")
            or not candidate.get("clarity_passed")
            or not candidate.get("story_passed")
            or candidate.get("issues")
        ]
        if len(scored) != 3 or failures:
            raise RuntimeError(json.dumps({"failures": failures}, ensure_ascii=False))
        generation = dict(metadata.get("content_generation_v2") or {})
        generation.update(
            {
                "enabled": True,
                "voice_profile_version": int(voice.get("version") or 1),
                "selected_variant_id": "user-story-v1",
                "variants": scored,
            }
        )
        metadata.update(
            {
                "generation_source": "user_approved_editorial",
                "quality_gate_version": "clear_story_v2",
                "user_selected_at": datetime.utcnow().isoformat(),
                "content_generation_v2": generation,
            }
        )
        cursor.execute(
            """
            UPDATE contentplanitems
            SET draft_text = %s,
                status = 'draft_generated',
                metadata_json = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND plan_id = %s
            """,
            (APPROVED_TEXT, json.dumps(metadata, ensure_ascii=False), item_id, PLAN_ID),
        )
        cursor.execute(
            """
            SELECT id
            FROM userexamples
            WHERE user_id = %s AND business_id = %s AND example_type = 'news'
              AND example_text = %s
            LIMIT 1
            """,
            (OWNER_ID, BUSINESS_ID, APPROVED_TEXT),
        )
        example_row = cursor.fetchone()
        example_id = str((dict(example_row) if isinstance(example_row, dict) else {}).get("id") or "")
        if not example_id:
            example_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO userexamples (
                    id, user_id, example_type, example_text, created_at,
                    business_id, platform, origin, quality_status, metadata_json
                ) VALUES (%s, %s, 'news', %s, CURRENT_TIMESTAMP, %s, 'base',
                          'user_approved_edit', 'reference', %s::jsonb)
                """,
                (
                    example_id,
                    OWNER_ID,
                    APPROVED_TEXT,
                    BUSINESS_ID,
                    json.dumps(
                        {
                            "content_plan_id": PLAN_ID,
                            "content_plan_item_id": item_id,
                            "confirmed_by_user": True,
                            "quality_gate_version": "clear_story_v2",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        db.conn.commit()
        print(
            json.dumps(
                {
                    "success": True,
                    "item_id": item_id,
                    "example_id": example_id,
                    "selected": scored[0],
                    "variants_count": len(scored),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
