"""Versioned, evidence-bound templates for LocalOS founder outreach.

Templates are the preferred writing path, not an approval shortcut.  A
template is selected only when its required public evidence is present and
current.  Callers must still run the normal human-language and quality gates.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


TEMPLATE_LIBRARY_VERSION = "localos_outreach_templates_v4"

OUTREACH_TEMPLATES = (
    {
        "key": "weak_map_rating_beauty_v1",
        "label": "Низкий рейтинг на картах",
        "version": 1,
        "angles": ("signal",),
        "pain_key": "marketing_and_clients",
        "required_evidence": ("current_map_rating", "beauty_segment"),
        "question_policy": "single_cta",
    },
    {
        "key": "crm_completed_service_content_v1",
        "label": "CRM и контент без ручной работы",
        "version": 1,
        "angles": ("crm_content", "content_operations"),
        "pain_key": "operations_and_burnout",
        "required_evidence": ("confirmed_crm_provider",),
        "question_policy": "single_cta",
    },
    {
        "key": "average_ticket_service_matrix_v1",
        "label": "Допродажи и средний чек",
        "version": 1,
        "angles": ("average_ticket", "crm_growth"),
        "pain_key": "pricing_and_average_ticket",
        "required_evidence": ("confirmed_crm_or_pricelist", "beauty_or_medical_segment"),
        "question_policy": "diagnostic_plus_cta",
    },
    {
        "key": "local_partnership_acquisition_v1",
        "label": "Новые клиенты через партнёрства",
        "version": 1,
        "angles": ("integrated_system",),
        "pain_key": "marketing_and_clients",
        "required_evidence": ("current_service_or_event_signal",),
        "question_policy": "single_cta",
    },
    {
        "key": "unanswered_review_response_v1",
        "label": "Отзывы без ответа",
        "version": 1,
        "angles": ("signal", "reviews_service"),
        "pain_key": "reviews_and_service",
        "required_evidence": ("current_unanswered_review",),
        "question_policy": "single_cta",
    },
    {
        "key": "map_content_gap_v3",
        "label": "Нет новостей в карточке",
        "version": 3,
        "angles": ("signal", "content_operations"),
        "pain_key": "marketing_and_clients",
        "required_evidence": ("current_map_content_gap",),
        "question_policy": "single_cta",
    },
    {
        "key": "map_service_price_coverage_v3",
        "label": "Услуги и цены в карточке",
        "version": 3,
        "angles": ("content_operations", "audit_step"),
        "pain_key": "marketing_and_clients",
        "required_evidence": ("current_map_service_price_coverage",),
        "question_policy": "single_cta",
    },
)

_TEMPLATE_BY_KEY = {item["key"]: item for item in OUTREACH_TEMPLATES}
_CURRENT_FRESHNESS = {"current", "current_snapshot", "fresh", "live"}
_BEAUTY_MEDICAL_MARKERS = (
    "beauty",
    "clinic",
    "medical",
    "private_beauty_specialist",
    "барбер",
    "клиник",
    "космет",
    "медиц",
    "салон красоты",
    "студия красоты",
    "эпиляц",
)
_RECIPIENT_GENITIVE_OVERRIDES = {
    "Кожно-венерологический диспансер № 7": "Кожно-венерологического диспансера № 7",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").replace("—", "-").replace("«", '"').replace("»", '"').split())


def _service_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "услуга"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "услуги"
    return "услуг"


def _identity_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        _text(candidate.get(key))
        for key in ("recipient_segment", "recipient_category", "recipient", "observed_fact")
    ).lower()


def _is_beauty_or_medical(candidate: dict[str, Any]) -> bool:
    identity = _identity_text(candidate)
    return any(marker in identity for marker in _BEAUTY_MEDICAL_MARKERS)


def _is_current_and_sourced(candidate: dict[str, Any]) -> bool:
    freshness = _text(candidate.get("freshness")).lower()
    return bool(
        _text(candidate.get("source_url"))
        and _text(candidate.get("evidence_status")) in {"approved", "observed"}
        and freshness in _CURRENT_FRESHNESS
    )


def _rating(candidate: dict[str, Any]) -> float | None:
    observed = _text(candidate.get("observed_fact"))
    match = re.search(
        r"рейтинг(?:\s*[-:]|\s+)?\s*([0-9]+(?:[.,][0-9]+)?)",
        observed,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _crm_provider(candidate: dict[str, Any]) -> str:
    return _text(candidate.get("crm_provider_name") or candidate.get("crm_type"))


def _signal_combo(candidate: dict[str, Any]) -> str:
    return _text(candidate.get("signal_combo")).lower()


def _matches(template_key: str, angle: str, candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    template = _TEMPLATE_BY_KEY[template_key]
    reasons: list[str] = []
    if _text(angle) not in template["angles"]:
        reasons.append("angle_not_supported")
    if not _is_current_and_sourced(candidate):
        reasons.append("current_source_required")

    signal_combo = _signal_combo(candidate)
    evidence_kind = _text(candidate.get("evidence_kind")).lower()
    if template_key == "weak_map_rating_beauty_v1":
        rating = _rating(candidate)
        if rating is None or rating > 4.4:
            reasons.append("low_map_rating_required")
        if not _is_beauty_or_medical(candidate):
            reasons.append("beauty_segment_required")
    elif template_key == "crm_completed_service_content_v1":
        if not _crm_provider(candidate):
            reasons.append("confirmed_crm_provider_required")
    elif template_key == "average_ticket_service_matrix_v1":
        evidence_kind = _text(candidate.get("evidence_kind")).lower()
        if not _crm_provider(candidate) and evidence_kind not in {
            "price_list",
            "pricelist",
            "website_pricing",
            "service_catalog",
        }:
            reasons.append("crm_or_pricelist_required")
        if not _is_beauty_or_medical(candidate):
            reasons.append("beauty_or_medical_segment_required")
    elif template_key == "local_partnership_acquisition_v1":
        if signal_combo not in {"recent_new_service_announcement", "recent_event_announcement"} and evidence_kind not in {
            "new_service", "service_launch", "event", "new_equipment",
        }:
            reasons.append("service_or_event_signal_required")
    elif template_key == "unanswered_review_response_v1":
        fact = _text(candidate.get("observed_fact")).lower()
        if signal_combo != "active_social_with_unanswered_negative_review" and not (
            "отзыв" in fact and "без ответ" in fact
        ):
            reasons.append("unanswered_review_required")
    elif template_key == "map_content_gap_v3":
        fact = _text(candidate.get("observed_fact")).lower()
        if signal_combo not in {
            "active_external_channels_with_incomplete_map_profile",
            "map_content_gap",
        } and not any(
            marker in fact for marker in ("нет новостей", "новости отсутствуют", "карточка не заполнена")
        ):
            reasons.append("map_content_gap_required")
    elif template_key == "map_service_price_coverage_v3":
        fact = _text(candidate.get("observed_fact")).lower()
        if _text(candidate.get("evidence_kind")).lower() not in {"map_issue", "map_services"} or not (
            "услуг" in fact and "цен" in fact
        ):
            reasons.append("map_service_price_coverage_required")
    return not reasons, reasons


def select_outreach_template(
    angle: str,
    candidate: dict[str, Any],
    *,
    used_template_keys: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Choose the first fully supported template or return an auditable fallback."""

    used = set(used_template_keys or ())
    requested = _text(candidate.get("outreach_template_key"))
    ordered = (
        [_TEMPLATE_BY_KEY[requested]]
        if requested in _TEMPLATE_BY_KEY
        else list(OUTREACH_TEMPLATES)
    )
    rejected: list[dict[str, Any]] = []
    for template in ordered:
        if template["key"] in used:
            rejected.append({"key": template["key"], "reasons": ["already_used_in_sequence"]})
            continue
        matches, reasons = _matches(template["key"], angle, candidate)
        if matches:
            return {
                "status": "selected",
                "library_version": TEMPLATE_LIBRARY_VERSION,
                "key": template["key"],
                "version": template["version"],
                "label": template["label"],
                "pain_key": template["pain_key"],
                "question_policy": template["question_policy"],
                "required_evidence": list(template["required_evidence"]),
                "rejected": rejected,
            }
        rejected.append({"key": template["key"], "reasons": reasons})
    return {
        "status": "individual_copy_required",
        "library_version": TEMPLATE_LIBRARY_VERSION,
        "key": None,
        "version": None,
        "label": None,
        "pain_key": None,
        "question_policy": None,
        "required_evidence": [],
        "rejected": rejected,
    }


def _sender_identity(candidate: dict[str, Any]) -> str:
    sender = _text(candidate.get("sender")) or "Александр Демьянов"
    role = _text(candidate.get("sender_role")) or "основатель LocalOS"
    return f"{sender}, {role}"


def attach_public_audit_link(text: str, candidate: dict[str, Any]) -> str:
    """Insert the canonical LocalOS audit before the final CTA."""

    if candidate.get("include_public_audit_link") is not True:
        return text
    audit_url = _text(candidate.get("public_audit_url"))
    parsed = urlparse(audit_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"localos.pro", "www.localos.pro"}
        or not parsed.path.strip("/")
        or audit_url in text
    ):
        return text
    paragraphs = text.split("\n\n")
    audit_paragraph = (
        "Мы подготовили аудит карточки на картах, "
        f"сможете поправить сами: {audit_url}"
    )
    if len(paragraphs) < 2:
        return f"{text}\n\n{audit_paragraph}"
    paragraphs.insert(-1, audit_paragraph)
    return "\n\n".join(paragraphs)


def _render_outreach_template_body(
    selection: dict[str, Any],
    candidate: dict[str, Any],
) -> str | None:
    """Render selected copy.  It still requires the normal quality gate."""

    key = _text(selection.get("key"))
    if selection.get("status") != "selected" or key not in _TEMPLATE_BY_KEY:
        return None
    recipient = _text(candidate.get("recipient")) or "вашего бизнеса"
    identity = _sender_identity(candidate)

    if key == "weak_map_rating_beauty_v1":
        rating = _rating(candidate)
        rating_text = (f"{rating:.1f}" if rating is not None else "").replace(".", ",")
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"В карточке {recipient} сейчас рейтинг {rating_text} на Яндекс Картах. "
            "С таким рейтингом карточка может терять клиентов из карт.\n\n"
            "LocalOS помогает исправить ситуацию: отслеживает отзывы, готовит ответы и подсказывает, "
            "что изменить в карточке. Для одного салона красоты мы с нуля привлекли 10 клиентов с карт.\n\n"
            "Стоимость - от 1200 рублей в месяц.\n\n"
            "Вам может быть это интересно?"
        )
    if key == "crm_completed_service_content_v1":
        provider = _crm_provider(candidate)
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"Вижу, вы пользуетесь {provider}.\n\n"
            f"На основе выгрузки из {provider} LocalOS автоматически подготовит черновики постов о выполненных услугах "
            "для Telegram, VK, Яндекс Карт и других площадок.\n\n"
            "Вам было бы интересно сэкономить время на ведении соцсетей?"
        )
    if key == "average_ticket_service_matrix_v1":
        observation = _text(candidate.get("observed_fact")).rstrip(" .") + "."
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"{observation}\n\n"
            "Вам знакома проблема: услуг много, а средний чек всё равно маленький?\n\n"
            "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, подготовит подсказки для администратора "
            "и поможет отследить результат.\n\n"
            "Вам было бы интересно увеличить средний чек?"
        )
    if key == "local_partnership_acquisition_v1":
        observation = _text(candidate.get("observed_fact")).rstrip(" .") + "."
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"{observation}\n\n"
            "Такая услуга может стать первым знакомством с компанией для клиентов бизнесов с похожей аудиторией.\n\n"
            "LocalOS подготовит список местных бизнесов со смежной аудиторией и черновик предложения о партнёрстве. "
            "Вы сами решите, кому его отправить.\n\n"
            "Вам было бы интересно находить новых клиентов через партнёрства?"
        )
    if key == "unanswered_review_response_v1":
        observation = _text(candidate.get("observed_fact")).rstrip(" .") + "."
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"{observation}\n\n"
            "LocalOS отслеживает новые отзывы, группирует темы и готовит черновики ответов. Сотруднику остаётся проверить и опубликовать ответ.\n\n"
            "Вам было бы интересно сэкономить время на работе с отзывами?"
        )
    if key == "map_content_gap_v3":
        observation = _text(candidate.get("observed_fact")).rstrip(" .") + "."
        if "нет новостей" in observation.lower() and "яндекс картах" not in observation.lower():
            observation = f"В карточке {recipient} на Яндекс Картах нет новостей."
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"{observation}\n\n"
            "Новости показывают клиентам актуальные услуги и дают ещё один повод обратиться из карт.\n\n"
            "LocalOS подготовит отдельные черновики новостей для Telegram, VK и Яндекс Карт. "
            "Сотруднику останется проверить и опубликовать текст.\n\n"
            "Вам было бы интересно привлекать больше клиентов онлайн?"
        )
    if key == "map_service_price_coverage_v3":
        observation = _text(candidate.get("observed_fact")).rstrip(" .") + "."
        counts = re.search(
            r"всего услуг\s*-\s*(\d+);\s*с ценой\s*-\s*(\d+)",
            observation,
            flags=re.IGNORECASE,
        )
        if counts:
            recipient_genitive = _RECIPIENT_GENITIVE_OVERRIDES.get(recipient)
            if recipient_genitive:
                observation = (
                    f"Вижу, что в карточке {recipient_genitive} на Яндекс Картах есть "
                    f"{counts.group(1)} {_service_word(int(counts.group(1)))}, но цена указана "
                    f"только для {counts.group(2)} из них."
                )
            else:
                observation = (
                    f"Вижу, что в карточке компании {recipient} на Яндекс Картах есть "
                    f"{counts.group(1)} {_service_word(int(counts.group(1)))}, но цена указана "
                    f"только для {counts.group(2)} из них."
                )
        return (
            f"Здравствуйте! Я {identity}.\n\n"
            f"{observation}\n\n"
            "Без цен клиенту сложнее выбрать и записаться, поэтому компания может недополучать обращения с карт.\n\n"
            "LocalOS поможет исправить карточку: сверит услуги и цены и подготовит изменения. "
            "Для одного салона красоты мы с нуля привлекли 10 клиентов с карт.\n\n"
            "Стоимость - от 1200 рублей в месяц.\n\n"
            "Вам может быть это интересно?"
        )
    return None


def render_outreach_template(
    selection: dict[str, Any],
    candidate: dict[str, Any],
) -> str | None:
    """Render selected copy and optionally attach the first-touch audit."""

    body = _render_outreach_template_body(selection, candidate)
    return attach_public_audit_link(body, candidate) if body else None


def template_allows_two_questions(
    text: str,
    angle: str,
    candidate: dict[str, Any],
) -> bool:
    """Allow only the exact approved diagnostic + final CTA template shape."""

    selection = select_outreach_template(angle, candidate)
    if selection.get("key") != "average_ticket_service_matrix_v1":
        return False
    diagnostic = "Вам знакома проблема: услуг много, а средний чек всё равно маленький?"
    final_cta = "Вам было бы интересно увеличить средний чек?"
    return bool(
        text.count("?") == 2
        and diagnostic in text
        and final_cta in text
        and text.rstrip().endswith(final_cta)
    )


def template_copy_matches(
    text: str,
    angle: str,
    candidate: dict[str, Any],
) -> bool:
    """Prove that the reviewed bytes are the selected versioned template."""

    selection = select_outreach_template(angle, candidate)
    expected = render_outreach_template(selection, candidate)
    return bool(expected and _text(expected) == _text(text))
