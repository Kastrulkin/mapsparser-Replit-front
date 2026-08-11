"""Founder-led copy recipes for LocalOS sales outreach.

The public signal opens the conversation but never becomes the whole offer.
Every recipe is assembled only from approved sender facts and recipient evidence.
"""

from __future__ import annotations

import re
from typing import Any

from services.outreach_playbook import (
    APPROVED_OUTREACH_COPY_CONTRACTS,
    APPROVED_FOUNDER_ORIGIN,
    APPROVED_LOCALOS_CASES,
    APPROVED_LOCALOS_MESSAGE_EXAMPLES,
    APPROVED_LOCALOS_PROOFS,
)
from services.outreach_template_service import (
    render_outreach_template,
    select_outreach_template,
)


BEAUTY_CATEGORY_MARKERS = (
    "барбер",
    "бров",
    "визаж",
    "космет",
    "макияж",
    "массаж",
    "ногт",
    "парикмах",
    "перманент",
    "ресниц",
    "салон красоты",
    "спа",
    "стилист",
    "эпиляц",
)

PRIVATE_SPECIALIST_MARKERS = (
    "врач-косметолог",
    "доктор-косметолог",
    "кабинет",
    "частн",
    "услуги частных специалистов",
)

NETWORK_MARKERS = ("сеть ", "сеть-", "филиал", "студии ", "салоны ")

FOUNDER_LED_SIGNAL_COMBOS = {
    "active_social_with_map_gap",
    "active_social_with_service_price_gap",
    "active_social_with_unanswered_negative_review",
    "recent_new_service_announcement",
    "recent_event_announcement",
}

PUBLICATION_PLATFORM_LABELS = {
    "telegram": "Telegram",
    "vk": "VK",
    "google_business": "Google Business Profile в beta-режиме",
}


def clean_copy(value: Any) -> str:
    return " ".join(str(value or "").replace("—", "-").replace("«", '"').replace("»", '"').split())


def outreach_email_subject(lead_name: Any) -> str:
    """Return the approved, invariant email subject for every outreach lead."""

    normalized_name = clean_copy(lead_name) or "Клиент"
    suffix = " | ЛокалОС | Сотрудничество"
    return f"{normalized_name[:200 - len(suffix)]}{suffix}"


def approved_copy_contract(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Return an explicitly selected, versioned editorial contract only."""

    key = clean_copy(candidate.get("approved_copy_contract"))
    return next(
        (
            item for item in APPROVED_OUTREACH_COPY_CONTRACTS
            if item["key"] == key and item["status"] == "approved"
        ),
        None,
    )


def _ready_publication_labels(candidate: dict[str, Any]) -> list[str]:
    capabilities = candidate.get("publication_capabilities")
    if not isinstance(capabilities, dict):
        return []
    labels = []
    for item in capabilities.get("channels") or []:
        if not isinstance(item, dict):
            continue
        platform = clean_copy(item.get("platform")).lower()
        if (
            item.get("connected") is True
            and item.get("provider_ready") is True
            and clean_copy(item.get("publish_mode")).lower() == "api"
            and clean_copy(item.get("status")).lower() == "ready"
            and platform in PUBLICATION_PLATFORM_LABELS
        ):
            labels.append(PUBLICATION_PLATFORM_LABELS[platform])
    return labels


def publication_solution(candidate: dict[str, Any]) -> str:
    labels = _ready_publication_labels(candidate)
    if not labels:
        return (
            "После подключения каналов и вашего подтверждения LocalOS автоматически "
            "публикует материалы в поддерживаемые каналы."
        )
    if len(labels) == 1:
        destinations = labels[0]
    else:
        destinations = f"{', '.join(labels[:-1])} и {labels[-1]}"
    return (
        "После вашего подтверждения LocalOS автоматически публикует "
        f"материалы в {destinations}."
    )


def _has_recipient_map_evidence(candidate: dict[str, Any]) -> bool:
    if clean_copy(candidate.get("map_observation")):
        return True
    if "map_gap" in clean_copy(candidate.get("signal_combo")).lower():
        return True
    map_kinds = {"map_rating", "map_issue", "map_gap", "map_services", "map_reviews"}
    if (
        clean_copy(candidate.get("evidence_kind")).lower() in map_kinds
        and bool(clean_copy(candidate.get("source_url")))
    ):
        return True
    return any(
        isinstance(item, dict)
        and clean_copy(item.get("kind")).lower() in map_kinds
        and bool(clean_copy(item.get("source_url")))
        for item in candidate.get("supporting_evidence") or []
    )


def localos_beauty_segment(
    category: Any,
    recipient: Any,
    public_context: Any = "",
) -> str | None:
    public_identity = clean_copy(public_context).split("опубликовано:", 1)[0]
    haystack = (
        f"{clean_copy(category)} {clean_copy(recipient)} {public_identity}"
    ).lower()
    if not any(marker in haystack for marker in BEAUTY_CATEGORY_MARKERS):
        return None
    if any(marker in haystack for marker in NETWORK_MARKERS):
        return "beauty_network"
    if any(marker in haystack for marker in PRIVATE_SPECIALIST_MARKERS):
        return "private_beauty_specialist"
    return "beauty_team"


def natural_observation(candidate: dict[str, Any]) -> str:
    observation = clean_copy(candidate.get("observed_fact")).rstrip(" .!?;")
    rating_match = re.search(
        r"рейтинг\s*-\s*([0-9]+(?:[.,][0-9]+)?);\s*публичных отзывов\s*-\s*(\d+)",
        observation,
        flags=re.IGNORECASE,
    )
    if rating_match:
        return (
            f"В публичной карточке сейчас {rating_match.group(2)} отзыва "
            f"и рейтинг {rating_match.group(1)}"
        )
    services_match = re.search(
        r"всего услуг\s*-\s*(\d+);\s*с ценой\s*-\s*(\d+)",
        observation,
        flags=re.IGNORECASE,
    )
    if services_match:
        return (
            f"В карточке указано {services_match.group(1)} услуг, "
            f"но цена видна только у {services_match.group(2)}"
        )
    if clean_copy(candidate.get("evidence_kind")) == "telegram_post":
        lowered = observation.lower()
        if "двойным подбородком" in lowered:
            return (
                "В Telegram вы разбираете тему двойного подбородка и объясняете, "
                "от чего зависит выбор метода"
            )
        if "массаж лица" in lowered:
            return "В Telegram вы подробно объясняете клиентам пользу массажа лица"
        if "менопауз" in lowered:
            return (
                "В Telegram вы разбираете, есть ли смысл в "
                "косметологических процедурах после менопаузы"
            )
        if "лазер летом" in lowered:
            return (
                "В Telegram вы объясняете, при каких условиях можно "
                "делать лазерную эпиляцию летом"
            )
        if "коррекцией губ" in lowered or "коррекции губ" in lowered:
            return "В Telegram вы разбираете вопросы перед коррекцией губ"
        if "коллаген" in lowered:
            return "В Telegram вы разбираете, зачем коже коллаген"
        if "лотере" in lowered:
            return "В Telegram вы напоминаете клиентам о лотерее"
        if "знакомьтесь" in lowered or "поздравляем" in lowered:
            return "В Telegram вы знакомите подписчиков с командой"
        if "сеть студий" in lowered and "spa" in lowered:
            return "В Telegram вы объясняете, зачем волосам нужен SPA-уход"
        if any(marker in lowered for marker in ("свободн", "горящ")) and any(
            marker in lowered for marker in ("окн", "окош")
        ):
            return "В Telegram вы публикуете свободные окна для записи"
        if "фотостарен" in lowered or "солнцезащит" in lowered:
            return "В Telegram вы пишете о фотостарении и солнцезащитных средствах"
        if "мама не разрешает краситься тушью" in lowered:
            return (
                "В Telegram вы разбираете ситуацию, когда подростку "
                "хочется яркий взгляд, а родители не разрешают тушь"
            )
        if "клиентский день" in lowered:
            return "В Telegram вы анонсируете клиентский день в салоне"
        if "акция от апельсин" in lowered:
            return "В Telegram вы показываете, как прошла акция на Кушелевской дороге"
        post_text = observation.split("опубликовано:", 1)[-1].strip(' "')
        post_text = re.sub(r"[_*#]+", " ", post_text)
        post_text = re.sub(r"^[^a-zа-яё0-9]+", "", post_text, flags=re.IGNORECASE)
        snippet = " ".join(post_text.split()[:12]).rstrip(" .,!?:;")
        if snippet:
            return f'В Telegram вы пишете: "{snippet}"'
        return "Увидел вашу публикацию для клиентов в Telegram"
    return observation


def _timing_observation(signal_combo: str, observed_fact: Any) -> str:
    observation = clean_copy(observed_fact)
    if signal_combo == "recent_price_update_announcement":
        return "обновление цен и прайс-листа"
    if signal_combo == "recent_new_service_announcement":
        match = re.search(
            r"нов\w*\s+услуг\w*\s*[-:]\s*([^.!?]{3,80})",
            observation,
            flags=re.IGNORECASE,
        )
        if match:
            service = re.split(
                r"\s+(?:метод|подходит|позволяет|теперь|для)\b",
                match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(' "-,:;')
            if service:
                return f'анонс новой услуги: "{service}"'
        return "анонс новой услуги"
    event_match = re.search(
        r"(\d{1,2}\s+[а-яё]+)\s*[-:]?\s*клиентск\w*\s+день",
        observation,
        flags=re.IGNORECASE,
    )
    if event_match:
        return f"анонс клиентского дня {event_match.group(1)}"
    return "анонс события для клиентов"


def _owner_context(segment: str | None) -> str:
    if segment == "private_beauty_specialist":
        return (
            "У частного специалиста контент, карточки и отзывы часто остаются на потом: "
            "сначала нужно работать с клиентами"
        )
    if segment == "beauty_network":
        return (
            "В сети такие задачи легко расходятся по разным точкам и снова "
            "возвращаются к руководителю"
        )
    return (
        "В салоне такие задачи часто остаются на владельце и проигрывают "
        "тому, что нужно решить сегодня"
    )


def _scenario_label(segment: str | None) -> str:
    if segment == "private_beauty_specialist":
        return "частного специалиста"
    if segment == "beauty_network":
        return "сети салонов"
    return "салона"


def select_approved_localos_case(candidate: dict[str, Any]) -> dict[str, Any]:
    """Choose a real approved case without turning a hypothesis into a claim."""

    requested_key = clean_copy(candidate.get("approved_case_key"))
    approved = [
        item for item in APPROVED_LOCALOS_CASES
        if item.get("status") == "approved"
    ]
    if requested_key:
        selected = next((item for item in approved if item.get("key") == requested_key), None)
        if selected:
            return dict(selected)

    evidence = " ".join(
        clean_copy(candidate.get(key)).lower()
        for key in (
            "observed_fact", "map_observation", "problem_hypothesis",
            "signal_combo", "signal_hypothesis_key",
        )
    )
    segment = clean_copy(candidate.get("recipient_segment"))
    preferred_key = "beauty_maps_zero_to_ten"
    if "услуг" in evidence and any(marker in evidence for marker in ("цен", "назван", "каталог")):
        preferred_key = "beauty_service_catalog_orders_plus_ten"
    elif "отзыв" in evidence and any(marker in evidence for marker in ("без ответ", "неотвеч")):
        preferred_key = "reviews_save_seven_hours"
    elif any(marker in evidence for marker in ("контент", "публикац")) and not any(
        marker in evidence for marker in ("рейтинг", "картах", "map_gap")
    ):
        preferred_key = "beauty_social_autopublishing"
    selected = next((item for item in approved if item.get("key") == preferred_key), approved[0])
    allowed_segments = selected.get("recipient_segments") or ()
    if allowed_segments and segment and segment not in allowed_segments:
        selected = approved[0]
    return dict(selected)


def localos_case_for_angle(angle: str, candidate: dict[str, Any]) -> dict[str, Any]:
    """Select the approved proof assigned to a reviewed sequence angle."""

    key_by_angle = {
        "content_operations": "beauty_social_autopublishing",
        "average_ticket": "beauty_service_catalog_revenue_plus_twenty",
        "reviews_service": "reviews_save_seven_hours",
    }
    requested_key = key_by_angle.get(clean_copy(angle))
    if requested_key:
        selected = next(
            (
                item
                for item in APPROVED_LOCALOS_CASES
                if item.get("key") == requested_key and item.get("status") == "approved"
            ),
            None,
        )
        if selected:
            return dict(selected)
    return select_approved_localos_case(candidate)


def founder_led_localos_text(
    angle: str,
    candidate: dict[str, Any],
    story: dict[str, Any] | None,
) -> str | None:
    if clean_copy(angle) == "respectful_close":
        angle = "integrated_system"
    if clean_copy(candidate.get("sender_mode")) not in {"", "localos"}:
        return None
    segment = clean_copy(candidate.get("recipient_segment")) or localos_beauty_segment(
        candidate.get("recipient_category"),
        candidate.get("recipient"),
        candidate.get("observed_fact"),
    )
    signal_combo = clean_copy(candidate.get("signal_combo"))
    composite_localos_signal = signal_combo in FOUNDER_LED_SIGNAL_COMBOS
    if not segment and not composite_localos_signal:
        return None

    sender = clean_copy(candidate.get("sender"))
    role = clean_copy(candidate.get("sender_role"))
    introduction = ", ".join(part for part in (sender, role) if part)
    sender_identity = introduction or "Александр Демьянов, основатель LocalOS"
    approved_story = clean_copy(candidate.get("founder_story"))
    approved_proof = clean_copy(candidate.get("founder_proof"))
    if not approved_proof and story:
        approved_proof = clean_copy(story.get("proof"))

    # A supported, versioned template is the preferred writing path. Explicit
    # founder-approved copy contracts keep priority, and a caller can disable
    # reuse after the same template has already appeared in the sequence.
    if (
        not approved_copy_contract(candidate)
        and clean_copy(candidate.get("outreach_template_key"))
        and candidate.get("outreach_template_disabled") is not True
    ):
        template_selection = select_outreach_template(angle, candidate)
        template_text = render_outreach_template(template_selection, candidate)
        if template_text:
            return template_text

    if angle == "signal":
        if signal_combo == "recent_price_update_announcement":
            localos_action = clean_copy(candidate.get("localos_action")) or (
                "LocalOS готовит обновления цен для сайта, карт и других площадок - "
                "вам остаётся проверить и подтвердить."
            )
            approved_case = next(
                item
                for item in APPROVED_LOCALOS_CASES
                if item.get("key") == "salon_price_300plus_clicks_v1"
            )
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                "Увидел, что вы обновили цены и прайс-лист.\n\n"
                "Если после такого обновления новые цены приходится отдельно "
                "переносить на сайт, карты и другие площадки, а затем проверять, "
                "что нигде не осталась старая версия.\n\n"
                f"{localos_action}\n\n"
                f"{approved_case['safe_formulation']}"
            )
        if signal_combo == "active_social_with_service_price_gap":
            services_match = re.search(
                r"найдено\s+(\d+)\s+услуг;\s+цена указана у\s+(\d+)",
                clean_copy(candidate.get("observed_fact")),
                flags=re.IGNORECASE,
            )
            total = services_match.group(1) if services_match else "несколько"
            priced = services_match.group(2) if services_match else "части"
            audit_url = clean_copy(candidate.get("public_audit_url"))
            audit_block = f"\n{audit_url}" if audit_url else ""
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                "Увидел, что вы регулярно ведёте свой канал. При этом в карточке "
                f"на картах указано {total} услуг, а цена видна только у {priced}.\n\n"
                "Клиенту из-за этого сложнее быстро выбрать услугу и записаться. "
                "LocalOS помогает привести список услуг и цены в понятный вид. "
                "Для одного салона такая работа дала рост выручки на 20%.\n\n"
                f"Вот короткий разбор карточки:{audit_block}\n\n"
                "Вам может быть интересно?"
            )
        if signal_combo == "active_social_with_unanswered_negative_review":
            review_match = re.search(
                r"найдено\s+(\d+)\s+свежих отзыв",
                clean_copy(candidate.get("observed_fact")),
                flags=re.IGNORECASE,
            )
            review_count = review_match.group(1) if review_match else ""
            if review_count == "1":
                review_phrase = "свежий отзыв"
            elif review_count:
                review_number = int(review_count)
                review_word = (
                    "отзыва"
                    if review_number % 10 in {2, 3, 4}
                    and review_number % 100 not in {12, 13, 14}
                    else "отзывов"
                )
                review_phrase = f"{review_count} свежих {review_word}"
            else:
                review_phrase = "несколько свежих отзывов"
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                "Увидел, что вы регулярно ведёте свой канал. При этом в карточке "
                f"на картах есть {review_phrase} с оценкой до 3 без ответа.\n\n"
                "День забит, а тут прилетает плохой отзыв. Мастер не понял клиента, "
                "а разбираться теперь владельцу. LocalOS отслеживает новые отзывы и "
                "готовит ответы - вам остаётся только подтвердить. Для сети кафе это "
                "освободило 7 часов в неделю.\n\n"
                "Вам может быть это интересно?"
            )
        if signal_combo in {"recent_new_service_announcement", "recent_event_announcement"}:
            observation = _timing_observation(signal_combo, candidate.get("observed_fact"))
            bridge = (
                "Такой повод можно один раз подготовить и адаптировать для ваших "
                "публичных каналов."
            )
            map_sentence = (
                " По тем же данным можно отдельно обновить карточку на картах."
                if _has_recipient_map_evidence(candidate)
                else ""
            )
            audit_url = clean_copy(candidate.get("public_audit_url"))
            audit_block = f"\n{audit_url}" if audit_url else ""
            audit_subject = (
                "публичной карточки"
                if _has_recipient_map_evidence(candidate)
                else "публичных каналов"
            )
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                f"Увидел ваш свежий {observation}.\n\n"
                f"{bridge}{map_sentence}\n\n"
                f"{publication_solution(candidate)}\n\n"
                f"Мы собрали короткий разбор {audit_subject}:{audit_block}\n\n"
                "Вам может быть это интересно?"
            )
        if signal_combo == "active_social_with_map_gap":
            rating_match = re.search(
                r"рейтинг\s+([0-9]+(?:[.,][0-9]+)?)\s+и\s+(\d+)\s+отзыв",
                clean_copy(candidate.get("observed_fact")),
                flags=re.IGNORECASE,
            )
            rating = rating_match.group(1) if rating_match else "ниже сильных конкурентов"
            reviews = rating_match.group(2) if rating_match else "немного"
            review_count = int(reviews) if reviews.isdigit() else 0
            review_word = "отзывов"
            if review_count % 10 == 1 and review_count % 100 != 11:
                review_word = "отзыв"
            elif review_count % 10 in {2, 3, 4} and review_count % 100 not in {12, 13, 14}:
                review_word = "отзыва"
            audit_url = clean_copy(candidate.get("public_audit_url"))
            audit_block = f"\n{audit_url}" if audit_url else ""
            approved_offer = clean_copy(candidate.get("next_step"))
            price_line = (
                " - от 1200 рублей в месяц"
                if re.search(r"(?:1\s*200|1200)", approved_offer)
                else ""
            )
            map_gap_copy = (
                f"Сейчас в карточке на картах рейтинг {rating} и только {reviews} {review_word}. "
                "Часто при таком количестве отзывов карточке сложнее подняться выше в выдаче. "
                "Тогда её видит меньше людей, и может приходить меньше обращений."
                if 0 < review_count <= 10
                else (
                    f"Сейчас в карточке на картах рейтинг {rating} "
                    f"при {reviews} {'отзыве' if review_count == 1 else 'отзывах'}. "
                    "Когда отзывов много, такой рейтинг уже заметно влияет на доверие."
                )
            )
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                "Увидел, что вы активно ведёте соцсети. Карты тоже могли бы "
                "помогать вам привлекать клиентов.\n\n"
                f"{map_gap_copy}\n\n"
                "Сам больше десяти лет в бизнесе и понимаю, почему регулярные задачи "
                "проигрывают клиентам и операционке.\n\n"
                f"Вот короткий разбор с конкретными шагами:{audit_block}\n\n"
                "Шаги можно выполнить самостоятельно. Если захотите, часть работы "
                f"можно поручить LocalOS{price_line}.\n\n"
                "Вам может быть это интересно?"
            )
        observation = natural_observation(candidate)
        map_observation = clean_copy(candidate.get("map_observation"))
        map_match = re.search(
            r"рейтинг\s*[\-—]\s*([0-9]+(?:[.,][0-9]+)?);\s*"
            r"публичных отзывов\s*[\-—]\s*(\d+)",
            map_observation,
            flags=re.IGNORECASE,
        )
        map_block = "Карты тоже могли бы помогать вам привлекать клиентов."
        if map_match:
            rating_value = float(map_match.group(1).replace(",", "."))
            review_count = int(map_match.group(2))
            if rating_value == 0 and review_count == 0:
                map_block += " В карточке пока нет рейтинга и отзывов."
            else:
                map_block += (
                    f" Сейчас в карточке на картах рейтинг {map_match.group(1)} "
                    f"и всего {map_match.group(2)} отзывов."
                )
        audit_url = clean_copy(candidate.get("public_audit_url"))
        approved_offer = clean_copy(candidate.get("next_step"))
        price_line = (
            " - от 1200 рублей в месяц"
            if re.search(r"(?:1\s*200|1200)", approved_offer)
            else ""
        )
        if (
            clean_copy(candidate.get("evidence_kind")) == "telegram_post"
            and observation
            and audit_url
        ):
            observation_for_sentence = observation[:1].lower() + observation[1:]
            telegram_activity = re.sub(
                r"^в Telegram вы\s+",
                "",
                observation_for_sentence,
                flags=re.IGNORECASE,
            )
            if _has_recipient_map_evidence(candidate):
                return (
                    f"Здравствуйте! Я {introduction}.\n\n"
                    f"Увидел, что в Telegram вы {telegram_activity} и активно ведёте канал.\n\n"
                    f"{map_block}\n\n"
                    "Мы посмотрели, как компания представлена в Яндекс Картах, "
                    "и собрали короткий разбор с конкретными шагами:\n"
                    f"{audit_url}\n\n"
                    "Шаги можно выполнить самостоятельно. Если захотите, часть работы "
                    f"можно поручить LocalOS{price_line}.\n\n"
                    "Вам может быть это интересно?"
                )
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                f"Увидел, что в Telegram вы {telegram_activity} и активно ведёте канал.\n\n"
                "Один такой материал можно адаптировать для других публичных каналов.\n\n"
                f"{publication_solution(candidate)}\n\n"
                f"Мы собрали короткий разбор публичных каналов:\n{audit_url}\n\n"
                "Показать на вашей публикации?"
            )
        return (
            f"Здравствуйте! Я {introduction}.\n\n"
            f"Посмотрел ваши открытые площадки. {observation}.\n\n"
            "Мы собрали короткий разбор по публичным данным компании. "
            "В нём только проверяемые наблюдения и конкретные шаги.\n\n"
            "Посмотреть разбор?"
        )

    if angle == "founder_story":
        return (
            "Здравствуйте! Коротко дополню.\n\n"
            "Понимаю, почему до таких задач часто не доходят руки: клиенты и "
            "ежедневная операционка всегда срочнее. Поэтому обновления карточек, "
            "контента и отзывов легко остаются на потом.\n\n"
            "Сам больше десяти лет в бизнесе и хорошо это понимаю.\n\n"
            f"{APPROVED_FOUNDER_ORIGIN}\n\n"
            "Вам может быть интересно, какие повторяющиеся задачи можно снять с владельца?"
        )

    if angle == "proof":
        approved_case = select_approved_localos_case(candidate)
        return (
            "Здравствуйте! Писал вам на почту и в Telegram.\n\n"
            f"{approved_case['safe_formulation']}\n\n"
            "Мы не просто дали советы, а настроили регулярную работу с карточкой.\n\n"
            "Вам может быть интересно, что именно мы изменили?"
        )

    if angle == "content_operations":
        return (
            "Здравствуйте! Клиенты и операционка всегда срочнее, а контент остаётся на потом.\n\n"
            "LocalOS готовит версии из одного исходника, а вы проверяете и решаете, что публиковать.\n\n"
            f"{publication_solution(candidate)}\n\n"
            "Вам может быть интересно освободить время?"
        )

    if angle == "average_ticket":
        contract = approved_copy_contract(candidate)
        if contract and contract["key"] == "fgf_average_ticket_owner_v1":
            diagnostic_question, final_cta = contract["required_exact_phrases"]
            return (
                f"Здравствуйте! Я {sender_identity}.\n\n"
                "В карточке FGF medical опубликованы два комплекса лазерной эпиляции. "
                f"{diagnostic_question}\n\n"
                "LocalOS по подтверждённому прайсу соберёт матрицу услуг и допов, "
                "сценарии для администратора и поможет отследить результат.\n\n"
                f"{final_cta}"
            )
        approved_case = localos_case_for_angle(angle, candidate)
        return (
            "Здравствуйте! Вам знакома проблема, когда работы много, а средний чек всё равно маленький?\n\n"
            "LocalOS анализирует список услуг и цены, помогает найти допродажи, кросс-продажи и пакетные предложения. "
            f"{approved_case['safe_formulation']}\n\n"
            "Если знакома, давайте проверим, что можно сделать."
        )

    if angle == "reviews_service":
        example = next(
            item
            for item in APPROVED_LOCALOS_MESSAGE_EXAMPLES
            if item.get("key") == "reviews_owner_day_interruption"
        )
        return str(example["text"])

    if angle == "crm_growth":
        provider_name = clean_copy(candidate.get("crm_provider_name")) or "CRM"
        recipient = clean_copy(candidate.get("recipient")) or "вашего бизнеса"
        return (
            f"Здравствуйте! Я {sender_identity}.\n\n"
            f"На ваших публичных площадках видна запись через {provider_name}. "
            "Это показывает, что приёмы уже учитываются в системе, но само по себе не говорит о проблеме.\n\n"
            "Если вручную передать обезличенную статистику по услугам и визитам, LocalOS помогает "
            "проверить сценарии повторных предложений, допродаж и работы со средним чеком.\n\n"
            f"Актуальна ли для {recipient} задача увеличивать средний чек?"
        )

    if angle == "crm_content":
        provider_name = clean_copy(candidate.get("crm_provider_name")) or "CRM"
        return (
            f"Здравствуйте! Я {sender_identity}.\n\n"
            f"Ещё одна возможность, если запись ведётся через {provider_name}.\n\n"
            "Из названия выполненной услуги можно подготовить черновик публикации без данных клиента. "
            "Если прямое подключение не поддерживается, исходные данные передаются вручную; "
            "публикация остаётся только после вашей проверки.\n\n"
            "Показать короткий пример?"
        )

    if angle == "integrated_system":
        return (
            "Здравствуйте! LocalOS помогает не только с картами.\n\n"
            "Система готовит контент и ответы на отзывы, помогает с услугами, КПИ, рабочими схемами и поиском партнёров. Удачные решения не теряются, а становятся повторяемыми сценариями.\n\n"
            "Какая из этих задач сейчас отнимает у вас больше всего времени?"
        )

    if angle == "founder_origin":
        return (
            "Здравствуйте! Сначала я создавал LocalOS для себя - чтобы меньше тонуть в операционке.\n\n"
            "Теперь с его помощью мы освобождаем от повторяющихся задач других предпринимателей. LocalOS уже применяется более чем в 240 точках малого бизнеса.\n\n"
            "Вам может быть это интересно?"
        )

    if angle == "audit_step":
        return (
            "Здравствуйте! Коротко о том, что ещё делает LocalOS.\n\n"
            "Мы помогаем с картами, отзывами и автопостингом, ищем локальных партнёров, "
            "собираем КПИ и схемы работы. Удачные сценарии не теряются: LocalOS накапливает опыт и помогает "
            "превращать его в повторяемые процессы.\n\n"
            "Какая из этих задач сейчас отнимает у вас больше всего времени?"
        )

    if angle == "phone_handoff":
        return (
            "Здравствуйте! Это Александр Демьянов, LocalOS.\n\n"
            "Ранее писал вам о LocalOS. Мы помогаем владельцам салонов снять с себя карты, контент, отзывы, "
            "поиск партнёров и часть контроля процессов.\n\n"
            "Какая из этих задач сейчас самая болезненная?"
        )

    return None


def founder_led_localos_subject(angle: str, candidate: dict[str, Any]) -> str | None:
    segment = clean_copy(candidate.get("recipient_segment")) or localos_beauty_segment(
        candidate.get("recipient_category"),
        candidate.get("recipient"),
        candidate.get("observed_fact"),
    )
    if not segment and clean_copy(candidate.get("signal_combo")) not in FOUNDER_LED_SIGNAL_COMBOS:
        return None
    return outreach_email_subject(candidate.get("recipient"))


def observation_is_grounded(text: str, observation: Any) -> bool:
    normalized_text = clean_copy(text).lower()
    normalized_observation = clean_copy(observation).lower()
    if not normalized_observation:
        return False
    if "telegram" in normalized_observation:
        if "telegram" not in normalized_text:
            return False
        if any(
            marker in normalized_text
            for marker in ("процедур", "клиент", "объясня")
        ):
            return True
        if (
            "горящ" in normalized_observation
            and "окош" in normalized_observation
            and "свободн" in normalized_text
            and "окн" in normalized_text
        ):
            return True
        post_text = normalized_observation.split("опубликовано:", 1)[-1]
        post_terms = [
            token
            for token in re.findall(r"[a-zа-яё]+", post_text)
            if len(token) >= 6
        ]
        return any(term[:6] in normalized_text for term in post_terms)
    numbers = re.findall(r"\d+(?:[.,]\d+)?", normalized_observation)
    if numbers and not all(number in normalized_text for number in numbers):
        return False
    important_terms = [
        token
        for token in re.findall(r"[a-zа-яё]+", normalized_observation)
        if len(token) >= 6 and token not in {"публичной", "карточке", "указано", "данным"}
    ]
    return bool(
        important_terms
        and sum(term[:6] in normalized_text for term in important_terms) >= min(2, len(important_terms))
    )
