from __future__ import annotations

import json
from datetime import date

from database_manager import DatabaseManager
from services.content_plan_service import (
    _build_content_brief_v1,
    _score_content_candidate,
    create_generated_content_plan,
)
from services.content_voice_service import load_content_voice_context


BUSINESS_ID = "761b0d73-bd35-4f20-9501-2fac1e822f1c"
OWNER_ID = "2ac5d045-6093-4a2f-be82-b659cf0a017b"
OLD_PLAN_ID = "94fcf55b-a3c7-43d3-a415-ea73c9b18823"
CHANNELS = ["yandex_maps", "two_gis", "google_business", "telegram", "vk"]
AUDIENCE = (
    "Жители и гости Краснодара, которым интересны камерные концерты, интеллектуальные игры, "
    "современное искусство и необычные форматы событий."
)


ITEMS = [
    {
        "scheduled_for": "2026-08-11",
        "content_type": "event",
        "theme": "Три события «Катка» во второй половине августа",
        "goal": "Помочь выбрать между концертом-свиданием, интеллектуальной игрой и концертом-казино.",
        "event": "В афише «Катка» опубликованы три события на 22, 23 и 28 августа.",
        "details": (
            "22 августа в 19:00 — «Тиндер Чайковского»; 23 августа в 19:00 — «Локсток»; "
            "28 августа в 19:00 — «Черный ящик». Все события проходят в «Катке» в Краснодаре."
        ),
        "main_idea": "В конце августа в «Катке» можно выбрать один из трёх принципиально разных вечеров.",
        "expected_action": "Открыть официальную афишу и выбрать событие.",
        "source": "https://katok.io/events.html",
    },
    {
        "scheduled_for": "2026-08-14",
        "content_type": "event",
        "theme": "«Тиндер Чайковского»: концерт, на котором выбирают пару",
        "goal": "Объяснить механику концерта-свидания без общих слов о классической музыке.",
        "event": "22 августа в 19:00 в «Катке» состоится концерт-свидание «Тиндер Чайковского».",
        "details": (
            "Гости услышат шесть произведений и истории любовных похождений композиторов, решат, "
            "с кем пошли бы на свидание, и узнают, с кем в зале составляют пару. Билеты — от 1 500 ₽."
        ),
        "main_idea": "Это концерт с игровой механикой знакомства, а не обычная программа из шести произведений.",
        "expected_action": "Посмотреть программу и выбрать билет на официальной странице события.",
        "source": "https://katok.io/events/event.html?id=1b619b04c43f",
    },
    {
        "scheduled_for": "2026-08-18",
        "content_type": "event",
        "theme": "Как устроен «Локсток»: числовые вопросы, ставки и блеф",
        "goal": "Показать, почему в игре может победить новичок без энциклопедических знаний.",
        "event": "23 августа в 19:00 в «Катке» пройдёт игра «Локсток» с Марией Тушкановой.",
        "details": (
            "Ответ на каждый вопрос — число. Игроки получают две подсказки, повышают ставку или говорят «пас». "
            "Формат соединяет викторину и покер; билет стоит 1 500 ₽."
        ),
        "main_idea": "В «Локстоке» важны не только знания, но и чувство числа, ставка и решение вовремя остановиться.",
        "expected_action": "Открыть официальную страницу события и забронировать участие.",
        "source": "https://katok.io/events/event.html?id=22886cea8595",
    },
    {
        "scheduled_for": "2026-08-21",
        "content_type": "event",
        "theme": "Два вечера подряд: «Тиндер Чайковского» или «Локсток»",
        "goal": "Дать понятный выбор между музыкой и интеллектуальной игрой на ближайшие выходные.",
        "event": "22 и 23 августа в «Катке» пройдут два разных события, оба начинаются в 19:00.",
        "details": (
            "22 августа — концерт-свидание «Тиндер Чайковского» с шестью произведениями и выбором пары; "
            "23 августа — «Локсток», игра на числовые вопросы со ставками и блефом."
        ),
        "main_idea": "Один уикенд предлагает два разных сценария: слушать и знакомиться или считать и рисковать.",
        "expected_action": "Сравнить два события в официальной афише и выбрать своё.",
        "source": "https://katok.io/events.html",
    },
    {
        "scheduled_for": "2026-08-23",
        "content_type": "event",
        "theme": "Сегодня в «Катке» — «Локсток»",
        "goal": "Сделать конкретное напоминание в день события без искусственного дефицита мест.",
        "event": "Сегодня, 23 августа, в 19:00 в «Катке» начинается игра «Локсток».",
        "details": (
            "Вопросы имеют числовые ответы; игроки получают подсказки, делают ставки или пасуют. "
            "Ведущая — Мария Тушканова, автор проекта «Моя игра». Билет стоит 1 500 ₽."
        ),
        "main_idea": "Сегодня можно проверить не объём знаний, а интуицию, ставку и умение читать игру.",
        "expected_action": "Проверить доступность участия на официальной странице события.",
        "source": "https://katok.io/events/event.html?id=22886cea8595",
    },
    {
        "scheduled_for": "2026-08-25",
        "content_type": "event",
        "theme": "«Черный ящик»: услышать подсказку у Вивальди",
        "goal": "Объяснить игровую механику концерта через один конкретный образ.",
        "event": "28 августа в 19:00 в «Катке» состоится концерт-казино «Черный ящик».",
        "details": (
            "Струнный квартет играет «Времена года» Вивальди. В каждой части зашифрован зверь, гроза или предмет; "
            "он находится в чёрном ящике на сцене, а гости слушают и угадывают. Билеты — от 1 500 ₽."
        ),
        "main_idea": "На этом концерте музыка становится подсказкой в игре, а не фоном.",
        "expected_action": "Открыть официальную страницу события и выбрать билет.",
        "source": "https://katok.io/events/concert.html?id=b627e3dfc223",
    },
    {
        "scheduled_for": "2026-08-28",
        "content_type": "event",
        "theme": "Сегодня — концерт-казино «Черный ящик»",
        "goal": "Напомнить точное время и механику события без рекламных обещаний.",
        "event": "Сегодня, 28 августа, в 19:00 в «Катке» начинается концерт-казино «Черный ящик».",
        "details": (
            "Квартет играет «Времена года» Вивальди, а гости угадывают предметы, зверей и явления, "
            "зашифрованные в музыке. Сбор гостей указан на 18:30; начало — в 19:00."
        ),
        "main_idea": "Сегодня Вивальди звучит как серия загадок с чёрным ящиком на сцене.",
        "expected_action": "Проверить билеты и подробности на официальной странице события.",
        "source": "https://katok.io/events/concert.html?id=b627e3dfc223",
    },
    {
        "scheduled_for": "2026-09-01",
        "content_type": "space",
        "theme": "Постоянная выставка «Катка»: работа со своей историей",
        "goal": "Рассказать о выставке через конкретную работу, а не через абстрактную атмосферу.",
        "event": "В «Катке» действует постоянная выставка текстильных работ со смыслом.",
        "details": (
            "Одна из работ — «Красная нить Ариадны»: история о нити, которая помогла выйти из лабиринта, "
            "но не помогла остаться вместе. Размер — 140 × 210 см, материал — хлопковый шнур."
        ),
        "main_idea": "На выставке каждая работа раскрывается через отдельный сюжет, который можно пересказать другому.",
        "expected_action": "Посмотреть работы на официальном сайте или зайти на выставку.",
        "source": "https://katok.io/catalog.html",
    },
    {
        "scheduled_for": "2026-09-05",
        "content_type": "space",
        "theme": "Как найти «Каток» у парка Галицкого",
        "goal": "Дать посетителю короткую и точную инструкцию перед визитом.",
        "event": "Официальная страница «Катка» уточняет адрес и расположение входа.",
        "details": (
            "Адрес: Краснодар, улица Жлобы, 139. «Каток» находится рядом с парком Галицкого; "
            "вход — со стороны стадиона."
        ),
        "main_idea": "До входа проще дойти, если заранее ориентироваться на сторону стадиона.",
        "expected_action": "Открыть официальную схему и построить маршрут.",
        "source": "https://katok.io/contact.html",
    },
]


def _brief_answers(item: dict[str, str]) -> dict[str, object]:
    return {
        "infopovod": item["event"],
        "confirmed_details": item["details"],
        "audience": AUDIENCE,
        "main_idea": item["main_idea"],
        "expected_action": item["expected_action"],
        "source": item["source"],
        "target_platforms": CHANNELS,
    }


def _plan_payload(plan_id: str) -> dict[str, object]:
    weekly_groups: dict[str, list[dict[str, object]]] = {}
    generated_items: list[dict[str, object]] = []
    for item in ITEMS:
        generated_item = {
            "scheduled_for": item["scheduled_for"],
            "content_type": item["content_type"],
            "theme": item["theme"],
            "goal": item["goal"],
            "source_kind": "official_site",
            "source_ref": item["source"],
            "brief_answers": _brief_answers(item),
        }
        generated_items.append(generated_item)
        item_date = date.fromisoformat(item["scheduled_for"])
        week_key = f"{item_date.isocalendar().year}-W{item_date.isocalendar().week:02d}"
        weekly_groups.setdefault(week_key, []).append(generated_item)
    return {
        "id": plan_id,
        "title": "Контент-план «Катка» с 11 августа",
        "period_days": 30,
        "period_start": "2026-08-11",
        "period_end": "2026-09-09",
        "selected_channels": CHANNELS,
        "items": generated_items,
        "weekly_groups": weekly_groups,
        "meta": {
            "density": "light",
            "items_target": len(ITEMS),
            "selected_channels": CHANNELS,
            "sources_used": ["official_site"],
            "content_types_used": sorted({item["content_type"] for item in ITEMS}),
            "grounded_rules": "content_brief_v1",
            "neuroslop_filter": True,
        },
    }


def _configure_plan(plan_id: str) -> list[str]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM contentplanitems WHERE plan_id = %s ORDER BY scheduled_for, created_at, id",
            (plan_id,),
        )
        item_ids = [str(row[0]) for row in cursor.fetchall() or []]
        if len(item_ids) != len(ITEMS):
            raise RuntimeError(f"Expected {len(ITEMS)} generated items, got {len(item_ids)}")
        for item_id, item in zip(item_ids, ITEMS):
            metadata = {
                "brief_answers": _brief_answers(item),
                "source_provenance": {
                    "type": "official_site",
                    "url": item["source"],
                    "checked_at": "2026-08-11",
                },
                "generation_rules": {
                    "content_generation_v2": True,
                    "factual_gate": True,
                    "quality_threshold": 70,
                    "neuroslop_filter": True,
                },
            }
            cursor.execute(
                """
                UPDATE contentplanitems
                SET scheduled_for = %s,
                    content_type = %s,
                    theme = %s,
                    goal = %s,
                    source_kind = 'official_site',
                    source_ref = %s,
                    seo_keyword = NULL,
                    seo_views = 0,
                    service_id = NULL,
                    transaction_id = NULL,
                    draft_text = NULL,
                    status = 'planned',
                    metadata_json = %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    item["scheduled_for"],
                    item["content_type"],
                    item["theme"],
                    item["goal"],
                    item["source"],
                    json.dumps(metadata, ensure_ascii=False),
                    item_id,
                ),
            )
        payload = _plan_payload(plan_id)
        cursor.execute(
            """
            UPDATE contentplans
            SET title = %s,
                period_days = 30,
                period_start = '2026-08-11',
                period_end = '2026-09-09',
                generated_plan_json = %s::jsonb,
                published_plan_json = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                payload["title"],
                json.dumps(payload, ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
                plan_id,
            ),
        )
        db.conn.commit()
        return item_ids
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _editorial_candidates(item: dict[str, str]) -> list[dict[str, object]]:
    event = item["event"].strip()
    details = item["details"].strip()
    main_idea = item["main_idea"].strip()
    return [
        {
            "id": "variant-fact-first",
            "angle": "Сначала факт",
            "text": f"{event} {details}\n\nПодробности — на официальной странице «Катка».",
            "used_fact_ids": ["event", "owner_detail", "owner_source"],
            "unsupported_facts": [],
        },
        {
            "id": "variant-mechanics-first",
            "angle": "Сначала механика",
            "text": f"{main_idea}\n\n{event} {details} Смотрите подробности на официальной странице «Катка».",
            "used_fact_ids": ["event", "owner_detail", "owner_source"],
            "unsupported_facts": [],
        },
        {
            "id": "variant-decision-first",
            "angle": "Помочь выбрать",
            "text": f"{item['theme']}. {main_idea}\n\n{details} Узнайте подробности на официальной странице «Катка».",
            "used_fact_ids": ["event", "owner_detail", "owner_source"],
            "unsupported_facts": [],
        },
    ]


def _generate_editorial_drafts(plan_id: str, item_ids: list[str]) -> list[dict[str, object]]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        voice = load_content_voice_context(
            cursor,
            user_id=OWNER_ID,
            business_id=BUSINESS_ID,
            limit=5,
        )
        results: list[dict[str, object]] = []
        for item_id, item in zip(item_ids, ITEMS):
            cursor.execute(
                """
                SELECT i.*, p.business_id
                FROM contentplanitems i
                JOIN contentplans p ON p.id = i.plan_id
                WHERE i.id = %s AND i.plan_id = %s
                """,
                (item_id, plan_id),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError(f"Plan item not found: {item_id}")
            if isinstance(row, dict):
                item_record = dict(row)
            else:
                columns = [description[0] for description in cursor.description]
                item_record = dict(zip(columns, row))
            brief = _build_content_brief_v1(item_record, {})
            if not brief.get("complete"):
                raise RuntimeError(
                    "Incomplete content brief: "
                    + json.dumps({"item_id": item_id, "brief": brief}, ensure_ascii=False)
                )
            scored = [
                _score_content_candidate(candidate, brief, voice)
                for candidate in _editorial_candidates(item)
            ]
            failed = [
                candidate
                for candidate in scored
                if not candidate.get("quality_passed")
                or int(candidate.get("score") or 0) < 70
                or candidate.get("issues")
            ]
            normalized_texts = {
                " ".join(str(candidate.get("text") or "").lower().split())
                for candidate in scored
            }
            if failed or len(scored) != 3 or len(normalized_texts) != 3:
                raise RuntimeError(
                    "Editorial candidate validation failed: "
                    + json.dumps(
                        {
                            "item_id": item_id,
                            "failed": failed,
                            "variants_count": len(scored),
                            "distinct_count": len(normalized_texts),
                        },
                        ensure_ascii=False,
                    )
                )
            selected = sorted(
                scored,
                key=lambda candidate: int(candidate.get("score") or 0),
                reverse=True,
            )[0]
            generation_metadata = {
                "generation_source": "editorial_grounded",
                "generation_fallback_reason": "model_three_candidates_contract_failed",
                "language": "ru",
                "content_brief_v1": brief,
                "content_generation_v2": {
                    "enabled": True,
                    "voice_profile_version": int(voice.get("version") or 1),
                    "selected_variant_id": str(selected.get("id") or ""),
                    "variants": scored,
                },
            }
            cursor.execute(
                """
                UPDATE contentplanitems
                SET draft_text = %s,
                    status = 'draft_generated',
                    metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND plan_id = %s
                """,
                (
                    str(selected.get("text") or ""),
                    json.dumps(generation_metadata, ensure_ascii=False),
                    item_id,
                    plan_id,
                ),
            )
            results.append(
                {
                    "item_id": item_id,
                    "selected_variant_id": selected.get("id"),
                    "selected_score": selected.get("score"),
                    "variants_count": len(scored),
                }
            )
        db.conn.commit()
        return results
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _validate_plan(plan_id: str) -> list[dict[str, object]]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, scheduled_for, theme, status, draft_text, metadata_json
            FROM contentplanitems
            WHERE plan_id = %s
            ORDER BY scheduled_for, id
            """,
            (plan_id,),
        )
        results: list[dict[str, object]] = []
        for row in cursor.fetchall() or []:
            metadata = row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}")
            generation = metadata.get("content_generation_v2") or {}
            brief = metadata.get("content_brief_v1") or {}
            selected_id = str(generation.get("selected_variant_id") or "")
            selected = next(
                (
                    variant
                    for variant in generation.get("variants") or []
                    if str(variant.get("id") or "") == selected_id
                ),
                {},
            )
            result = {
                "id": str(row[0]),
                "scheduled_for": str(row[1]),
                "theme": str(row[2]),
                "status": str(row[3]),
                "draft_length": len(str(row[4] or "")),
                "generation_source": str(metadata.get("generation_source") or ""),
                "brief_complete": bool(brief.get("complete")),
                "voice_profile_version": int(generation.get("voice_profile_version") or 0),
                "selected_score": int(selected.get("score") or 0),
                "quality_passed": bool(selected.get("quality_passed")),
                "issues": selected.get("issues") or [],
                "source": next(
                    (
                        source.get("fact")
                        for source in brief.get("sources") or []
                        if source.get("id") == "owner_source"
                    ),
                    "",
                ),
            }
            results.append(result)
        if len(results) != len(ITEMS):
            raise RuntimeError(f"Plan contains {len(results)} items instead of {len(ITEMS)}")
        failures = [
            item
            for item in results
            if item["status"] != "draft_generated"
            or item["generation_source"] != "editorial_grounded"
            or not item["brief_complete"]
            or not item["quality_passed"]
            or item["selected_score"] < 70
            or item["issues"]
            or not item["source"]
        ]
        if failures:
            raise RuntimeError("Quality validation failed: " + json.dumps(failures, ensure_ascii=False))
        return results
    finally:
        db.close()


def _archive_old_plan() -> None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            "UPDATE contentplans SET plan_status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (OLD_PLAN_ID,),
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _delete_failed_plan(plan_id: str) -> None:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("DELETE FROM contentplans WHERE id = %s", (plan_id,))
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    plan = create_generated_content_plan(
        OWNER_ID,
        BUSINESS_ID,
        scope_type="single_business",
        scope_target_id=BUSINESS_ID,
        period_days=30,
        density="light",
        content_mix={
            "services": True,
            "seo": False,
            "sales": False,
            "audit": False,
            "seasonal": False,
            "templates": True,
            "channels": CHANNELS,
        },
    )
    plan_id = str(plan.get("id") or "")
    if not plan_id:
        raise RuntimeError("Generated plan id is missing")
    try:
        item_ids = _configure_plan(plan_id)
        generation_results = _generate_editorial_drafts(plan_id, item_ids)
        validation = _validate_plan(plan_id)
        _archive_old_plan()
        print(
            json.dumps(
                {
                    "success": True,
                    "plan_id": plan_id,
                    "old_plan_archived": OLD_PLAN_ID,
                    "items": validation,
                    "generation_results": generation_results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
    except Exception:
        _delete_failed_plan(plan_id)
        raise


if __name__ == "__main__":
    main()
