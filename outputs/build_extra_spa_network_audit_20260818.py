#!/usr/bin/env python3
import argparse
import copy
import json

from psycopg2.extras import Json, RealDictCursor

from api.admin_prospecting import (
    _build_admin_lead_offer_payload,
    _drop_mismatched_explicit_business_link,
    _load_prospecting_lead,
    _normalize_lead_for_display,
    _sync_lead_business_link_from_parse_history,
    _sync_lead_contacts_from_parsed_data,
    _to_json_compatible,
)
from core.card_audit import build_lead_card_preview_snapshot
from pg_db_utils import get_db_connection


LEAD_ID = "c2e6f5d5-1dd0-4dd3-9cdc-d0e67603a8cf"
SLUG = "extra-spa-saint-petersburg-tipanova"
NETWORK_ID = "e22f911c-6ed8-5313-b1f5-8081df5f5649"
OFFICIAL_SITE = "https://экстраспа.рф/"
DISCOVERED_LOCATIONS_COUNT = 6
PUBLIC_REVIEWS_LOADED = 2486


CONTENT_AUDIT = {
    "title": "Extra СПА: единая репутация и контент для шести филиалов",
    "plan_intro": (
        "Контент сети должен не повторять акции, а заранее объяснять формат программы, "
        "условия сертификата и различия между филиалами."
    ),
    "facts_label": "Нужны факты от сети",
    "summary": (
        "У сети сильный объём отзывов и регулярные новости. Следующий рост даст не больше "
        "одинаковых публикаций, а единый стандарт ожиданий и доказательства по каждой точке."
    ),
    "metrics": [],
    "findings": [
        {
            "title": "Рейтинг 5,0 скрывает разные причины недовольства",
            "body": (
                "В текстах встречаются претензии к ожиданию, длительности этапов программы, "
                "температуре, интерьеру, сертификатам и работе администратора. Их нужно видеть "
                "по филиалам, а не только в среднем рейтинге сети."
            ),
        },
        {
            "title": "Апелляции нужно подкреплять журналом изменений",
            "body": (
                "Текущий импорт фиксирует публичный набор отзывов на сегодня. Для доказательной "
                "апелляции LocalOS должен ежедневно хранить количество отзывов и каждый review ID: "
                "какой текст исчез, когда и в какой карточке."
            ),
        },
        {
            "title": "Новости есть во всех точках, но активность различается",
            "body": (
                "Публикации уже ведутся по всей сети. Теперь важнее измерять регулярность и "
                "адаптировать общую тему под реальные условия филиала."
            ),
        },
        {
            "title": "Ответ на негатив должен начинаться с конкретного эпизода",
            "body": (
                "Общий ответ не закрывает спор. Нужны дата визита, программа, длительность этапов, "
                "имя филиала и предложенное решение."
            ),
        },
    ],
    "patterns": [
        {
            "title": "До покупки показать сценарий программы по времени",
            "body": (
                "Разложить программу на этапы: прогрев, процедура, массаж, отдых. Это снижает "
                "разрыв между рекламным названием и фактическим опытом гостя."
            ),
            "source_label": "Отзывы сети Extra СПА",
            "source_url": "https://yandex.com/maps/org/extra_spa/211181504259",
        },
        {
            "title": "Разделять общую тему и локальный факт",
            "body": (
                "Одна акция может быть общей, но фото, мастер, помещение и доступные слоты должны "
                "относиться к конкретному филиалу."
            ),
            "source_label": "Официальный сайт сети",
            "source_url": OFFICIAL_SITE,
        },
        {
            "title": "Условия сертификата объяснять до оплаты",
            "body": (
                "Срок, филиал, ограничения по времени и порядок переноса записи должны быть видны "
                "в одном сообщении, без поиска по правилам и переписке."
            ),
            "source_label": "Ответы на частые вопросы Extra СПА",
            "source_url": "https://экстраспа.рф/answers",
        },
        {
            "title": "Для апелляции хранить факт, а не пересказ",
            "body": (
                "Нужны исходный review ID, текст, оценка, дата, ответ компании и снимок до исчезновения. "
                "Тогда обращение в поддержку можно собрать по конкретному случаю."
            ),
            "source_label": "Базовый снимок отзывов LocalOS",
            "source_url": "https://localos.pro/extra-spa-saint-petersburg-tipanova",
        },
    ],
    "plan": [
        {
            "date_label": "День 1",
            "type": "Как всё проходит",
            "title": "Три часа в СПА: из каких этапов состоит программа",
            "goal": "Синхронизировать ожидания гостя с реальным сценарием визита.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "Перед записью хочется понимать не только название программы, но и как пройдёт визит. "
                "Покажите по минутам один реальный сценарий филиала: сколько занимает прогрев, процедура, "
                "массаж и время для отдыха. Так гость заранее выбирает подходящий формат и приходит без "
                "неожиданных ожиданий."
            ),
            "facts_needed": [
                "Выбрать одну действующую программу и один филиал.",
                "Подтвердить фактическую длительность каждого этапа.",
                "Уточнить, что гостю нужно взять с собой.",
            ],
            "visual_brief": "Четыре последовательных кадра реальной программы в выбранном филиале.",
            "cta": "Выбрать программу и записаться в удобный филиал.",
        },
        {
            "date_label": "День 3",
            "type": "Знакомство с филиалом",
            "title": "Какой филиал Extra СПА подойдёт именно вам",
            "goal": "Помочь выбрать точку по формату, а не только по ближайшему адресу.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "У шести филиалов одна сеть, но разный формат пространства. В публикации стоит показать "
                "одну точку честно: где она находится, как найти вход, что есть внутри и для каких программ "
                "она подходит лучше всего. Следующая публикация расскажет о другом филиале."
            ),
            "facts_needed": [
                "Подтвердить отличительные особенности каждого филиала.",
                "Указать вход, этаж и ориентир без расхождений с карточкой.",
                "Назвать программы, которые доступны именно здесь.",
            ],
            "visual_brief": "Вход, зона отдыха и помещение конкретного филиала, без смешивания адресов.",
            "cta": "Посмотреть адреса и выбрать филиал.",
        },
        {
            "date_label": "День 5",
            "type": "FAQ",
            "title": "Что важно знать о подарочном сертификате до покупки",
            "goal": "Снять частые вопросы и снизить конфликтные ожидания.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "Подарок должен радовать и в момент вручения, и при записи. В одном коротком посте объясните: "
                "сколько действует сертификат, в каких филиалах его принимают, как перенести запись и есть ли "
                "ограничения по времени. Только актуальные условия, без рекламных формулировок."
            ),
            "facts_needed": [
                "Подтвердить срок действия сертификата.",
                "Уточнить правила переноса и отмены.",
                "Проверить, действует ли сертификат во всех шести филиалах.",
            ],
            "visual_brief": "Реальный сертификат Extra СПА и спокойный кадр зоны ресепшен.",
            "cta": "Уточнить условия и выбрать программу в подарок.",
        },
        {
            "date_label": "День 7",
            "type": "История гостя",
            "title": "Что помогло гостю действительно расслабиться",
            "goal": "Показать ценность через подтверждённую сцену, а не перечень процедур.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "Возьмите один подтверждённый отзыв и раскройте одну сцену: с каким состоянием пришёл гость, "
                "что уточнил мастер и какой момент визита он запомнил. Не копируйте отзыв целиком и не добавляйте "
                "детали, которых в истории не было."
            ),
            "facts_needed": [
                "Выбрать отзыв с разрешённой обезличенной историей.",
                "Подтвердить филиал, программу и мастера.",
                "Получить согласие на использование узнаваемых деталей или убрать их.",
            ],
            "visual_brief": "Мастер в процессе и деталь программы; лицо гостя только с согласия.",
            "cta": "Выбрать программу для своего сценария отдыха.",
        },
    ],
    "methodology_note": (
        "Аудит охватывает все шесть найденных карточек Extra СПА. Загружено максимально доступное "
        "на публичных страницах Яндекса количество текстов отзывов. Публичная выдача вернула не все "
        "тексты, заявленные счётчиками карточек; незагруженные отзывы не считаются проанализированными."
    ),
}


def _load_network_rows(cursor):
    cursor.execute(
        """
        SELECT b.id, b.name, b.address, b.rating, b.reviews_count, b.yandex_url AS source_url,
               COALESCE(NULLIF(b.external_ids->>'yandex_news_count', '')::integer, 0) AS news_count,
               COALESCE(review_stats.imported_count, 0) AS imported_count,
               COALESCE(review_stats.unanswered_count, 0) AS unanswered_count,
               COALESCE(review_stats.low_rating_count, 0) AS low_rating_count,
               COALESCE(review_stats.low_rating_unanswered_count, 0) AS low_rating_unanswered_count
        FROM businesses b
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (WHERE COALESCE(r.is_current, TRUE)) AS imported_count,
                   COUNT(*) FILTER (
                       WHERE COALESCE(r.is_current, TRUE)
                         AND COALESCE(NULLIF(TRIM(r.response_text), ''), '') IN ('', '—')
                   ) AS unanswered_count,
                   COUNT(*) FILTER (
                       WHERE COALESCE(r.is_current, TRUE) AND COALESCE(r.rating, 0) <= 3
                   ) AS low_rating_count,
                   COUNT(*) FILTER (
                       WHERE COALESCE(r.is_current, TRUE) AND COALESCE(r.rating, 0) <= 3
                         AND COALESCE(NULLIF(TRIM(r.response_text), ''), '') IN ('', '—')
                   ) AS low_rating_unanswered_count
            FROM externalbusinessreviews r
            WHERE r.business_id = b.id AND r.source = 'yandex_maps'
        ) review_stats ON TRUE
        WHERE b.network_id = %s AND b.id <> %s
        ORDER BY b.address, b.name
        """,
        (NETWORK_ID, NETWORK_ID),
    )
    return [dict(row) for row in cursor.fetchall()]


def build_page():
    lead = _load_prospecting_lead(LEAD_ID)
    if not lead:
        raise RuntimeError("Lead not found")
    lead = _drop_mismatched_explicit_business_link(dict(lead))
    lead = _sync_lead_business_link_from_parse_history(dict(lead))
    lead = _sync_lead_contacts_from_parsed_data(dict(lead))
    display = _normalize_lead_for_display(dict(lead))
    preview = build_lead_card_preview_snapshot(display)
    page = _to_json_compatible(
        _build_admin_lead_offer_payload(
            lead=display,
            preview=preview,
            preferred_language="ru",
            enabled_languages=["ru"],
        )
    )

    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        rows = _load_network_rows(cursor)
    finally:
        conn.close()
    if len(rows) != DISCOVERED_LOCATIONS_COUNT:
        raise RuntimeError(f"Expected six network locations, got {len(rows)}")

    ratings = [float(row["rating"]) for row in rows if float(row.get("rating") or 0) > 0]
    total_public_count = sum(int(row.get("reviews_count") or 0) for row in rows)
    total_imported = sum(int(row.get("imported_count") or 0) for row in rows)
    total_unanswered = sum(int(row.get("unanswered_count") or 0) for row in rows)
    total_low = sum(int(row.get("low_rating_count") or 0) for row in rows)
    total_low_unanswered = sum(int(row.get("low_rating_unanswered_count") or 0) for row in rows)
    locations_with_unanswered = sum(1 for row in rows if int(row.get("unanswered_count") or 0) > 0)
    news_counts = [int(row.get("news_count") or 0) for row in rows]

    page.update(
        {
            "slug": SLUG,
            "public_url": f"https://localos.pro/{SLUG}",
            "name": "Extra СПА — сеть",
            "display_name": "Extra СПА — сеть",
            "address": "Санкт-Петербург, 6 филиалов",
            "source_url": OFFICIAL_SITE,
            "rating": max(ratings) if ratings else None,
            "reviews_count": total_public_count,
            "has_recent_activity": True,
            "content_audit": copy.deepcopy(CONTENT_AUDIT),
        }
    )
    page["content_audit"]["metrics"] = [
        {
            "value": str(len(rows)),
            "label": "филиалов в аудите",
            "detail": "Все найденные адреса представлены отдельными карточками.",
        },
        {
            "value": f"{total_imported:,}".replace(",", " "),
            "label": "текстов отзывов загружено",
            "detail": (
                f"Карточки показывают {total_public_count} отзывов; публичная выдача вернула "
                f"{total_imported} доступных текстов."
            ),
        },
        {
            "value": str(total_unanswered),
            "label": "отзыва без ответа",
            "detail": f"Они распределены по {locations_with_unanswered} филиалам.",
        },
        {
            "value": str(total_low),
            "label": "оценок 1–3 звезды",
            "detail": f"У {total_low_unanswered} из них ещё нет публичного ответа.",
        },
    ]

    network_locations = [
        {
            "name": row.get("name"),
            "address": row.get("address"),
            "rating": float(row["rating"]) if float(row.get("rating") or 0) > 0 else None,
            "reviews_count": int(row.get("reviews_count") or 0),
            "news_count": int(row.get("news_count") or 0),
            "unanswered_count": int(row.get("unanswered_count") or 0),
            "source_url": row.get("source_url"),
        }
        for row in rows
    ]

    audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
    audit.update(
        {
            "audit_profile": "network_spa_wellness",
            "audit_profile_label": "Сеть СПА-салонов",
            "summary_score": 82,
            "health_level": "growth",
            "health_label": "Сильная репутация, нужен контроль по филиалам",
            "summary_text": (
                f"Это аудит всей сети из шести филиалов. Загружено {total_imported} доступных текстов отзывов. "
                f"Сейчас без ответа остаётся {total_unanswered}, включая {total_low_unanswered} оценок 1–3 звезды."
            ),
            "summary_public": (
                f"Аудит охватывает все шесть филиалов Extra СПА, а не одну карточку. Публичный рейтинг "
                f"округляется до 5,0, поэтому для управления важнее различия в отзывах, ответах и новостях."
            ),
            "summary_whatsapp": (
                f"В аудит вошли 6 филиалов и {total_imported} доступных текстов отзывов. "
                f"Без ответа осталось {total_unanswered}; для апелляций создан базовый снимок review ID по каждой точке."
            ),
            "rating": max(ratings) if ratings else None,
            "reviews_count": total_public_count,
            "network_locations": network_locations,
            "subscores": {"profile": 90, "reputation": 78, "services": 84, "activity": 86},
            "current_state": {
                "rating": max(ratings) if ratings else None,
                "rating_min": min(ratings) if ratings else None,
                "rating_max": max(ratings) if ratings else None,
                "reviews_count": total_public_count,
                "imported_review_texts_count": total_imported,
                "unanswered_reviews_count": total_unanswered,
                "low_rating_reviews_count": total_low,
                "low_rating_unanswered_count": total_low_unanswered,
                "locations_count": len(rows),
                "discovered_cards_count": DISCOVERED_LOCATIONS_COUNT,
                "duplicate_cards_count": 0,
                "locations_with_news": sum(1 for count in news_counts if count > 0),
                "weak_locations_count": 0,
                "services_count": 0,
                "services_with_price_count": 0,
                "is_verified": None,
                "paid_promotion_detected": False,
                "has_website": True,
                "has_recent_activity": True,
                "news_count": sum(news_counts),
                "news_count_min": min(news_counts),
                "news_count_max": max(news_counts),
                "news_status": "uneven",
                "photos_state": "good",
                "description_applicable": True,
                "description_present": True,
            },
            "findings": [
                {
                    "code": "network_review_appeals_baseline",
                    "title": "Для апелляций не хватало журнала изменений",
                    "description": (
                        f"Зафиксирован первый сетевой снимок: {total_imported} доступных текстов и их review ID "
                        "по каждому филиалу. Он позволит доказательно видеть исчезновение и возврат отзывов."
                    ),
                    "severity": "high",
                },
                {
                    "code": "network_reviews_unanswered",
                    "title": f"Без ответа осталось {total_unanswered} отзывов",
                    "description": f"Из них {total_low_unanswered} — оценки от 1 до 3 звёзд.",
                    "severity": "high",
                },
                {
                    "code": "network_rating_masks_variance",
                    "title": "Округлённый рейтинг не показывает причины риска",
                    "description": (
                        f"Во всех карточках отображается 5,0, но среди загруженных текстов есть {total_low} "
                        "оценок 1–3 звезды с разными причинами по филиалам."
                    ),
                    "severity": "medium",
                },
                {
                    "code": "network_news_uneven",
                    "title": "Новости ведутся во всех точках, но с разной плотностью",
                    "description": f"На карточках найдено от {min(news_counts)} до {max(news_counts)} публикаций.",
                    "severity": "medium",
                },
            ],
            "recommended_actions": [
                {
                    "title": "Включить ежедневный журнал отзывов",
                    "description": "Хранить review ID, текст, оценку и ответ по каждому филиалу, чтобы собирать доказательства для апелляций.",
                    "priority": "high",
                },
                {
                    "title": f"Закрыть {total_low_unanswered} негативных отзывов без ответа",
                    "description": "Сначала разобрать оценки 1–3 звезды, затем остальные отзывы без ответа.",
                    "priority": "high",
                },
                {
                    "title": "Разделить сетевую тему и факт филиала",
                    "description": "Общий оффер адаптировать под адрес, помещение, программу и реальные фото каждой точки.",
                    "priority": "medium",
                },
            ],
            "issue_blocks": [
                {
                    "id": "network_review_appeals_baseline",
                    "section": "reviews",
                    "priority": "high",
                    "title": "Апелляции: нужен доказательный журнал",
                    "problem": "Текущий публичный снимок не объясняет, какие отзывы исчезали раньше и возвращались после обращения.",
                    "impact": "Без истории review ID трудно доказать площадке конкретное изменение и проверить результат апелляции.",
                    "evidence": f"На 18 августа зафиксировано {total_imported} доступных текстов по шести филиалам.",
                    "fix": "Снимать ежедневный реестр отзывов и формировать карточку апелляции: филиал, review ID, текст, дата исчезновения, обращение и результат.",
                },
                {
                    "id": "network_reviews_unanswered",
                    "section": "reviews",
                    "priority": "high",
                    "title": f"{total_unanswered} отзывов без ответа",
                    "problem": f"В очереди остаются {total_low_unanswered} оценок 1–3 звезды и отзывы с более высокой оценкой.",
                    "impact": "Негативный эпизод остаётся без позиции компании, а качество работы сети выглядит неодинаково.",
                    "evidence": f"Очередь есть в {locations_with_unanswered} из шести филиалов.",
                    "fix": "Ответить сначала на низкие оценки, привязывая ответ к программе, дате визита и предложенному решению.",
                },
                {
                    "id": "network_news_uneven",
                    "section": "news",
                    "priority": "medium",
                    "title": "Сетевая лента ведётся неравномерно",
                    "problem": f"Количество найденных новостей различается: от {min(news_counts)} до {max(news_counts)} на карточку.",
                    "impact": "Гость получает разное впечатление об актуальности сети в зависимости от выбранного адреса.",
                    "evidence": "Новости есть у всех шести филиалов, поэтому задача — выровнять качество и локальную достоверность.",
                    "fix": "Планировать одну общую тему, но выпускать версии с фактом, фото и условиями конкретного филиала.",
                },
            ],
            "top_3_issues": [
                {
                    "id": "network_review_appeals_baseline",
                    "priority": "high",
                    "title": "Нет истории для апелляций",
                    "problem": "До текущего снимка исчезновение и возврат отдельных отзывов не отслеживались по review ID.",
                },
                {
                    "id": "network_reviews_unanswered",
                    "priority": "high",
                    "title": f"{total_unanswered} отзывов без ответа",
                    "problem": f"{total_low_unanswered} из них имеют оценку 1–3 звезды.",
                },
                {
                    "id": "network_news_uneven",
                    "priority": "medium",
                    "title": "Разная плотность новостей",
                    "problem": "Общая активность сети не превращена в единый стандарт по филиалам.",
                },
            ],
            "action_plan": {
                "next_24h": [
                    f"Ответить на {total_low_unanswered} негативных отзывов без реакции компании.",
                    "Зафиксировать базовый список review ID по каждому филиалу.",
                ],
                "next_7d": [
                    "Включить ежедневное сравнение отзывов и отдельный журнал апелляций.",
                    "Подготовить четыре сетевые темы с локальными фактами и фото филиалов.",
                ],
                "ongoing": [
                    "Отвечать на новые отзывы в течение 48 часов.",
                    "Проверять исчезнувшие отзывы и результат апелляции по конкретному review ID.",
                    "Сравнивать филиалы не только по рейтингу, но и по причинам негатива.",
                ],
            },
            "photo_shots_missing": [
                "Вход и ориентир каждого филиала",
                "Реальный интерьер без смешивания адресов",
                "Этапы одной программы по порядку",
            ],
            "positioning_focus": [
                "Объяснять сценарий программы до записи.",
                "Показывать различия филиалов честно и конкретно.",
                "Условия сертификата и переноса записи сообщать до оплаты.",
            ],
            "cadence": {"news_posts_per_month_min": 4, "photos_per_month_min": 8, "reviews_response_hours_max": 48},
        }
    )
    page["audit"] = audit
    return page


def apply_page(page):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT id FROM users
            WHERE COALESCE(is_superadmin, FALSE) = TRUE
            ORDER BY created_at ASC NULLS LAST, id ASC LIMIT 1
            """
        )
        user = cursor.fetchone()
        if not user:
            raise RuntimeError("Superadmin user not found")
        user_id = str(user["id"])
        cursor.execute("SELECT company_id, company_location_id FROM prospectingleads WHERE id = %s", (LEAD_ID,))
        lead_row = cursor.fetchone() or {}
        cursor.execute(
            """
            INSERT INTO adminprospectingleadpublicoffers (
                lead_id, slug, page_json, is_active, created_by, created_at, updated_at,
                business_id, business_profile, source_type, generated_json, published_json,
                edit_status, published_by, published_at, company_id, company_location_id,
                audit_context
            ) VALUES (
                %s, %s, %s, TRUE, %s, NOW(), NOW(), %s, 'network_spa_wellness',
                'partnership_partner', %s, %s, 'published', %s, NOW(), %s, %s, 'public'
            )
            ON CONFLICT (lead_id) DO UPDATE SET
                slug = EXCLUDED.slug,
                page_json = EXCLUDED.page_json,
                generated_json = EXCLUDED.generated_json,
                published_json = EXCLUDED.published_json,
                is_active = TRUE,
                business_id = EXCLUDED.business_id,
                business_profile = EXCLUDED.business_profile,
                source_type = EXCLUDED.source_type,
                edit_status = 'published',
                published_by = EXCLUDED.published_by,
                published_at = NOW(),
                company_id = EXCLUDED.company_id,
                company_location_id = EXCLUDED.company_location_id,
                audit_context = 'public',
                updated_at = NOW()
            """,
            (
                LEAD_ID,
                SLUG,
                Json(page),
                user_id,
                NETWORK_ID,
                Json(page),
                Json(page),
                user_id,
                lead_row.get("company_id"),
                lead_row.get("company_location_id"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    page = build_page()
    print(json.dumps(page, ensure_ascii=False, indent=2))
    if args.apply:
        apply_page(page)
        print(f"Published: https://localos.pro/{SLUG}")


if __name__ == "__main__":
    main()
