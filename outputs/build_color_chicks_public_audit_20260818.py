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


LEAD_ID = "f4021ec4-3c3e-4cb1-b88e-3812a8e2623c"
SLUG = "raznotsvetnye-tsyplyata-sankt-peterburg-balkanskaya"
NETWORK_ID = "e4a9da71-d9fe-5500-8c2a-0053de0fb3cd"
DISCOVERED_CARDS_COUNT = 21
DUPLICATE_CARDS_COUNT = 1
CHAIN_URL = "https://yandex.com/maps/2/saint-petersburg/chain/raznocvetnye_cypljata/82325561646/"


CONTENT_AUDIT = {
    "title": "Разноцветные цыплята: единая контент-система для сети",
    "plan_intro": (
        "Четыре разные задачи: история результата, процесс занятия, диагностика "
        "и практический вопрос об оплате."
    ),
    "facts_label": "Нужны факты от центра",
    "summary": "Сеть нужно вести как единый контентный контур: общие редакционные темы дополняются фактами, специалистами и результатами конкретного филиала.",
    "metrics": [
        {
            "value": "50",
            "label": "отзывов изучено",
            "detail": "Это актуальный срез отзывов, загруженный в LocalOS.",
        },
        {
            "value": "37 из 50",
            "label": "говорят о результате",
            "detail": "Родители пишут о речи, звуках, словарном запасе и пересказе.",
        },
        {
            "value": "25 из 50",
            "label": "ребёнок идёт с удовольствием",
            "detail": "Игровой формат и контакт со специалистом повторяются в отзывах.",
        },
        {
            "value": "49 из 50",
            "label": "получили ответ",
            "detail": "Один отзыв в загруженном срезе остаётся без ответа.",
        },
    ],
    "findings": [
        {
            "title": "Доказательства уже есть в отзывах",
            "body": (
                "Родители называют сроки и изменения: появились предложения, речь стала "
                "понятнее, поставлены звуки, ребёнок научился пересказывать. Это сильнее "
                "общих обещаний о пользе занятий."
            ),
        },
        {
            "title": "Один результат - одна публикация",
            "body": (
                "Не нужно перечислять все услуги центра. Один пост показывает одну исходную "
                "трудность, действие специалиста и наблюдаемое изменение."
            ),
        },
        {
            "title": "Называть механизм, а не только итог",
            "body": (
                "Фраза «ребёнок стал лучше говорить» убедительнее, когда рядом есть конкретика: "
                "игровая форма, разнообразные домашние задания, план по этапам или работа над "
                "слоговой структурой."
            ),
        },
        {
            "title": "После поста нужен один понятный шаг",
            "body": (
                "Для Яндекс Карт лучше предлагать запись на диагностику или уточнение условий. "
                "Просьба оставить комментарий не помогает родителю перейти к знакомству с центром."
            ),
        },
    ],
    "patterns": [
        {
            "title": "Показать путь ребёнка по этапам",
            "body": (
                "Начать с исходной ситуации, назвать, над чем работали, и завершить тем, "
                "что изменилось. Персональные данные ребёнка не нужны."
            ),
            "source_label": "Отзывы сети на Яндекс Картах",
            "source_url": "https://yandex.com/maps/org/raznotsvetnyye_tsyplyata/1315866281",
        },
        {
            "title": "Объяснить диагностику через результат для родителя",
            "body": (
                "Вместо перечня методик показать, что семья узнаёт после встречи: причины "
                "трудности, маршрут занятий и ближайшую цель."
            ),
            "source_label": "Описание диагностики на сайте",
            "source_url": "https://color-chicks.ru/spb",
        },
        {
            "title": "Подкрепить рассказ конкретным материалом",
            "body": (
                "Фото упражнения, карточек или логопедического зеркала объясняет работу "
                "лучше, чем случайный портрет ребёнка."
            ),
            "source_label": "Пример: #АйДаКодить",
            "source_url": "https://yandex.com/maps/org/aydakodit/43884878561",
        },
        {
            "title": "Оставить в тексте одну перемену",
            "body": (
                "Звук, предложение, пересказ или готовность идти на занятие - один результат "
                "становится центром публикации, остальные преимущества не отвлекают."
            ),
            "source_label": "Пример: Центр «Каскад»",
            "source_url": "https://yandex.com/maps/org/tsentr_detskogo_dosuga_kaskad/1164443906",
        },
    ],
    "plan": [
        {
            "date_label": "20 августа",
            "type": "История результата",
            "title": "От отдельных слов к предложениям: что изменилось за три месяца",
            "goal": "Показать результат занятий на подтверждённом примере из отзыва.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "В 2 года 8 месяцев у ребёнка почти не было речи, а слова давались с трудом. "
                "После трёх месяцев занятий он начал говорить предложениями. Позже семья "
                "вернулась, чтобы сделать речь понятнее и поставить звуки. За полтора месяца "
                "произношение заметно улучшилось. Специалист Мария нашла подход и мотивацию, "
                "поэтому ребёнок идёт на занятия с удовольствием."
            ),
            "facts_needed": [
                "Подтвердить, что историю можно публиковать в обезличенном виде.",
                "Уточнить филиал, к которому относится история, и получить согласие на обезличенную публикацию.",
                "Выбрать одно изменение для заголовка: предложения или более понятная речь.",
            ],
            "visual_brief": (
                "Материал с занятия, карточки или упражнение на слоговую структуру. "
                "Не использовать узнаваемое фото ребёнка без согласия семьи."
            ),
            "cta": "Записаться на диагностику и обсудить речевую ситуацию ребёнка.",
        },
        {
            "date_label": "22 августа",
            "type": "Как проходят занятия",
            "title": "Почему ребёнок ждёт следующего занятия",
            "goal": "Показать игровой формат и контакт со специалистом через реальную сцену.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "В отзывах родители часто пишут: ребёнок идёт на занятие с удовольствием, "
                "а иногда не хочет уходить. Это не случайность. Специалист подбирает задания "
                "под интересы ребёнка, меняет упражнения и сохраняет понятную цель каждого этапа. "
                "Так работа над речью остаётся серьёзной, но не превращается для ребёнка в испытание."
            ),
            "facts_needed": [
                "Один свежий пример игры или упражнения в филиале Купчино.",
                "Комментарий специалиста: какой навык отрабатывает это упражнение.",
                "Возраст, для которого подходит выбранный пример.",
            ],
            "visual_brief": (
                "Руки ребёнка и специалиста в процессе упражнения, без постановочной улыбки "
                "в камеру. В кадре должен читаться материал занятия."
            ),
            "cta": "Узнать, как проходит первое занятие в центре.",
        },
        {
            "date_label": "25 августа",
            "type": "Ответ родителю",
            "title": "Что родитель узнаёт после диагностики логопеда-дефектолога",
            "goal": "Снять неопределённость перед первым визитом.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "Диагностика нужна не для общего ответа «заниматься или подождать». За встречу "
                "специалист уточняет запрос семьи, смотрит речь и связанные навыки, а затем "
                "объясняет, над чем работать в первую очередь. Родитель уходит с понятным маршрутом: "
                "ближайшая цель, формат занятий и признаки, по которым можно отслеживать изменения."
            ),
            "facts_needed": [
                "Точная длительность диагностики в филиале Купчино.",
                "Что входит в заключение и выдаётся ли оно письменно.",
                "Актуальная стоимость и способ записи.",
            ],
            "visual_brief": (
                "Подготовленный стол специалиста: материалы, зеркало, карточки или бланк маршрута. "
                "Личные данные ребёнка в кадр не должны попасть."
            ),
            "cta": "Выбрать ближайший филиал и записаться на диагностику.",
        },
        {
            "date_label": "27 августа",
            "type": "Практический вопрос",
            "title": "Можно ли оплатить занятия материнским капиталом?",
            "goal": "Ответить на частый вопрос и убрать барьер перед записью.",
            "platforms": ["Яндекс Карты", "VK", "Telegram"],
            "draft": (
                "Занятия в «Разноцветных цыплятах» можно оплачивать средствами материнского "
                "капитала - родители отдельно отмечают это в отзывах. Перед оформлением центр "
                "уточнит программу, график и подготовит необходимые документы. Чтобы понять "
                "порядок действий для вашей ситуации, сначала свяжитесь с администратором филиала."
            ),
            "facts_needed": [
                "Подтвердить актуальные условия оплаты материнским капиталом.",
                "Список документов и примерный срок оформления.",
                "Уточнить возможность налогового вычета и действующие ограничения.",
            ],
            "visual_brief": (
                "Администратор за стойкой или аккуратный набор документов без персональных данных. "
                "Не использовать изображение сертификата из интернета."
            ),
            "cta": "Уточнить условия у администратора выбранного филиала.",
        },
    ],
    "methodology_note": "Аудит охватывает сетевой объект Яндекса и уникальные карточки филиалов. Примеры других организаций используются только как редакционные ориентиры, а не как факты о сети.",
}


def build_page() -> dict:
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
    page.update(
        {
            "slug": SLUG,
            "public_url": f"https://localos.pro/{SLUG}",
            "rating": 5.0,
            "reviews_count": 116,
            "has_recent_activity": False,
            "content_audit": copy.deepcopy(CONTENT_AUDIT),
        }
    )

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT b.name, b.address, b.rating, b.reviews_count, b.yandex_url AS source_url,
                   COALESCE(NULLIF(b.external_ids->>'yandex_news_count', '')::integer, 0) AS news_count,
                   COALESCE(reviews.unanswered_count, 0) AS unanswered_count
            FROM businesses b
            LEFT JOIN LATERAL (
                SELECT COUNT(*) FILTER (
                    WHERE COALESCE(NULLIF(TRIM(r.response_text), ''), '') IN ('', '—')
                      AND COALESCE(r.is_current, TRUE) IS TRUE
                ) AS unanswered_count
                FROM externalbusinessreviews r
                WHERE r.business_id = b.id
            ) reviews ON TRUE
            WHERE b.network_id = %s AND b.id <> %s
            ORDER BY b.address, b.name
            """,
            (NETWORK_ID, NETWORK_ID),
        )
        network_rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    ratings = [float(row["rating"]) for row in network_rows if float(row.get("rating") or 0) > 0]
    total_unanswered = sum(int(row.get("unanswered_count") or 0) for row in network_rows)
    locations_with_news = sum(1 for row in network_rows if int(row.get("news_count") or 0) > 0)
    locations_without_news = len(network_rows) - locations_with_news
    locations_with_unanswered = sum(1 for row in network_rows if int(row.get("unanswered_count") or 0) > 0)
    total_reviews = sum(int(row.get("reviews_count") or 0) for row in network_rows)

    page.update(
        {
            "name": "Разноцветные цыплята — сеть",
            "display_name": "Разноцветные цыплята — сеть",
            "address": "Санкт-Петербург и Ленинградская область",
            "source_url": CHAIN_URL,
            "rating": max(ratings) if ratings else None,
            "reviews_count": total_reviews,
        }
    )

    content_audit = page.get("content_audit") if isinstance(page.get("content_audit"), dict) else {}
    content_audit.update(
        {
            "summary": (
                f"В сетевом объекте Яндекса найдена {DISCOVERED_CARDS_COUNT} карточка. "
                f"Одна карточка Балканской площади дублируется и не имеет рейтинга, поэтому "
                f"в рабочий аудит включено {len(network_rows)} уникальных точек. У "
                f"{locations_without_news} точек нет новостей, а в {locations_with_unanswered} "
                f"точках есть отзывы без ответа. Контент нужно готовить централизованно, "
                f"но подтверждать фактами конкретного филиала."
            ),
            "metrics": [
                {
                    "value": str(DISCOVERED_CARDS_COUNT),
                    "label": "карточка найдена",
                    "detail": f"{len(network_rows)} уникальных точек и один дубль Балканской площади без рейтинга.",
                },
                {
                    "value": str(locations_without_news),
                    "label": "точек без новостей",
                    "detail": "Эти филиалы не используют публикации для поисковой видимости и доверия.",
                },
                {
                    "value": str(total_unanswered),
                    "label": "отзывов без ответа",
                    "detail": f"Они распределены по {locations_with_unanswered} филиалам сети.",
                },
                {
                    "value": f"{min(ratings):.1f}–{max(ratings):.1f}" if ratings else "—",
                    "label": "диапазон рейтингов",
                    "detail": "Точка без рейтинга не участвует в расчёте диапазона.",
                },
            ],
            "methodology_note": (
                f"Аудит построен по сетевому объекту Яндекса: найдено {DISCOVERED_CARDS_COUNT} карточек, "
                f"после удаления одного дубля Балканской площади анализируется {len(network_rows)} "
                f"уникальных точек и {total_reviews} отзывов."
            ),
        }
    )
    page["content_audit"] = content_audit

    audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
    audit.update(
        {
            "audit_profile": "network_children_education",
            "audit_profile_label": "Сеть детских развивающих центров",
            "summary_score": 78,
            "health_level": "growth",
            "health_label": "Сильная репутация, нужен контент",
            "summary_text": f"В сетевом объекте Яндекса найдена {DISCOVERED_CARDS_COUNT} карточка. Одна карточка Балканской площади является дублем без рейтинга; аудит охватывает {len(network_rows)} уникальных точек. У {locations_without_news} точек нет новостей, а у {locations_with_unanswered} есть отзывы без ответа.",
            "summary_public": f"Это аудит сети, а не одной точки: найдено {DISCOVERED_CARDS_COUNT} карточек, из них {len(network_rows)} уникальных. Один дубль Балканской площади без рейтинга исключён из сравнения. У {locations_without_news} точек нет новостей, у {locations_with_unanswered} есть отзывы без ответа.",
            "summary_whatsapp": (
                f"У сети «Разноцветные цыплята» {len(network_rows)} уникальных точек и {total_reviews} отзывов. "
                f"У {locations_without_news} филиалов нет новостей, а в {locations_with_unanswered} есть отзывы без ответа."
            ),
            "rating": max(ratings) if ratings else None,
            "reviews_count": total_reviews,
            "network_locations": [
                {
                    "name": row.get("name"),
                    "address": row.get("address"),
                    "rating": float(row["rating"]) if float(row.get("rating") or 0) > 0 else None,
                    "reviews_count": int(row.get("reviews_count") or 0),
                    "news_count": int(row.get("news_count") or 0),
                    "unanswered_count": int(row.get("unanswered_count") or 0),
                    "source_url": row.get("source_url"),
                }
                for row in network_rows
            ],
            "subscores": {"profile": 86, "reputation": 100, "services": 54, "activity": 42},
            "current_state": {
                "rating": max(ratings) if ratings else None,
                "rating_min": min(ratings) if ratings else None,
                "rating_max": max(ratings) if ratings else None,
                "reviews_count": total_reviews,
                "unanswered_reviews_count": total_unanswered,
                "locations_count": len(network_rows),
                "discovered_cards_count": DISCOVERED_CARDS_COUNT,
                "duplicate_cards_count": DUPLICATE_CARDS_COUNT,
                "locations_with_news": locations_with_news,
                "weak_locations_count": locations_without_news,
                "services_count": 0,
                "services_with_price_count": 0,
                "is_verified": None,
                "raw_is_verified": None,
                "paid_promotion_detected": False,
                "has_website": True,
                "has_recent_activity": False,
                "news_count": sum(int(row.get("news_count") or 0) for row in network_rows),
                "recent_news_count": 0,
                "old_news_count": 0,
                "latest_news_at": None,
                "news_status": "uneven",
                "photos_state": "good",
                "photos_count": len((preview.get("preview_meta") or {}).get("photo_urls") or []),
                "description_applicable": True,
                "description_present": True,
                "booking_offer_count": 0,
            },
            "findings": [
                {
                    "code": "education_children_news_missing",
                    "title": "Публикации ведутся не во всех филиалах",
                    "description": f"У {locations_without_news} из {len(network_rows)} уникальных точек нет новостей.",
                    "severity": "high",
                },
                {
                    "code": "network_duplicate_listing",
                    "title": "В сетевом объекте есть дубль",
                    "description": "Карточка Балканской площади представлена дважды; дубль не имеет рейтинга.",
                    "severity": "medium",
                },
                {
                    "code": "education_children_reviews_unanswered",
                    "title": "Отзывы без ответа распределены по сети",
                    "description": f"Без ответа осталось {total_unanswered} отзывов в {locations_with_unanswered} филиалах.",
                    "severity": "medium",
                },
            ],
            "recommended_actions": [
                {
                    "title": f"Запустить новости в {locations_without_news} точках",
                    "description": "Начать с общей сетевой темы и дополнить её локальным фото, специалистом или фактом филиала.",
                    "priority": "high",
                },
                {
                    "title": "Убрать дубль Балканской площади",
                    "description": "Проверить правообладателя карточек и закрыть либо объединить дублирующую карточку без рейтинга.",
                    "priority": "medium",
                },
                {
                    "title": f"Ответить на {total_unanswered} отзывов",
                    "description": "Сначала закрыть точки с тремя и двумя отзывами без ответа, затем остальные.",
                    "priority": "medium",
                },
            ],
            "issue_blocks": [
                {
                    "id": "education_children_news_missing",
                    "section": "news",
                    "priority": "high",
                    "title": f"{locations_without_news} точек не публикуют новости",
                    "problem": f"У {locations_without_news} из {len(network_rows)} уникальных филиалов нет публикаций.",
                    "impact": "Родитель видит менее живую карточку, а филиал теряет дополнительную поисковую видимость.",
                    "evidence": f"Новости есть у {locations_with_news} точек, отсутствуют у {locations_without_news}.",
                    "fix": "Дать этим филиалам первый месячный план и выпускать общую тему с локальными фактами и фотографиями.",
                },
                {
                    "id": "network_duplicate_listing",
                    "section": "profile",
                    "priority": "medium",
                    "title": "Балканская площадь представлена дважды",
                    "problem": "В сетевом объекте Яндекса есть дублирующая карточка без рейтинга.",
                    "impact": "Дубль размывает статистику сети и может путать родителей при выборе филиала.",
                    "evidence": f"Найдена {DISCOVERED_CARDS_COUNT} карточка, но уникальных действующих точек — {len(network_rows)}.",
                    "fix": "Проверить карточки Балканской площади и отправить в Яндекс запрос на объединение либо закрытие дубля.",
                },
                {
                    "id": "education_children_reviews_unanswered",
                    "section": "reviews",
                    "priority": "medium",
                    "title": f"В {locations_with_unanswered} филиалах есть отзывы без ответа",
                    "problem": f"Без публичной реакции осталось {total_unanswered} отзывов.",
                    "impact": "Качество коммуникации выглядит разным в зависимости от выбранного филиала.",
                    "evidence": f"Отзывы без ответа распределены по {locations_with_unanswered} точкам сети.",
                    "fix": "Закрыть текущую очередь и назначить единый срок ответа для всех филиалов — не более 48 часов.",
                },
            ],
            "top_3_issues": [
                {
                    "id": "education_children_news_missing",
                    "priority": "high",
                    "title": "Пять точек без новостей",
                    "problem": "Часть сети не использует публикации для видимости и доверия.",
                },
                {
                    "id": "network_duplicate_listing",
                    "priority": "medium",
                    "title": "Дубль Балканской площади",
                    "problem": "Одна из 21 найденной карточки дублирует точку и не имеет рейтинга.",
                },
                {
                    "id": "education_children_reviews_unanswered",
                    "priority": "medium",
                    "title": "15 отзывов без ответа",
                    "problem": "Очередь распределена по девяти филиалам сети.",
                },
            ],
            "action_plan": {
                "next_24h": [
                    "Проверить и пометить дубль карточки Балканской площади.",
                    "Ответить на отзывы в филиалах с самой большой очередью.",
                ],
                "next_7d": [
                    "Запустить первые новости в пяти филиалах без публикаций.",
                    "Зафиксировать единый шаблон: сетевая тема плюс локальный факт и фото филиала.",
                ],
                "ongoing": [
                    "Сравнивать точки по рейтингу, отзывам, ответам и регулярности новостей.",
                    "Отвечать на новые отзывы во всех филиалах в течение 48 часов.",
                    "Для каждой публикации использовать факты и фото конкретной точки.",
                ],
            },
            "photo_shots_missing": [
                "Материалы и упражнения крупным планом",
                "Специалист и ребёнок в процессе занятия",
                "Диагностический стол без персональных данных",
            ],
            "positioning_focus": [
                "Показывать изменения в речи через подтверждённые истории.",
                "Объяснять работу специалиста через конкретное упражнение или этап.",
                "Заканчивать публикацию одним действием: записаться на диагностику или уточнить условия.",
            ],
            "cadence": {"news_posts_per_month_min": 4, "photos_per_month_min": 8, "reviews_response_hours_max": 48},
        }
    )
    page["audit"] = audit
    return page


def apply_page(page: dict) -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id
            FROM users
            WHERE COALESCE(is_superadmin, FALSE) = TRUE
            ORDER BY created_at ASC NULLS LAST, id ASC
            LIMIT 1
            """
        )
        user = cur.fetchone()
        if not user:
            raise RuntimeError("Superadmin user not found")
        user_id = str(user["id"])

        cur.execute("SELECT company_id, company_location_id FROM prospectingleads WHERE id = %s", (LEAD_ID,))
        lead_row = cur.fetchone() or {}
        cur.execute(
            """
            INSERT INTO adminprospectingleadpublicoffers (
                lead_id, slug, page_json, is_active, created_by, created_at, updated_at,
                business_id, business_profile, source_type, generated_json, published_json,
                edit_status, published_by, published_at, company_id, company_location_id,
                audit_context
            ) VALUES (
                %s, %s, %s, TRUE, %s, NOW(), NOW(), %s, %s, %s, %s, %s,
                'published', %s, NOW(), %s, %s, 'public'
            )
            ON CONFLICT (lead_id) DO UPDATE
            SET slug = EXCLUDED.slug,
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
                LEAD_ID,
                "education_children",
                "partnership_partner",
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


def main() -> None:
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
