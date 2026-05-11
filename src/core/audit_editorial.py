from __future__ import annotations

import copy
import re
from typing import Any


SUMMARY_PUBLIC_MAX = 300
SUMMARY_WHATSAPP_MAX = 220


AUDIT_FORBIDDEN_MARKERS = (
    "за чем сюда идти",
    "слабый визуальный слой режет доверие",
    "зоны роста",
    "реальные запросы клиентов",
    "без допрекламы",
    "конверсионный блок",
    "конверсионные фото",
    "social proof",
    "для medical вертикали",
    "для beauty вертикали",
    "алгоритмы и пользователи",
    "ai ",
    "q&a",
    "всего 1 фото",
    "фото 1",
    "общее описание без структуры",
    "нет цены или формата",
    "ключевые направления",
)


TECHNICAL_PUBLIC_KEYS = {
    "audit_full",
    "ai_enrichment",
    "debug",
    "debug_json",
    "raw_response",
    "prompt",
    "prompt_text",
    "prompt_key",
    "prompt_version",
    "prompt_source",
    "model",
    "model_name",
    "reasoning",
}


PROFILE_ACTOR = {
    "medical": "пациент",
    "hospitality": "гость",
}

PROFILE_ACTOR_DATIVE = {
    "medical": "пациенту",
    "hospitality": "гостю",
}


def normalize_audit_text(value: Any, *, audit_profile: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return text

    replacements = (
        ("за чем сюда идти", "с каким запросом обращаться"),
        ("Зачем сюда идти", "С каким запросом обращаться"),
        (
            "Описание карточки не объясняет, с каким запросом сюда обращаться",
            "Описание не показывает основные услуги и поводы обратиться",
        ),
        (
            "описание карточки не объясняет, с каким запросом сюда обращаться",
            "описание не показывает основные услуги и поводы обратиться",
        ),
        (
            "Описание карточки не объясняет центр под поисковое намерение",
            "Описание не показывает ключевые процедуры и формат центра",
        ),
        (
            "описание карточки не объясняет центр под поисковое намерение",
            "описание не показывает ключевые процедуры и формат центра",
        ),
        (
            "Описание карточки не объясняет центр под запросы клиентов",
            "Описание не показывает ключевые процедуры, формат центра и кому он подходит",
        ),
        (
            "описание карточки не объясняет центр под запросы клиентов",
            "описание не показывает ключевые процедуры, формат центра и кому он подходит",
        ),
        (
            "Описание карточки не объясняет ценность бизнеса",
            "Описание не показывает, чем занимается бизнес и почему его выбрать",
        ),
        (
            "описание карточки не объясняет ценность бизнеса",
            "описание не показывает, чем занимается бизнес и почему его выбрать",
        ),
        ("слабый визуальный слой режет доверие", "не хватает визуальных доказательств выбора"),
        ("Слабый визуальный слой режет доверие", "Не хватает визуальных доказательств выбора"),
        ("зоны роста", "что мешает получать больше обращений"),
        ("Зоны роста", "Что мешает получать больше обращений"),
        ("под реальный спрос", "под поисковые сценарии клиентов"),
        ("Под реальный спрос", "Под поисковые сценарии клиентов"),
        ("под поисковое намерение", "под запросы клиентов"),
        ("Под поисковое намерение", "Под запросы клиентов"),
        ("реальные запросы клиентов", "поисковые сценарии клиентов"),
        ("Реальные запросы клиентов", "Поисковые сценарии клиентов"),
        ("без допрекламы", "без увеличения рекламного бюджета"),
        ("Без допрекламы", "Без увеличения рекламного бюджета"),
        ("конверсионные фото", "фото, которые помогают выбрать"),
        ("конверсионный блок", "понятный блок выбора"),
        ("conversion layer", "слой выбора"),
        ("Social proof", "Доверие через отзывы"),
        ("social proof", "доверие через отзывы"),
        ("Q&A", "вопросы и ответы"),
        ("q&a", "вопросы и ответы"),
        ("freshness", "свежести обновлений"),
        ("clinic / medical center / diagnostics / rehabilitation / specialty doctor", "медицинский центр, клиника, диагностика, реабилитация, профильные врачи"),
        ("Clinic / medical center / diagnostics / rehabilitation / specialty doctor", "Медицинский центр, клиника, диагностика, реабилитация, профильные врачи"),
        ("3–5 updates", "3–5 публикаций"),
        ("3-5 updates", "3–5 публикаций"),
        ("updates:", "публикаций:"),
        ("Updates:", "Публикаций:"),
        ("lunch offers", "обеденные предложения"),
        ("recovery journeys", "истории восстановления"),
        ("recovery / therapy", "восстановление и терапия"),
        ("Spa, Massage therapist, Wellness center", "спа, массаж, wellness-центр"),
        ("ресепшен", "стойка администратора"),
        ("в рабочей среде без визуального шума", "в рабочей обстановке"),
        ("УТП", "отличие"),
        ("утп", "отличие"),
        ("Добавить описание 500–1000 символов:", "Добавить короткое описание:"),
        ("Добавить описание 500-1000 символов:", "Добавить короткое описание:"),
        ("Для medical вертикали", "Для медицинской карточки"),
        ("Для beauty вертикали", "Для карточки услуг"),
        ("алгоритмы и пользователи ждут", "пользователям важно видеть"),
        ("Пациенты и алгоритмы ждут", "Пациентам важно видеть"),
        ("описание не превращает их в понятные причины записаться", "описание не выделяет их как основные причины выбрать карточку"),
        ("не превращает отзывы в SEO", "не использует отзывы для доверия и выбора"),
        ("не продаёт", "не объясняет"),
        ("режет доверие", "снижает доверие"),
        ("целевой зоны", "нужного уровня"),
        ("общее описание без структуры", "понятный список услуг"),
        ("Общее описание без структуры", "Понятный список услуг"),
        ("нет цены или формата", "не хватает цены и формата услуги"),
        ("Нет цены или формата", "Не хватает цены и формата услуги"),
        ("ключевые направления", "основные услуги"),
        ("Ключевые направления", "Основные услуги"),
    )
    result = text
    for source, target in replacements:
        result = result.replace(source, target)

    if audit_profile not in {"medical", "hospitality"}:
        result = result.replace("Пациент", "Клиент").replace("пациент", "клиент")
    if audit_profile not in {"beauty", "wellness", "medical"}:
        result = re.sub(r"\bсалона\b", "бизнеса", result, flags=re.IGNORECASE)
        result = re.sub(r"\bсалон\b", "бизнес", result, flags=re.IGNORECASE)

    result = re.sub(r"\s+", " ", result).strip()
    return result


def truncate_sentence(text: Any, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if len(value) <= limit:
        return value
    cut = value[: max(0, limit - 1)].rstrip()
    sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence_end >= 120:
        return cut[: sentence_end + 1].strip()
    return cut.rstrip(" .,;:") + "…"


def actor_for_profile(audit_profile: Any) -> str:
    return PROFILE_ACTOR.get(str(audit_profile or "").strip().lower(), "клиент")


def actor_dative_for_profile(audit_profile: Any) -> str:
    return PROFILE_ACTOR_DATIVE.get(str(audit_profile or "").strip().lower(), "клиенту")


def _first_issue(audit: dict[str, Any]) -> dict[str, Any]:
    for key in ("top_3_issues", "issue_blocks", "findings"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                return item
    return {}


def _issue_title(issue: dict[str, Any]) -> str:
    return str(issue.get("title") or issue.get("problem") or issue.get("description") or "").strip().rstrip(".")


def _issue_fix(issue: dict[str, Any]) -> str:
    return str(issue.get("fix") or issue.get("description") or issue.get("title") or "").strip().rstrip(".")


def _first_action_fix(audit: dict[str, Any], fallback: str) -> str:
    actions = audit.get("recommended_actions")
    if isinstance(actions, list):
        for item in actions:
            if not isinstance(item, dict):
                continue
            candidate = str(item.get("description") or item.get("fix") or item.get("title") or "").strip().rstrip(".")
            if candidate and candidate.lower() != fallback.lower():
                return candidate
    return fallback


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def detect_photo_signal_confidence(audit: dict[str, Any]) -> str:
    state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    explicit = str(
        audit.get("photo_signal_confidence")
        or state.get("photo_signal_confidence")
        or state.get("photos_confidence")
        or ""
    ).strip().lower()
    if explicit in {"confirmed", "weak", "parser_uncertain"}:
        return explicit

    photos_count = _safe_int(state.get("photos_count"))
    photos_state = str(state.get("photos_state") or "").strip().lower()
    photos_source = str(state.get("photos_source") or state.get("photos_count_source") or "").strip().lower()
    if photos_source in {"manual", "official_gallery", "platform_gallery", "confirmed"}:
        return "confirmed"
    if photos_state in {"good", "strong"} and photos_count >= 8:
        return "confirmed"
    if photos_count >= 8:
        return "weak"
    return "parser_uncertain"


def _services_focus(audit: dict[str, Any]) -> str:
    candidates: list[str] = []
    audit_profile = str(audit.get("audit_profile") or "").strip().lower()
    for key in ("search_intents_to_target", "services_preview", "top_services"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                text = str(item.get("current_name") or item.get("name") or item.get("title") or "").strip()
            else:
                text = str(item or "").strip()
            if not text:
                continue
            text = _clean_focus_term(text, audit_profile=audit_profile)
            if not text:
                continue
            normalized = text.lower().replace("ё", "е")
            if normalized in {candidate.lower().replace("ё", "е") for candidate in candidates}:
                continue
            candidates.append(text)
            if len(candidates) >= 3:
                break
        if len(candidates) >= 3:
            break
    if not candidates and audit_profile == "beauty":
        candidates = ["основные процедуры", "цены", "формат записи"]
    if not candidates and audit_profile == "wellness":
        candidates = ["массаж", "уходовые процедуры", "восстановление"]
    if not candidates and audit_profile == "medical":
        candidates = ["направления приёма", "специалисты", "формат записи"]
    if not candidates and audit_profile == "food":
        candidates = ["формат заведения", "меню", "бронь или заказ"]
    if not candidates and audit_profile == "fashion":
        candidates = ["ассортимент", "цены", "наличие"]
    if not candidates and audit_profile == "fitness":
        candidates = ["форматы тренировок", "расписание", "запись"]
    if not candidates and audit_profile == "hospitality":
        candidates = ["формат проживания", "условия", "бронь"]
    if not candidates:
        candidates = ["основные услуги", "цены", "способ обращения"]
    return ", ".join(candidates[:3])


def _clean_focus_term(value: str, *, audit_profile: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip(" ,.;"))
    if not text:
        return ""
    city_noise = (
        "санкт-петербург",
        "спб",
        "городской посёлок",
        "ленинградская область",
    )
    lowered = text.lower().replace("ё", "е")
    blocked_terms = {
        "общее описание без структуры",
        "нет цены или формата",
        "ключевые направления",
        "что предлагает бизнес",
        "цены / отзывы",
        "компания рядом",
    }
    if lowered in blocked_terms:
        return ""
    if any(term in lowered for term in ("общее описание без структуры", "нет цены или формата")):
        return ""
    if audit_profile == "default_local_business":
        if any(token in lowered for token in ("компания рядом", "цены / отзывы", "что предлагает бизнес")):
            return ""
    replacements = {
        "spa": "спа",
        "massage": "массаж",
        "wellness center": "центр восстановления",
        "pilates": "пилатес",
        "yoga": "йога",
        "fitness": "фитнес",
    }
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    text = lowered
    if any(term in text for term in ("понятный список услуг", "не хватает цены", "основные услуги")):
        return ""
    for token in city_noise:
        text = text.replace(token, "").strip(" ,-/")
    text = re.sub(r"\s+", " ", text).strip(" ,-/")
    if len(text) > 54:
        return ""
    return text


def _state_facts(audit: dict[str, Any]) -> list[str]:
    state = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    primary_facts: list[str] = []
    secondary_facts: list[str] = []
    services_count = _safe_int(state.get("services_count"))
    priced_count = _safe_int(state.get("services_with_price_count") or state.get("priced_services_count"))
    photos_count = _safe_int(state.get("photos_count"))
    reviews_count = _safe_int(state.get("reviews_count"))
    unanswered = _safe_int(state.get("unanswered_reviews_count"))
    rating = state.get("rating")
    has_website = state.get("has_website")
    has_activity = state.get("has_recent_activity")
    description_present = bool(state.get("description_present"))
    photo_confidence = detect_photo_signal_confidence(audit)

    if services_count > 0 and priced_count <= 0:
        primary_facts.append(f"услуг {services_count}, но цены не показаны")
    elif services_count <= 0:
        primary_facts.append("услуги не раскрыты в карточке")
    if reviews_count > 0 and unanswered > 0:
        primary_facts.append(f"без ответа {unanswered} отзывов")
    elif reviews_count <= 0:
        primary_facts.append("отзывов пока нет")
    if rating is not None:
        try:
            rating_value = float(rating)
        except (TypeError, ValueError):
            rating_value = None
        if rating_value is not None and 0 < rating_value < 4.5:
            primary_facts.append(f"рейтинг {rating_value:.1f}")
    if has_website is False:
        primary_facts.append("сайт не указан")
    if not description_present:
        primary_facts.append("описание не объясняет основные услуги")
    if has_activity is False:
        secondary_facts.append("карточка давно не обновлялась")

    if photo_confidence == "confirmed":
        if photos_count <= 0:
            secondary_facts.append("фотографий нет")
        elif photos_count == 1:
            secondary_facts.append("в карточке только одно фото")
        elif photos_count < 8:
            secondary_facts.append(f"фото пока {photos_count}")
    elif photos_count <= 1:
        secondary_facts.append("по собранным данным визуальный блок выглядит слабым")

    if len(primary_facts) >= 2:
        return primary_facts[:3]
    return [*primary_facts, *secondary_facts][:3]


def _state_fact(audit: dict[str, Any]) -> str:
    return ", ".join(_state_facts(audit)[:2])


def _fact_family(fact: str) -> str:
    lowered = str(fact or "").lower().replace("ё", "е")
    if any(token in lowered for token in ("услуг", "описан", "направлен", "процедур", "формат")):
        return "offer_clarity"
    if "цен" in lowered:
        return "price"
    if "отзыв" in lowered or "рейтинг" in lowered:
        return "reputation"
    if "сайт" in lowered or "контакт" in lowered:
        return "contact"
    if "обновля" in lowered or "новост" in lowered:
        return "freshness"
    if "фото" in lowered or "визуаль" in lowered or "фотограф" in lowered:
        return "visual"
    return lowered[:40]


def _issue_families(text: str) -> set[str]:
    lowered = str(text or "").lower().replace("ё", "е")
    families: set[str] = set()
    if any(token in lowered for token in ("услуг", "описан", "направлен", "процедур", "формат", "выбор")):
        families.add("offer_clarity")
    if "цен" in lowered:
        families.add("price")
    if "отзыв" in lowered or "рейтинг" in lowered:
        families.add("reputation")
    if "сайт" in lowered or "контакт" in lowered:
        families.add("contact")
    if "обновля" in lowered or "новост" in lowered:
        families.add("freshness")
    if "фото" in lowered or "визуаль" in lowered:
        families.add("visual")
    return families


def _summary_state_facts(audit: dict[str, Any], issue_title: str) -> list[str]:
    issue_related = _issue_families(issue_title)
    selected: list[str] = []
    selected_families: set[str] = set()
    for fact in _state_facts(audit):
        family = _fact_family(fact)
        if family in issue_related:
            continue
        if family in selected_families:
            continue
        selected.append(fact)
        selected_families.add(family)
        if len(selected) >= 2:
            break
    if selected:
        return selected
    return []


def _pattern_hint(audit: dict[str, Any]) -> str:
    patterns = audit.get("industry_patterns") if isinstance(audit.get("industry_patterns"), dict) else {}
    examples = patterns.get("examples") if isinstance(patterns.get("examples"), list) else []
    service_patterns = patterns.get("service_patterns") if isinstance(patterns.get("service_patterns"), list) else []
    if examples:
        return f"Ориентир для услуг: {', '.join(str(item) for item in examples[:2])}."
    if service_patterns:
        return str(service_patterns[0]).strip().rstrip(".") + "."
    return ""


def _summary_variant_index(audit: dict[str, Any]) -> int:
    basis = "|".join(
        str(audit.get(key) or "")
        for key in ("lead_id", "business_name", "name", "audit_profile", "audit_slug", "business_address", "summary_text")
    )
    return sum((index + 1) * ord(char) for index, char in enumerate(basis)) % 7


def _summary_impact(audit: dict[str, Any], *, actor: str, actor_dative: str) -> str:
    variants = (
        f"{actor[:1].upper() + actor[1:]} открывает карточку, но не получает достаточно причин для звонка или записи.",
        "Часть тёплого спроса уходит к конкурентам, где быстрее понятно, что выбрать.",
        "Карточка хуже доводит до обращения: нужно больше ясности в услугах, доверии и следующем шаге.",
        f"{actor_dative[:1].upper() + actor_dative[1:]} приходится сравнивать вручную, поэтому решение откладывается.",
        "Спрос есть, но карточка не всегда переводит просмотр в действие.",
        "На этапе выбора не хватает короткого ответа: что здесь главное и почему обратиться сюда.",
        "Пользователь видит карточку, но часть сомнений остаётся до звонка или визита.",
    )
    return variants[_summary_variant_index(audit)]


def _profile_action_words(audit_profile: str) -> dict[str, str]:
    if audit_profile == "medical":
        return {
            "action": "записаться на консультацию",
            "choice": "выбора врача или процедуры",
            "next": "записи на консультацию",
        }
    if audit_profile == "food":
        return {
            "action": "забронировать стол или сделать заказ",
            "choice": "выбора блюда или формата визита",
            "next": "брони или заказа",
        }
    if audit_profile == "fashion":
        return {
            "action": "уточнить наличие или выбрать товар",
            "choice": "выбора ассортимента",
            "next": "уточнения наличия",
        }
    if audit_profile == "hospitality":
        return {
            "action": "забронировать проживание",
            "choice": "выбора номера или формата отдыха",
            "next": "брони",
        }
    if audit_profile == "fitness":
        return {
            "action": "записаться на тренировку",
            "choice": "выбора тренировки",
            "next": "записи на тренировку",
        }
    return {
        "action": "записаться",
        "choice": "выбора услуги",
        "next": "записи",
    }


def _summary_action_prefix(audit: dict[str, Any]) -> str:
    variants = (
        "Начать стоит с",
        "Быстрее всего даст эффект",
        "Первым делом лучше",
        "Самая короткая правка",
        "Практичный первый шаг",
        "Для быстрого эффекта",
        "Сначала лучше",
        "В первую очередь стоит",
        "Самый понятный шаг",
        "Минимальная правка",
        "Лучше начать с",
        "Ближайшее действие",
    )
    return variants[_summary_variant_index(audit) % len(variants)]


def _rewrite_issue_title(audit: dict[str, Any], issue_title: str) -> str:
    text = normalize_audit_text(issue_title, audit_profile=str(audit.get("audit_profile") or ""))
    lowered = text.lower().replace("ё", "е")
    if "описание не показывает основные услуги" not in lowered:
        return text
    variants = (
        "в описании не видно, какие услуги здесь основные",
        "карточка не объясняет, с какими услугами обращаться в первую очередь",
        "предложение собрано слишком общо: основные услуги не выделены",
        "описание не помогает быстро понять формат услуг и повод записаться",
        "главные услуги есть в данных, но не собраны в понятный выбор для клиента",
        "карточка не показывает, чем именно точка сильна для нового клиента",
        "описание не превращает список услуг в понятный маршрут выбора",
    )
    return variants[_summary_variant_index(audit)]


def _editorial_next_action(audit: dict[str, Any], issue_fix: str) -> str:
    focus = _services_focus(audit)
    variant = _summary_variant_index(audit)
    audit_profile = str(audit.get("audit_profile") or "").strip().lower()
    words = _profile_action_words(audit_profile)
    normalized_fix = normalize_audit_text(issue_fix, audit_profile=str(audit.get("audit_profile") or ""))
    if focus:
        variants = (
            f"показать в описании {focus}: что выбрать, кому подходит и как {words['action']}",
            f"выделить {focus} и добавить короткую причину для {words['choice']}",
            f"собрать {focus} в понятный блок: результат, цена или ориентир, следующий шаг",
            f"переписать описание вокруг {focus}, чтобы клиент быстрее дошёл до {words['next']}",
            f"показать, что здесь главное: {focus}, и чем эта точка удобнее конкурентов",
            f"разделить {focus} по сценариям: для кого, какой результат, что делать дальше",
            f"добавить короткий блок про {focus}: отличие, ориентир по выбору и следующий шаг",
        )
        return variants[variant]
    if normalized_fix:
        lowered = normalized_fix.lower()
        if "опис" in lowered:
            return f"добавить в описание основные услуги, поводы обратиться и понятный способ {words['next']}"
        if "цен" in lowered:
            return "добавить цены или диапазоны цен в услуги, чтобы клиент мог сравнить варианты до звонка"
        if "отзыв" in lowered:
            return "ответить на свежие отзывы и вынести сильные формулировки клиентов в описание карточки"
        if "фото" in lowered:
            return "добавить фото работ, входа или результата, чтобы карточка давала больше доказательств выбора"
        return normalized_fix[:1].lower() + normalized_fix[1:]
    return f"выделить основные услуги, добавить доказательства выбора и довести клиента до {words['next']}"


def build_editorial_summary(audit: dict[str, Any], *, max_length: int = SUMMARY_PUBLIC_MAX) -> str:
    if not isinstance(audit, dict):
        return ""
    audit_profile = str(audit.get("audit_profile") or "").strip().lower()
    actor = actor_for_profile(audit_profile)
    actor_dative = actor_dative_for_profile(audit_profile)
    business_name = str(audit.get("business_name") or audit.get("name") or "").strip()
    issue = _first_issue(audit)
    issue_title = _rewrite_issue_title(audit, _issue_title(issue))
    issue_fix = normalize_audit_text(_first_action_fix(audit, _issue_fix(issue)), audit_profile=audit_profile)
    state_facts = _summary_state_facts(audit, issue_title)
    state_fact = ", ".join(state_facts[:2])
    pattern_hint = _pattern_hint(audit)
    next_action = _editorial_next_action(audit, issue_fix)

    if issue_title:
        if business_name:
            first = f"У «{business_name}»: {issue_title[:1].lower() + issue_title[1:]}."
        else:
            first = issue_title + "."
    elif state_fact:
        first = f"В карточке видно: {state_fact}."
    else:
        first = "Карточка нуждается в более понятной упаковке предложения."

    if state_fact:
        impact = _summary_impact(audit, actor=actor, actor_dative=actor_dative)
        second = f"Сейчас {state_fact}. {impact}"
    elif pattern_hint:
        second = pattern_hint
    else:
        second = _summary_impact(audit, actor=actor, actor_dative=actor_dative)

    third = f"{_summary_action_prefix(audit)}: {next_action}."

    summary = normalize_audit_text(" ".join([first, second, third]), audit_profile=audit_profile)
    if len(summary) <= max_length:
        return summary

    compact_second = " ".join(second.split(". ")[:1]).strip()
    if compact_second and not compact_second.endswith((".", "!", "?")):
        compact_second += "."
    compact_summary = normalize_audit_text(" ".join([first, compact_second, third]), audit_profile=audit_profile)
    if len(compact_summary) <= max_length:
        return compact_summary

    return truncate_sentence(
        normalize_audit_text(" ".join([first, third]), audit_profile=audit_profile),
        max_length,
    )


def build_summary_variants(audit: dict[str, Any]) -> dict[str, str]:
    public_summary = build_editorial_summary(audit, max_length=SUMMARY_PUBLIC_MAX)
    whatsapp_summary = build_editorial_summary(audit, max_length=SUMMARY_WHATSAPP_MAX)
    return {
        "summary_public": public_summary,
        "summary_whatsapp": whatsapp_summary,
    }


def _contains_forbidden_marker(text: Any) -> bool:
    lowered = str(text or "").strip().lower().replace("ё", "е")
    return any(marker.replace("ё", "е") in lowered for marker in AUDIT_FORBIDDEN_MARKERS)


def audit_quality_gate(audit: dict[str, Any]) -> dict[str, Any]:
    summary = str(audit.get("summary_text") or "").strip()
    issues: list[str] = []
    if len(summary) > SUMMARY_PUBLIC_MAX:
        issues.append("summary_too_long")
    if _contains_forbidden_marker(summary):
        issues.append("summary_forbidden_marker")
    for key in ("issue_blocks", "top_3_issues", "recommended_actions"):
        items = audit.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            joined = " ".join(str(value or "") for value in item.values())
            if _contains_forbidden_marker(joined):
                issues.append(f"{key}_forbidden_marker")
                break
    photo_confidence = detect_photo_signal_confidence(audit)
    if photo_confidence != "confirmed":
        lowered_summary = summary.lower().replace("ё", "е")
        hard_photo_claims = ("фотографий нет", "всего 1 фото", "фото 1", "только одно фото")
        if any(claim in lowered_summary for claim in hard_photo_claims):
            issues.append("photo_hard_claim_without_confidence")
    audit_profile = str(audit.get("audit_profile") or "").strip().lower()
    if audit_profile not in {"medical", "hospitality"} and "пациент" in summary.lower().replace("ё", "е"):
        issues.append("wrong_actor_for_profile")
    return {
        "status": "pass" if not issues else "rewritten",
        "issues": sorted(set(issues)),
    }


def _sanitize_uncertain_photo_issue(item: dict[str, Any], *, photo_confidence: str) -> dict[str, Any]:
    if photo_confidence == "confirmed":
        return item
    next_item = copy.deepcopy(item)
    item_id = str(next_item.get("id") or next_item.get("code") or "").strip().lower()
    joined = " ".join(str(next_item.get(key) or "") for key in ("title", "problem", "description", "evidence", "fix"))
    lowered = joined.lower().replace("ё", "е")
    has_hard_photo_count = bool(
        re.search(r"фото\s+в\s+карточке\s*:\s*\d+", lowered)
        or "всего 1 фото" in lowered
        or "только одно фото" in lowered
        or "фото 1" in lowered
    )
    if item_id not in {"photo_story_gap", "visual_no_photos", "photos_gap"} and not has_hard_photo_count:
        return next_item
    next_item["evidence"] = (
        "По собранным данным визуальный блок требует ручной проверки: важно убедиться, "
        "что в карточке видны вход, ресепшен, кабинеты, оборудование и специалисты."
    )
    return next_item


def apply_audit_editorial_pass(audit: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(audit if isinstance(audit, dict) else {})
    audit_profile = str(output.get("audit_profile") or "").strip().lower()
    output["photo_signal_confidence"] = detect_photo_signal_confidence(output)
    photo_confidence = str(output.get("photo_signal_confidence") or "").strip().lower()

    for key in ("summary_text", "why_now"):
        if key in output:
            output[key] = normalize_audit_text(output.get(key), audit_profile=audit_profile)

    for list_key in ("issue_blocks", "top_3_issues", "recommended_actions", "findings"):
        items = output.get(list_key)
        if not isinstance(items, list):
            continue
        next_items: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                next_items.append(item)
                continue
            next_item = copy.deepcopy(item)
            for text_key in ("title", "problem", "description", "evidence", "impact", "fix"):
                if text_key in next_item:
                    next_item[text_key] = normalize_audit_text(next_item.get(text_key), audit_profile=audit_profile)
            next_item = _sanitize_uncertain_photo_issue(next_item, photo_confidence=photo_confidence)
            next_items.append(next_item)
        output[list_key] = next_items

    for list_key in (
        "best_fit_customer_profile",
        "weak_fit_customer_profile",
        "best_fit_guest_profile",
        "weak_fit_guest_profile",
        "search_intents_to_target",
        "photo_shots_missing",
        "positioning_focus",
    ):
        items = output.get(list_key)
        if isinstance(items, list):
            output[list_key] = [normalize_audit_text(item, audit_profile=audit_profile) for item in items]

    gate_before = audit_quality_gate(output)
    if gate_before["issues"] or output.get("business_name") or not str(output.get("summary_text") or "").strip():
        output["summary_text"] = build_editorial_summary(output, max_length=SUMMARY_PUBLIC_MAX)

    variants = build_summary_variants(output)
    output.update(variants)
    output["editorial_quality_gate"] = audit_quality_gate(output)
    return output


def clean_public_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [clean_public_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in TECHNICAL_PUBLIC_KEYS:
            continue
        result[key] = clean_public_payload(item)
    return result
