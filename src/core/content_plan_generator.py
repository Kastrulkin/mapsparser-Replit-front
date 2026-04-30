from __future__ import annotations

from datetime import date, timedelta
from typing import Any


_CONTENT_TYPE_TITLES = {
    "seo": "SEO-запрос",
    "service": "Услуга",
    "sales": "Продажи",
    "audit": "Улучшение карточки",
    "seasonal": "Сезонный повод",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _weekly_frequency_by_density(density: str) -> int:
    normalized = _safe_text(density).lower()
    if normalized == "light":
        return 1
    if normalized == "active":
        return 3
    return 2


def _content_mix_value(content_mix: dict[str, Any], key: str, fallback: bool = True) -> bool:
    value = content_mix.get(key) if isinstance(content_mix, dict) else None
    if value is None:
        return fallback
    return bool(value)


def _quoted(value: str) -> str:
    clean = _safe_text(value)
    return f"«{clean}»" if clean else ""


def _city_suffix(city: str) -> str:
    clean = _safe_text(city)
    return f" в {clean}" if clean else ""


def _service_goal(service_name: str, city: str) -> str:
    location = _city_suffix(city)
    return (
        f"Помочь клиенту быстрее выбрать услугу {_quoted(service_name)}{location} "
        "и дать понятный повод записаться без перехода в долгий поиск."
    )


def _service_cta(service_name: str) -> str:
    return (
        f"Покажите, для кого подходит {_quoted(service_name)}, что входит в услугу "
        "и как записаться через карточку."
    )


def _seo_goal(keyword_text: str, city: str) -> str:
    location = _city_suffix(city)
    return (
        f"Закрыть локальный сценарий спроса по запросу {_quoted(keyword_text)}{location} "
        "и объяснить, почему эту карточку стоит открыть и сравнить первой."
    )


def _seo_cta(keyword_text: str) -> str:
    return (
        f"Свяжите запрос {_quoted(keyword_text)} с конкретной услугой, преимуществом "
        "или понятным следующим действием."
    )


def _sales_goal(sale_name: str) -> str:
    return (
        f"Опирайтесь на уже подтверждённый интерес к {_quoted(sale_name)}: "
        "покажите, что это не случайная тема, а реальный повторяющийся спрос."
    )


def _sales_cta(sale_name: str) -> str:
    return (
        f"Сделайте акцент на том, почему {_quoted(sale_name)} выбирают сейчас "
        "и как быстро получить эту услугу или товар."
    )


def _audit_goal(theme: str) -> str:
    return (
        f"Закрыть слабое место карточки вокруг темы {_quoted(theme)} "
        "и снизить сомнения перед звонком, визитом или записью."
    )


def _audit_cta(theme: str) -> str:
    return (
        f"Сделайте публикацию, которая прямо отвечает на пробел по теме {_quoted(theme)} "
        "и усиливает доверие к карточке."
    )


def _seasonal_goal(topic: str) -> str:
    return (
        f"Дать карточке регулярный живой повод для обновления через тему {_quoted(topic)}, "
        "чтобы бизнес не выглядел заброшенным."
    )


def _seasonal_cta(topic: str) -> str:
    return (
        f"Используйте тему {_quoted(topic)} как короткий актуальный повод: подборка, "
        "обновление, акция или объяснение текущего спроса."
    )


def _fallback_goal(business_name: str) -> str:
    return (
        f"Показать, что карточка {_quoted(business_name)} ведётся регулярно, "
        "даже если данных для более точной темы пока мало."
    )


def build_content_plan_skeleton(
    context: dict[str, Any],
    *,
    period_days: int,
    density: str,
    content_mix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content_mix = content_mix if isinstance(content_mix, dict) else {}
    period_days = 30 if int(period_days or 30) not in {30, 60, 90} else int(period_days or 30)
    frequency_per_week = _weekly_frequency_by_density(density)
    items_target = max(4, round(period_days / 7 * frequency_per_week))
    period_start = date.today()
    period_end = period_start + timedelta(days=period_days - 1)

    candidates: list[dict[str, Any]] = []
    services = context.get("services") if isinstance(context.get("services"), list) else []
    seo_keywords = context.get("seo_keywords") if isinstance(context.get("seo_keywords"), list) else []
    sales_signals = context.get("sales_signals") if isinstance(context.get("sales_signals"), list) else []
    audit_signals = context.get("audit_signals") if isinstance(context.get("audit_signals"), list) else []
    business = context.get("business") if isinstance(context.get("business"), dict) else {}
    business_name = _safe_text(business.get("name")) or "Бизнес"
    city = _safe_text(business.get("city"))

    if _content_mix_value(content_mix, "services"):
        for service in services[:10]:
            service_name = _safe_text(service.get("name"))
            if not service_name:
                continue
            candidates.append(
                {
                    "content_type": "service",
                    "theme": f"Подсветить услугу: {service_name}",
                    "goal": _service_goal(service_name, city),
                    "source_kind": "service",
                    "source_ref": service_name,
                    "service_id": _safe_text(service.get("id")),
                    "cta_hint": _service_cta(service_name),
                }
            )

    if _content_mix_value(content_mix, "seo"):
        for keyword in seo_keywords[:10]:
            keyword_text = _safe_text(keyword.get("keyword"))
            if not keyword_text:
                continue
            theme_suffix = f" в {city}" if city else ""
            candidates.append(
                {
                    "content_type": "seo",
                    "theme": f"Ответить на спрос: {keyword_text}{theme_suffix}",
                    "goal": _seo_goal(keyword_text, city),
                    "source_kind": "seo_keyword",
                    "source_ref": keyword_text,
                    "seo_keyword": keyword_text,
                    "cta_hint": _seo_cta(keyword_text),
                }
            )

    if _content_mix_value(content_mix, "sales"):
        for sale in sales_signals[:8]:
            sale_name = _safe_text(sale.get("title") or sale.get("label") or sale.get("service_name"))
            if not sale_name:
                continue
            candidates.append(
                {
                    "content_type": "sales",
                    "theme": f"Продвижение на основе продаж: {sale_name}",
                    "goal": _sales_goal(sale_name),
                    "source_kind": "transaction",
                    "source_ref": sale_name,
                    "transaction_id": _safe_text(sale.get("transaction_id")),
                    "cta_hint": _sales_cta(sale_name),
                }
            )

    if _content_mix_value(content_mix, "audit"):
        for signal in audit_signals[:8]:
            signal_title = _safe_text(signal.get("title"))
            signal_problem = _safe_text(signal.get("problem"))
            if not signal_title and not signal_problem:
                continue
            theme = signal_title or signal_problem
            candidates.append(
                {
                    "content_type": "audit",
                    "theme": f"Закрыть слабую зону карточки: {theme}",
                    "goal": _audit_goal(theme),
                    "source_kind": "audit_signal",
                    "source_ref": theme,
                    "cta_hint": _audit_cta(theme),
                }
            )

    if _content_mix_value(content_mix, "seasonal"):
        seasonal_topics = [
            f"Сезонная подборка для {business_name}",
            f"Что выбрать сейчас: предложения {business_name}",
            f"Новая причина зайти в {business_name}",
        ]
        for topic in seasonal_topics:
            candidates.append(
                {
                    "content_type": "seasonal",
                    "theme": topic,
                    "goal": _seasonal_goal(topic),
                    "source_kind": "seasonal",
                    "source_ref": topic,
                    "cta_hint": _seasonal_cta(topic),
                }
            )

    if not candidates:
        candidates.append(
            {
                "content_type": "seasonal",
                "theme": f"Обновление карточки {business_name}",
                "goal": _fallback_goal(business_name),
                "source_kind": "fallback",
                "source_ref": business_name,
                "cta_hint": "Дать понятный повод клиенту открыть карточку и связаться.",
            }
        )

    selected_items: list[dict[str, Any]] = []
    step_days = max(3, round(period_days / max(items_target, 1)))
    current_date = period_start
    candidate_index = 0
    while len(selected_items) < items_target:
        candidate = candidates[candidate_index % len(candidates)]
        scheduled_for = current_date.isoformat()
        selected_items.append(
            {
                "scheduled_for": scheduled_for,
                "content_type": candidate.get("content_type") or "news",
                "theme": candidate.get("theme") or "Тема публикации",
                "goal": candidate.get("goal") or "",
                "source_kind": candidate.get("source_kind") or "",
                "source_ref": candidate.get("source_ref") or "",
                "seo_keyword": candidate.get("seo_keyword") or "",
                "service_id": candidate.get("service_id") or "",
                "transaction_id": candidate.get("transaction_id") or "",
                "cta_hint": candidate.get("cta_hint") or "",
            }
        )
        current_date = min(period_end, current_date + timedelta(days=step_days))
        candidate_index += 1
        if current_date >= period_end and len(selected_items) < items_target:
            current_date = period_start + timedelta(days=min(candidate_index, period_days - 1))

    weekly_summary: dict[str, list[dict[str, Any]]] = {}
    for item in selected_items:
        item_date = date.fromisoformat(item["scheduled_for"])
        week_key = f"{item_date.isocalendar().year}-W{item_date.isocalendar().week:02d}"
        weekly_summary.setdefault(week_key, []).append(item)

    return {
        "title": f"Контент-план на {period_days} дней",
        "period_days": period_days,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "items": selected_items,
        "weekly_groups": weekly_summary,
        "meta": {
            "density": density,
            "items_target": items_target,
            "sources_used": sorted({
                _safe_text(item.get("source_kind"))
                for item in selected_items
                if _safe_text(item.get("source_kind"))
            }),
            "content_types_used": sorted({
                _safe_text(item.get("content_type"))
                for item in selected_items
                if _safe_text(item.get("content_type"))
            }),
        },
    }
