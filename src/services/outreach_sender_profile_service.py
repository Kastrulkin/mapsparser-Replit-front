"""Completeness rules for evidence-safe founder-led sender profiles."""

from __future__ import annotations

from typing import Any


def evaluate_sender_profile_completeness(
    profile: dict[str, Any] | None,
    *,
    workstream_type: str,
    business_service_count: int | None = None,
) -> dict[str, Any]:
    """Return a user-facing, evidence-safe readiness checklist for one sender."""
    sender = dict(profile or {})
    context = (
        sender.get("outreach_context_json")
        if isinstance(sender.get("outreach_context_json"), dict)
        else {}
    )

    def approved_facts(value: Any) -> list[str]:
        items = value if isinstance(value, list) else []
        result: list[str] = []
        for item in items:
            if isinstance(item, dict):
                status = str(item.get("status") or "approved").strip().lower()
                if status not in {"approved", "observed"}:
                    continue
                text = str(
                    item.get("fact") or item.get("text") or item.get("result")
                    or item.get("title") or ""
                ).strip()
            else:
                text = str(item or "").strip()
            if text:
                result.append(text)
        return result

    proof = approved_facts(sender.get("proof_points_json")) + approved_facts(
        sender.get("verified_cases_json")
    )
    offers = approved_facts(sender.get("allowed_offers_json"))
    voice_examples = approved_facts(sender.get("voice_examples_json"))
    forbidden_claims = approved_facts(sender.get("forbidden_claims_json"))
    segments = context.get("segments") if isinstance(context.get("segments"), list) else []
    partner_types = (
        context.get("desired_partner_types")
        if isinstance(context.get("desired_partner_types"), list)
        else []
    )
    competence_status = str(
        context.get("competence_story_status") or "approved"
    ).strip().lower()
    approved_story = bool(
        str(sender.get("competence_story") or "").strip()
        and competence_status in {"approved", "observed"}
    )

    checks: list[tuple[str, str, str, bool]] = [
        ("sender_identity", "Отправитель", "Укажите имя, роль и компанию", bool(
            str(sender.get("display_name") or "").strip()
            and str(sender.get("role_title") or "").strip()
            and str(sender.get("company_name") or "").strip()
        )),
        ("sender_experience", "Опыт", "Добавьте подтверждённый опыт основателя или команды", approved_story or bool(proof)),
        ("sender_proof", "Кейс или факт", "Добавьте хотя бы один подтверждённый кейс или факт", bool(proof)),
        ("sender_audience", "Аудитория", "Опишите аудиторию или сегменты бизнеса", bool(
            str(context.get("audience") or "").strip()
            or any(str(item or "").strip() for item in segments)
        )),
        ("sender_offer", "Предложение", "Добавьте хотя бы одно допустимое предложение", bool(offers)),
        ("sender_voice", "Голос", "Добавьте пример сообщения вашим живым голосом", bool(voice_examples)),
        ("sender_forbidden_claims", "Ограничения", "Укажите, что LocalOS нельзя утверждать", bool(forbidden_claims)),
    ]
    if workstream_type == "client_partnership":
        checks.extend([
            (
                "sender_services",
                "Услуги бизнеса",
                "Добавьте услуги бизнеса в LocalOS",
                business_service_count is None or business_service_count > 0,
            ),
            (
                "desired_partner_types",
                "Типы партнёров",
                "Укажите желаемые типы партнёров",
                any(str(item or "").strip() for item in partner_types),
            ),
        ])

    items = [
        {"code": code, "title": title, "label": label, "complete": complete}
        for code, title, label, complete in checks
    ]
    missing_items = [
        {"code": item["code"], "label": item["label"]}
        for item in items
        if not item["complete"]
    ]
    completed_count = len(items) - len(missing_items)
    return {
        "ready": not missing_items,
        "status": "ready" if not missing_items else "draft",
        "completed_count": completed_count,
        "required_count": len(items),
        "items": items,
        "missing_items": missing_items,
    }
