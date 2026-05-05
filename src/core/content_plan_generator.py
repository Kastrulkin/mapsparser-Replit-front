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


def _clean_audit_signal_text(value: str) -> str:
    text = _safe_text(value)
    prefixes = [
        "Недопокрытый поисковый сценарий:",
        "Закрыть слабую зону карточки:",
        "Закрыть слабое место карточки:",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip(" .:;\"'«»")
                changed = True
    return text


def _search_intent_theme(intent: str) -> str:
    clean = _clean_audit_signal_text(intent)
    normalized = clean.lower()
    if any(marker in normalized for marker in ("цен", "стоимост", "прайс", "пример", "работ", "фото")):
        return "Показать цену и примеры работ"
    if any(marker in normalized for marker in ("рядом", "поблизости", "около", "возле")):
        return f"Почему выбрать вас по запросу {_quoted(clean)}" if clean else "Объяснить, почему выбрать вас рядом"
    if clean:
        return f"Ответить на запрос клиента: {clean}"
    return "Ответить на важный поисковый запрос"


def _audit_theme(signal: dict[str, Any]) -> str:
    section = _safe_text(signal.get("section")).lower()
    signal_id = _safe_text(signal.get("id")).lower()
    evidence = _safe_text(signal.get("evidence"))
    title = _safe_text(signal.get("title"))
    problem = _safe_text(signal.get("problem"))
    if section == "search" or "search_intent:" in signal_id:
        return _search_intent_theme(evidence or title or problem)
    clean_title = _clean_audit_signal_text(title)
    if clean_title:
        return clean_title
    clean_problem = _clean_audit_signal_text(problem)
    if clean_problem:
        return clean_problem
    return "Усилить карточку перед выбором клиента"


def _audit_goal(signal: dict[str, Any]) -> str:
    section = _safe_text(signal.get("section")).lower()
    signal_id = _safe_text(signal.get("id")).lower()
    evidence = _clean_audit_signal_text(_safe_text(signal.get("evidence")))
    problem = _clean_audit_signal_text(_safe_text(signal.get("problem")))
    if section == "search" or "search_intent:" in signal_id:
        if any(marker in evidence.lower() for marker in ("цен", "стоимост", "прайс", "пример", "работ", "фото")):
            return (
                "Клиенту проще записаться, если в карточке видно цену, результат и понятный следующий шаг. "
                "Публикация должна убрать сомнения перед звонком или записью."
            )
        if evidence:
            return (
                f"Дать понятный ответ на запрос {_quoted(evidence)}: что вы предлагаете, почему это удобно "
                "и как быстро связаться с бизнесом."
            )
        return "Дать клиенту понятный ответ на поисковый запрос и привести его к звонку, маршруту или записи."
    if problem:
        theme = _audit_theme(signal)
        if theme:
            return f"Усилить блок {_quoted(theme)} и объяснить клиенту простым языком: {problem}"
        return f"Объяснить клиенту важный пробел карточки простым языком: {problem}"
    return "Сделать карточку понятнее и убедительнее перед звонком, визитом или записью."


def _audit_cta(signal: dict[str, Any]) -> str:
    section = _safe_text(signal.get("section")).lower()
    signal_id = _safe_text(signal.get("id")).lower()
    evidence = _clean_audit_signal_text(_safe_text(signal.get("evidence")))
    if section == "search" or "search_intent:" in signal_id:
        if any(marker in evidence.lower() for marker in ("цен", "стоимост", "прайс", "пример", "работ", "фото")):
            return "Покажите цену, пример результата и один простой способ записаться."
        if evidence:
            return f"Свяжите запрос {_quoted(evidence)} с конкретной услугой, выгодой и действием."
    return "Сделайте короткую публикацию, которая закрывает пробел карточки и усиливает доверие."


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


def _priority_weight(priority: str) -> int:
    normalized = _safe_text(priority).lower()
    if normalized == "critical":
        return 130
    if normalized == "high":
        return 110
    if normalized == "medium":
        return 80
    if normalized == "low":
        return 50
    return 60


def _service_strength(service: dict[str, Any]) -> int:
    score = 40
    if _safe_text(service.get("price")):
        score += 18
    if _safe_text(service.get("category")):
        score += 12
    if _safe_text(service.get("description")):
        score += 10
    return score


def _seo_strength(keyword: dict[str, Any]) -> int:
    views = int(keyword.get("views") or 0)
    score = 55
    if views >= 5000:
        score += 45
    elif views >= 2000:
        score += 35
    elif views >= 800:
        score += 25
    elif views >= 200:
        score += 15
    elif views > 0:
        score += 8
    if _safe_text(keyword.get("category")):
        score += 6
    return score


def _sales_strength(sale: dict[str, Any]) -> int:
    amount = float(sale.get("amount") or 0)
    score = 50
    if amount >= 15000:
        score += 35
    elif amount >= 7000:
        score += 28
    elif amount >= 3000:
        score += 18
    elif amount > 0:
        score += 10
    if _safe_text(sale.get("transaction_date")):
        score += 6
    return score


def _audit_strength(signal: dict[str, Any]) -> int:
    score = _priority_weight(_safe_text(signal.get("priority")))
    section = _safe_text(signal.get("section")).lower()
    signal_id = _safe_text(signal.get("id")).lower()
    evidence = _safe_text(signal.get("evidence"))
    if section == "search":
        score += 18
    if section == "reviews":
        score += 12
    if "search_intent:" in signal_id:
        score += 20
    if evidence:
        score += 4
    return score


def _seasonal_strength(topic: str) -> int:
    if "сезон" in _safe_text(topic).lower():
        return 38
    return 34


def _recent_content_blob(context: dict[str, Any]) -> str:
    recent_news = context.get("recent_news") if isinstance(context.get("recent_news"), list) else []
    return " ".join(
        _safe_text(item.get("text")).lower()
        for item in recent_news
        if isinstance(item, dict) and _safe_text(item.get("text"))
    )


def _is_topic_covered(topic: str, recent_blob: str) -> bool:
    clean = _safe_text(topic).lower()
    if not clean or not recent_blob:
        return False
    words = [
        word
        for word in clean.replace(",", " ").replace(".", " ").split()
        if len(word) >= 4
    ]
    if not words:
        return clean in recent_blob
    matched = sum(1 for word in words if word in recent_blob)
    required_matches = 1 if len(words) == 1 else max(2, round(len(words) * 0.6))
    return matched >= required_matches


def _undercovered_bonus(topic: str, recent_blob: str) -> int:
    if not _safe_text(topic):
        return 0
    return 16 if not _is_topic_covered(topic, recent_blob) else -8


def _weak_zone_bonus(signal: dict[str, Any]) -> int:
    priority = _safe_text(signal.get("priority")).lower()
    section = _safe_text(signal.get("section")).lower()
    signal_id = _safe_text(signal.get("id")).lower()
    score = 0
    if priority in {"critical", "high"}:
        score += 14
    if section in {"search", "reviews", "photos", "services"}:
        score += 8
    if "search_intent:" in signal_id:
        score += 12
    return score


def _ranking_reason(label: str, score: int) -> dict[str, Any]:
    return {
        "label": label,
        "score": int(score or 0),
    }


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str]:
    return (int(candidate.get("strength_score") or 0), _safe_text(candidate.get("theme")))


def _learning_adjustment(context: dict[str, Any], candidate: dict[str, Any]) -> int:
    feedback = context.get("learning_feedback") if isinstance(context.get("learning_feedback"), dict) else {}
    source_feedback = feedback.get("source_kind") if isinstance(feedback.get("source_kind"), dict) else {}
    content_feedback = feedback.get("content_type") if isinstance(feedback.get("content_type"), dict) else {}
    location_feedback = _current_location_feedback(context)
    source_kind = _safe_text(candidate.get("source_kind"))
    content_type = _safe_text(candidate.get("content_type"))
    score = 0
    if source_kind and isinstance(source_feedback.get(source_kind), dict):
        score += int(source_feedback[source_kind].get("score_adjustment") or 0)
    if content_type and isinstance(content_feedback.get(content_type), dict):
        score += int(content_feedback[content_type].get("score_adjustment") or 0)
    if location_feedback:
        score += int(location_feedback.get("score_adjustment") or 0)
    return max(-35, min(18, score))


def _current_location_feedback(context: dict[str, Any]) -> dict[str, Any]:
    feedback = context.get("learning_feedback") if isinstance(context.get("learning_feedback"), dict) else {}
    location_feedback = feedback.get("location") if isinstance(feedback.get("location"), dict) else {}
    scope = context.get("scope") if isinstance(context.get("scope"), dict) else {}
    business = context.get("business") if isinstance(context.get("business"), dict) else {}
    keys = [
        _safe_text(scope.get("scope_target_id")),
        _safe_text(business.get("id")),
        "current",
    ]
    for key in keys:
        if key and isinstance(location_feedback.get(key), dict):
            return location_feedback[key]
    return {}


def _location_quality_hint(context: dict[str, Any]) -> str:
    item = _current_location_feedback(context)
    if not item:
        return ""
    risk_score = float(item.get("risk_score") or 0.0)
    reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
    if risk_score < 35 and int(item.get("score_adjustment") or 0) >= 0:
        return ""
    if "drafts_not_published" in reasons:
        return "Для этой точки делайте тему короче и ближе к публикации: конкретный повод, короткий текст и одно действие."
    if "major_rewrites" in reasons:
        return "Для этой точки избегайте общих формулировок: укажите конкретную услугу, выгоду, доказательство и следующий шаг."
    if "skipped_items" in reasons:
        return "Для этой точки выбирайте темы, которые можно быстро выпустить без подготовки: готовый повод, понятный CTA и минимум абстракции."
    if "many_edits" in reasons:
        return "Для этой точки формулируйте черновик точнее: меньше общих слов, больше связи с услугой, спросом и причиной выбрать бизнес."
    return "Для этой точки нужен более конкретный черновик: услуга, сценарий выбора, доказательство и CTA."


def _apply_learning_feedback(context: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    location_hint = _location_quality_hint(context)
    for candidate in candidates:
        adjustment = _learning_adjustment(context, candidate)
        next_candidate = dict(candidate)
        ranking_reasons = candidate.get("ranking_reasons") if isinstance(candidate.get("ranking_reasons"), list) else []
        next_candidate["learning_adjustment"] = adjustment
        next_candidate["base_strength_score"] = int(candidate.get("strength_score") or 0)
        next_candidate["strength_score"] = max(1, int(candidate.get("strength_score") or 0) + adjustment)
        if location_hint:
            current_goal = _safe_text(next_candidate.get("goal"))
            next_candidate["goal"] = f"{current_goal} {location_hint}".strip()
            next_candidate["quality_hint"] = location_hint
            ranking_reasons = [
                *ranking_reasons,
                _ranking_reason("location_quality_feedback", adjustment),
            ]
        if adjustment != 0:
            next_candidate["ranking_reasons"] = [
                *ranking_reasons,
                _ranking_reason("learning_feedback", adjustment),
            ]
        elif location_hint:
            next_candidate["ranking_reasons"] = ranking_reasons
        adjusted.append(next_candidate)
    return adjusted


def _pick_candidates(candidates: list[dict[str, Any]], items_target: int) -> list[dict[str, Any]]:
    if not candidates:
        return []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        content_type = _safe_text(candidate.get("content_type")) or "news"
        buckets.setdefault(content_type, []).append(candidate)
    for bucket in buckets.values():
        bucket.sort(key=_candidate_sort_key, reverse=True)

    type_order = sorted(
        buckets.keys(),
        key=lambda content_type: _candidate_sort_key(buckets[content_type][0]),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    while len(selected) < items_target:
        progress = False
        for content_type in type_order:
            bucket = buckets.get(content_type) or []
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            progress = True
            if len(selected) >= items_target:
                break
        if not progress:
            break

    if len(selected) < items_target:
        refill_pool = sorted(candidates, key=_candidate_sort_key, reverse=True)
        refill_index = 0
        while len(selected) < items_target and refill_pool:
            selected.append(refill_pool[refill_index % len(refill_pool)])
            refill_index += 1
    return selected


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
    recent_blob = _recent_content_blob(context)

    if _content_mix_value(content_mix, "services"):
        for service in services[:10]:
            service_name = _safe_text(service.get("name"))
            if not service_name:
                continue
            base_score = _service_strength(service)
            coverage_score = _undercovered_bonus(service_name, recent_blob)
            candidates.append(
                {
                    "content_type": "service",
                    "theme": f"Подсветить услугу: {service_name}",
                    "goal": _service_goal(service_name, city),
                    "source_kind": "service",
                    "source_ref": service_name,
                    "service_id": _safe_text(service.get("id")),
                    "cta_hint": _service_cta(service_name),
                    "strength_score": base_score + coverage_score,
                    "ranking_reasons": [
                        _ranking_reason("service_signal_strength", base_score),
                        _ranking_reason("undercovered_topic", coverage_score),
                    ],
                }
            )

    if _content_mix_value(content_mix, "seo"):
        for keyword in seo_keywords[:10]:
            keyword_text = _safe_text(keyword.get("keyword"))
            if not keyword_text:
                continue
            theme_suffix = f" в {city}" if city else ""
            base_score = _seo_strength(keyword)
            coverage_score = _undercovered_bonus(keyword_text, recent_blob)
            candidates.append(
                {
                    "content_type": "seo",
                    "theme": f"Ответить на спрос: {keyword_text}{theme_suffix}",
                    "goal": _seo_goal(keyword_text, city),
                    "source_kind": "seo_keyword",
                    "source_ref": keyword_text,
                    "seo_keyword": keyword_text,
                    "cta_hint": _seo_cta(keyword_text),
                    "strength_score": base_score + coverage_score,
                    "ranking_reasons": [
                        _ranking_reason("seo_demand_strength", base_score),
                        _ranking_reason("undercovered_seo_scenario", coverage_score),
                    ],
                }
            )

    if _content_mix_value(content_mix, "sales"):
        for sale in sales_signals[:8]:
            sale_name = _safe_text(sale.get("title") or sale.get("label") or sale.get("service_name"))
            if not sale_name:
                continue
            base_score = _sales_strength(sale)
            coverage_score = _undercovered_bonus(sale_name, recent_blob)
            candidates.append(
                {
                    "content_type": "sales",
                    "theme": f"Продвижение на основе продаж: {sale_name}",
                    "goal": _sales_goal(sale_name),
                    "source_kind": "transaction",
                    "source_ref": sale_name,
                    "transaction_id": _safe_text(sale.get("transaction_id")),
                    "cta_hint": _sales_cta(sale_name),
                    "strength_score": base_score + coverage_score,
                    "ranking_reasons": [
                        _ranking_reason("sales_signal_strength", base_score),
                        _ranking_reason("undercovered_sales_topic", coverage_score),
                    ],
                }
            )

    if _content_mix_value(content_mix, "audit"):
        for signal in audit_signals[:8]:
            signal_title = _safe_text(signal.get("title"))
            signal_problem = _safe_text(signal.get("problem"))
            if not signal_title and not signal_problem:
                continue
            theme = _audit_theme(signal)
            source_ref = _clean_audit_signal_text(_safe_text(signal.get("evidence") or signal_title or signal_problem))
            base_score = _audit_strength(signal)
            weak_zone_score = _weak_zone_bonus(signal)
            coverage_score = _undercovered_bonus(theme, recent_blob)
            candidates.append(
                {
                    "content_type": "audit",
                    "theme": theme,
                    "goal": _audit_goal(signal),
                    "source_kind": "audit_signal",
                    "source_ref": source_ref or theme,
                    "cta_hint": _audit_cta(signal),
                    "strength_score": base_score + weak_zone_score + coverage_score,
                    "ranking_reasons": [
                        _ranking_reason("audit_signal_strength", base_score),
                        _ranking_reason("weak_zone_priority", weak_zone_score),
                        _ranking_reason("undercovered_weak_zone", coverage_score),
                    ],
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
                    "strength_score": _seasonal_strength(topic),
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
                "strength_score": 20,
            }
        )

    candidates = _apply_learning_feedback(context, candidates)
    selected_candidates = _pick_candidates(candidates, items_target)
    selected_items: list[dict[str, Any]] = []
    step_days = max(3, round(period_days / max(items_target, 1)))
    current_date = period_start
    while len(selected_items) < items_target:
        candidate = selected_candidates[len(selected_items) % len(selected_candidates)]
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
                "strength_score": int(candidate.get("strength_score") or 0),
                "learning_adjustment": int(candidate.get("learning_adjustment") or 0),
                "base_strength_score": int(candidate.get("base_strength_score") or candidate.get("strength_score") or 0),
                "quality_hint": candidate.get("quality_hint") or "",
                "ranking_reasons": candidate.get("ranking_reasons") if isinstance(candidate.get("ranking_reasons"), list) else [],
            }
        )
        current_date = min(period_end, current_date + timedelta(days=step_days))
        if current_date >= period_end and len(selected_items) < items_target:
            current_date = period_start + timedelta(days=min(len(selected_items), period_days - 1))

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
            "max_strength_score": max(int(item.get("strength_score") or 0) for item in selected_items),
            "learning_feedback_applied": any(int(item.get("learning_adjustment") or 0) != 0 for item in selected_items),
            "quality_ranking_applied": any(
                bool(item.get("ranking_reasons"))
                for item in selected_items
            ),
        },
    }
