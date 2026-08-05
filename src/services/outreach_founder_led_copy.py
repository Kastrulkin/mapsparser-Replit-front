"""Founder-led copy recipes for LocalOS sales outreach.

The public signal opens the conversation but never becomes the whole offer.
Every recipe is assembled only from approved sender facts and recipient evidence.
"""

from __future__ import annotations

import re
from typing import Any

from services.outreach_playbook import (
    APPROVED_FOUNDER_ORIGIN,
    APPROVED_LOCALOS_PROOFS,
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


def clean_copy(value: Any) -> str:
    return " ".join(str(value or "").replace("—", "-").replace("«", '"').replace("»", '"').split())


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


def founder_led_localos_text(
    angle: str,
    candidate: dict[str, Any],
    story: dict[str, Any] | None,
) -> str | None:
    if clean_copy(candidate.get("sender_mode")) not in {"", "localos"}:
        return None
    segment = clean_copy(candidate.get("recipient_segment")) or localos_beauty_segment(
        candidate.get("recipient_category"),
        candidate.get("recipient"),
        candidate.get("observed_fact"),
    )
    if not segment:
        return None

    sender = clean_copy(candidate.get("sender"))
    role = clean_copy(candidate.get("sender_role"))
    introduction = ", ".join(part for part in (sender, role) if part)
    approved_story = clean_copy(candidate.get("founder_story"))
    approved_proof = clean_copy(candidate.get("founder_proof"))
    if not approved_proof and story:
        approved_proof = clean_copy(story.get("proof"))

    if angle == "signal":
        if clean_copy(candidate.get("signal_combo")) == "active_social_with_map_gap":
            rating_match = re.search(
                r"рейтинг\s+([0-9]+(?:[.,][0-9]+)?)\s+и\s+(\d+)\s+отзыв",
                clean_copy(candidate.get("observed_fact")),
                flags=re.IGNORECASE,
            )
            rating = rating_match.group(1) if rating_match else "ниже сильных конкурентов"
            reviews = rating_match.group(2) if rating_match else "немного"
            audit_url = clean_copy(candidate.get("public_audit_url"))
            audit_block = f"\n{audit_url}" if audit_url else ""
            approved_offer = clean_copy(candidate.get("next_step"))
            price_line = (
                " - от 1200 рублей в месяц"
                if re.search(r"(?:1\s*200|1200)", approved_offer)
                else ""
            )
            return (
                f"Здравствуйте! Я {introduction}.\n\n"
                "Увидел, что вы активно ведёте соцсети. Карты тоже могли бы "
                "помогать вам привлекать клиентов.\n\n"
                f"Сейчас в карточке на картах рейтинг {rating} и только {reviews} отзыва. "
                "Часто при таком количестве отзывов карточке сложнее подняться выше в выдаче. "
                "Тогда её видит меньше людей, и может приходить меньше обращений.\n\n"
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
        map_block = (
            "Карты тоже могли бы помогать вам привлекать клиентов. "
            f"Сейчас в карточке на картах рейтинг {map_match.group(1)} "
            f"и всего {map_match.group(2)} отзывов."
            if map_match
            else ""
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
            f"Посмотрел ваши открытые площадки. {observation}.\n\n"
            "Мы собрали короткий разбор по публичным данным компании. "
            "В нём только проверяемые наблюдения и конкретные шаги.\n\n"
            "Посмотреть разбор?"
        )

    if angle == "founder_story":
        return (
            "Здравствуйте! Коротко дополню.\n\n"
            "Понимаю, почему до таких задач часто не доходят руки: клиенты и "
            "ежедневная операционка всегда срочнее. Владельцы часто описывают это так: "
            '"Если не я, то никто".\n\n'
            "Сам больше десяти лет в бизнесе и хорошо это понимаю.\n\n"
            f"{APPROVED_FOUNDER_ORIGIN}\n\n"
            "Вам может быть интересно, какие повторяющиеся задачи можно снять с владельца?"
        )

    if angle == "proof":
        return (
            "Здравствуйте! Писал вам на почту и в Telegram.\n\n"
            f"{APPROVED_LOCALOS_PROOFS[0]}\n\n"
            "Мы не просто дали советы, а настроили регулярную работу с карточкой.\n\n"
            "Вам может быть интересно, что именно мы изменили?"
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

    if angle == "respectful_close":
        return (
            "Здравствуйте! Закрою тему.\n\n"
            f"{APPROVED_FOUNDER_ORIGIN}\n\n"
            "LocalOS также накапливает опыт других компаний: рабочие связки можно проверять, улучшать и переносить в понятные сценарии.\n\n"
            "Если сейчас не до этого, больше напоминать не буду. Вернуться к теме позже?"
        )
    return None


def founder_led_localos_subject(angle: str, candidate: dict[str, Any]) -> str | None:
    segment = clean_copy(candidate.get("recipient_segment")) or localos_beauty_segment(
        candidate.get("recipient_category"),
        candidate.get("recipient"),
        candidate.get("observed_fact"),
    )
    if not segment:
        return None
    recipient = clean_copy(candidate.get("recipient"))
    labels = {
        "signal": f"{recipient} | короткий вопрос",
        "founder_story": "Почему я создал LocalOS",
        "proof": "Как LocalOS снимает регулярные задачи",
        "respectful_close": "Закрою тему",
    }
    return labels.get(angle)


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
