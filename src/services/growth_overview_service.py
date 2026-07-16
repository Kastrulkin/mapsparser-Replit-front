from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from database_manager import DatabaseManager


AREA_ORDER = ("maps", "content", "partnerships", "automation", "upsells")
logger = logging.getLogger(__name__)


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    return default


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    clean = str(value).strip()
    return clean or None


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS relation", (f"public.{table_name}",))
    return bool(_row_value(cursor.fetchone(), "relation"))


def _milestone(key: str, label: str, done: bool, achieved_at: Any = None, evidence: str = "") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "done" if done else "next",
        "achieved_at": _iso(achieved_at) if done else None,
        "evidence": evidence if done else "",
    }


def _action(
    *,
    title: str,
    reason: str,
    expected_outcome: str,
    cta_label: str,
    cta_url: str,
    priority: int,
) -> dict[str, Any]:
    return {
        "title": title,
        "reason": reason,
        "expected_outcome": expected_outcome,
        "cta_label": cta_label,
        "cta_url": cta_url,
        "priority": priority,
        "estimated_effect": None,
    }


def _area(
    *,
    key: str,
    label: str,
    status: str,
    summary: str,
    problem: str | None,
    expected_outcome: str,
    action: dict[str, Any],
    milestones: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    source_state: str = "ready",
) -> dict[str, Any]:
    completed = len([item for item in milestones if item["status"] == "done"])
    return {
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "problem": problem,
        "expected_outcome": expected_outcome,
        "action": action,
        "progress": {"completed": completed, "total": len(milestones)},
        "milestones": milestones,
        "metrics": metrics,
        "source_state": source_state,
    }


def _unavailable_area(key: str, label: str, url: str) -> dict[str, Any]:
    return _area(
        key=key,
        label=label,
        status="unavailable",
        summary="Данные временно недоступны",
        problem="LocalOS не смог получить состояние этого направления.",
        expected_outcome="После восстановления данных прогресс появится автоматически.",
        action=_action(
            title="Открыть раздел",
            reason="Проверьте состояние непосредственно в рабочем разделе.",
            expected_outcome="Вы увидите доступные действия и текущие данные.",
            cta_label="Открыть раздел",
            cta_url=url,
            priority=10,
        ),
        milestones=[],
        metrics=[],
        source_state="unavailable",
    )


def _build_maps_area(data: dict[str, Any], locations_count: int) -> dict[str, Any]:
    links = int(data.get("linked_locations") or 0)
    parsed = int(data.get("parsed_locations") or 0)
    services = int(data.get("services_count") or 0)
    unanswered = int(data.get("unanswered_reviews") or 0)
    reviews = int(data.get("reviews_count") or 0)
    latest_at = data.get("latest_at")
    has_links = links > 0
    has_parse = parsed > 0
    profile_ready = has_parse and services > 0
    reputation_started = reviews > 0
    attention_location = str(data.get("attention_location") or "").strip()
    coverage = f"{links} из {locations_count}" if locations_count > 1 else ("Подключена" if has_links else "Не подключена")

    if not has_links:
        status = "not_started"
        problem = "Без ссылки LocalOS не может проверить карточку и показать изменения."
        action = _action(
            title="Подключите карту",
            reason=problem,
            expected_outcome="LocalOS получит данные карточки и подготовит первый аудит.",
            cta_label="Добавить карту",
            cta_url="/dashboard/profile",
            priority=100,
        )
        summary = "Карточка ещё не подключена"
    elif not has_parse:
        status = "needs_attention"
        problem = "Карта подключена, но свежих данных и аудита ещё нет."
        action = _action(
            title="Получите данные карты",
            reason=problem,
            expected_outcome="Появится аудит с конкретными проблемами карточки.",
            cta_label="Обновить карту",
            cta_url="/dashboard/card",
            priority=90,
        )
        summary = "Карта подключена, аудит ещё не готов"
    elif unanswered > 0:
        status = "needs_attention"
        problem = (
            f"Точка «{attention_location}»: без ответа осталось отзывов: {unanswered}."
            if attention_location
            else f"Без ответа осталось отзывов: {unanswered}."
        )
        action = _action(
            title="Ответьте на новые отзывы",
            reason=problem,
            expected_outcome="Клиенты увидят, что бизнес реагирует на обратную связь.",
            cta_label="Открыть отзывы",
            cta_url="/dashboard/card?tab=reviews",
            priority=80,
        )
        summary = "Аудит готов, репутация требует внимания"
    elif not profile_ready:
        status = "in_progress"
        problem = "В данных карты пока не хватает услуг или основных сведений."
        action = _action(
            title="Дополните карточку",
            reason=problem,
            expected_outcome="Клиентам будет проще понять предложение и выбрать бизнес.",
            cta_label="Открыть рекомендации",
            cta_url="/dashboard/card",
            priority=65,
        )
        summary = "Аудит готов, карточку можно усилить"
    else:
        status = "healthy"
        problem = None
        action = _action(
            title="Поддерживайте данные актуальными",
            reason="Карточка подключена, аудит доступен, срочных проблем не видно.",
            expected_outcome="Актуальная карточка продолжит помогать клиентам находить и выбирать бизнес.",
            cta_label="Открыть карты",
            cta_url="/dashboard/card",
            priority=20,
        )
        summary = "Карточка и репутация под контролем"

    return _area(
        key="maps",
        label="Карты и репутация",
        status=status,
        summary=summary,
        problem=problem,
        expected_outcome=action["expected_outcome"],
        action=action,
        milestones=[
            _milestone("map_connected", "Карта подключена", has_links, data.get("link_created_at"), coverage),
            _milestone("map_audited", "Данные и аудит получены", has_parse, latest_at, f"Обновлено карточек: {parsed}"),
            _milestone("map_profile_ready", "Основные данные заполнены", profile_ready, latest_at, f"Услуг в карточке: {services}"),
            _milestone("reputation_started", "Начата работа с репутацией", reputation_started, latest_at, f"Отзывов: {reviews}"),
        ],
        metrics=[
            {"label": "Карты", "value": coverage},
            {"label": "Отзывы", "value": reviews},
            {"label": "Без ответа", "value": unanswered},
        ],
    )


def _build_content_area(data: dict[str, Any]) -> dict[str, Any]:
    plans = int(data.get("plans") or 0)
    drafts = int(data.get("drafts") or 0)
    published = int(data.get("published") or 0)
    if plans == 0:
        status, problem, priority = "not_started", "Контент-план ещё не создан.", 45
        title, cta = "Запустите контент-план", "Создать контент-план"
    elif drafts == 0:
        status, problem, priority = "in_progress", "План создан, но готовых материалов пока нет.", 55
        title, cta = "Подготовьте первый материал", "Открыть контент-план"
    elif published == 0:
        status, problem, priority = "in_progress", "Черновики готовы, но ни одна публикация ещё не подтверждена.", 60
        title, cta = "Доведите материал до публикации", "Проверить материалы"
    else:
        status, problem, priority = "healthy", None, 18
        title, cta = "Продолжайте по плану", "Открыть контент"
    action = _action(
        title=title,
        reason=problem or "Контент-план работает, готовые материалы и публикации сохраняются в истории.",
        expected_outcome="У бизнеса будет регулярный поток подготовленных публикаций.",
        cta_label=cta,
        cta_url="/dashboard/content",
        priority=priority,
    )
    return _area(
        key="content",
        label="Контент",
        status=status,
        summary=(f"Планов: {plans}, готовых материалов: {drafts}, опубликовано: {published}" if plans else "Контент-план ещё не запущен"),
        problem=problem,
        expected_outcome=action["expected_outcome"],
        action=action,
        milestones=[
            _milestone("content_plan_created", "Контент-план создан", plans > 0, data.get("plan_at"), f"Планов: {plans}"),
            _milestone("content_draft_ready", "Подготовлен материал", drafts > 0, data.get("draft_at"), f"Материалов: {drafts}"),
            _milestone("content_published", "Публикация подтверждена", published > 0, data.get("published_at"), f"Публикаций: {published}"),
        ],
        metrics=[
            {"label": "Планы", "value": plans},
            {"label": "Готово", "value": drafts},
            {"label": "Опубликовано", "value": published},
        ],
    )


def _build_partnerships_area(data: dict[str, Any]) -> dict[str, Any]:
    leads = int(data.get("leads") or 0)
    proposals = int(data.get("proposals") or 0)
    contacted = int(data.get("contacted") or 0)
    results = int(data.get("results") or 0)
    if leads == 0:
        status, problem, priority, title, cta = "not_started", "Потенциальные партнёры ещё не найдены.", 40, "Найдите партнёров", "Начать поиск"
    elif proposals == 0:
        status, problem, priority, title, cta = "in_progress", "Партнёры найдены, но предложения ещё не подготовлены.", 52, "Подготовьте предложение", "Открыть партнёров"
    elif contacted == 0:
        status, problem, priority, title, cta = "in_progress", "Предложения готовы и ждут следующего ручного шага.", 58, "Выберите партнёров для контакта", "Проверить предложения"
    elif results == 0:
        status, problem, priority, title, cta = "in_progress", "Контакты начаты, ответы ещё не зафиксированы.", 50, "Проверьте ответы и следующие шаги", "Открыть воронку"
    else:
        status, problem, priority, title, cta = "healthy", None, 17, "Развивайте успешные контакты", "Открыть партнёров"
    action = _action(
        title=title,
        reason=problem or "По партнёрствам уже есть подтверждённые результаты.",
        expected_outcome="Появятся подготовленные контакты и совместные предложения без автоматической отправки.",
        cta_label=cta,
        cta_url="/dashboard/partnerships",
        priority=priority,
    )
    return _area(
        key="partnerships",
        label="Партнёры",
        status=status,
        summary=(f"Найдено: {leads}, предложений: {proposals}, результатов: {results}" if leads else "Поиск партнёров ещё не запускался"),
        problem=problem,
        expected_outcome=action["expected_outcome"],
        action=action,
        milestones=[
            _milestone("partner_found", "Найден потенциальный партнёр", leads > 0, data.get("lead_at"), f"Лидов: {leads}"),
            _milestone("partner_proposal_ready", "Подготовлено предложение", proposals > 0, data.get("proposal_at"), f"Предложений: {proposals}"),
            _milestone("partner_contacted", "Установлен контакт", contacted > 0, data.get("contact_at"), f"Контактов: {contacted}"),
            _milestone("partner_result", "Получен ответ или результат", results > 0, data.get("result_at"), f"Результатов: {results}"),
        ],
        metrics=[
            {"label": "Найдено", "value": leads},
            {"label": "В контакте", "value": contacted},
            {"label": "Результаты", "value": results},
        ],
    )


def _build_automation_area(data: dict[str, Any]) -> dict[str, Any]:
    agents = int(data.get("agents") or 0)
    tests = int(data.get("tests") or 0)
    active = int(data.get("active") or 0)
    completed = int(data.get("completed") or 0)
    failed = int(data.get("failed") or 0)
    if failed > 0:
        status, problem, priority, title, cta = "needs_attention", f"Рабочих запусков с ошибкой: {failed}.", 85, "Проверьте ошибку агента", "Открыть агентов"
    elif agents == 0:
        status, problem, priority, title, cta = "not_started", "Автоматизированные задачи ещё не настроены.", 35, "Настройте первую задачу", "Создать агента"
    elif tests == 0:
        status, problem, priority, title, cta = "in_progress", "Агент создан, но ещё не проверен на примере.", 57, "Запустите безопасный тест", "Проверить агента"
    elif active == 0:
        status, problem, priority, title, cta = "in_progress", "Тест пройден, но ни один агент не включён в работу.", 62, "Включите проверенного агента", "Открыть агентов"
    elif completed == 0:
        status, problem, priority, title, cta = "in_progress", "Агент включён, но рабочего результата пока нет.", 48, "Запустите первую работу", "Открыть агентов"
    else:
        status, problem, priority, title, cta = "healthy", None, 16, "Следите за следующими результатами", "Открыть агентов"
    action = _action(
        title=title,
        reason=problem or "Агенты выполняют рабочие задачи, результаты сохраняются в истории.",
        expected_outcome="Повторяемая работа будет выполняться без повторной настройки сценария.",
        cta_label=cta,
        cta_url="/dashboard/agents",
        priority=priority,
    )
    return _area(
        key="automation",
        label="Автоматизация",
        status=status,
        summary=(f"Агентов: {agents}, работают: {active}, выполнено задач: {completed}" if agents else "Автоматизированных задач пока нет"),
        problem=problem,
        expected_outcome=action["expected_outcome"],
        action=action,
        milestones=[
            _milestone("agent_tested", "Агент проверен", tests > 0, data.get("test_at"), f"Тестов: {tests}"),
            _milestone("agent_enabled", "Агент включён", active > 0, data.get("active_at"), f"Работают: {active}"),
            _milestone("agent_completed", "Рабочая задача выполнена", completed > 0, data.get("completed_at"), f"Результатов: {completed}"),
        ],
        metrics=[
            {"label": "Создано", "value": agents},
            {"label": "Работают", "value": active},
            {"label": "Выполнено", "value": completed},
        ],
    )


def _build_upsells_area(data: dict[str, Any]) -> dict[str, Any]:
    matrices = int(data.get("matrices") or 0)
    active = int(data.get("active") or 0)
    bought = int(data.get("bought") or 0)
    revenue = float(data.get("revenue") or 0)
    if matrices == 0:
        status, problem, priority, title, cta = "not_started", "Варианты допродаж ещё не рассчитаны.", 38, "Рассчитайте допродажи", "Рассчитать допродажи"
    elif active == 0:
        status, problem, priority, title, cta = "in_progress", "Рекомендации рассчитаны, но ни одна не включена в работу.", 54, "Выберите предложения для внедрения", "Открыть рекомендации"
    elif bought == 0:
        status, problem, priority, title, cta = "in_progress", "Предложения внедрены, продажи по ним ещё не зафиксированы.", 42, "Начните отмечать результаты", "Открыть допродажи"
    else:
        status, problem, priority, title, cta = "healthy", None, 15, "Продолжайте фиксировать результаты", "Открыть допродажи"
    actual_effect = None
    if revenue > 0:
        actual_effect = {
            "kind": "actual",
            "label": "Зафиксированная дополнительная выручка",
            "amount": round(revenue, 2),
            "currency": "RUB",
            "source": "Отмеченные покупки в разделе допродаж",
            "confidence": "confirmed",
            "disclaimer": None,
        }
    action = _action(
        title=title,
        reason=problem or "По внедрённым предложениям уже зафиксированы покупки.",
        expected_outcome="Сотрудникам будет понятно, что уместно предложить вместе с основной услугой.",
        cta_label=cta,
        cta_url="/dashboard/average-ticket",
        priority=priority,
    )
    action["estimated_effect"] = actual_effect
    return _area(
        key="upsells",
        label="Допродажи",
        status=status,
        summary=(f"Расчётов: {matrices}, внедрено: {active}, покупок: {bought}" if matrices else "Допродажи ещё не рассчитаны"),
        problem=problem,
        expected_outcome=action["expected_outcome"],
        action=action,
        milestones=[
            _milestone("upsells_calculated", "Рекомендации рассчитаны", matrices > 0, data.get("matrix_at"), f"Расчётов: {matrices}"),
            _milestone("upsells_enabled", "Предложение внедрено", active > 0, data.get("active_at"), f"Активно: {active}"),
            _milestone("upsells_bought", "Зафиксирована продажа", bought > 0, data.get("bought_at"), f"Покупок: {bought}"),
        ],
        metrics=[
            {"label": "Рассчитано", "value": matrices},
            {"label": "Внедрено", "value": active},
            {"label": "Покупки", "value": bought},
        ],
    )


def build_growth_overview(snapshot: dict[str, Any]) -> dict[str, Any]:
    scope = snapshot.get("scope") if isinstance(snapshot.get("scope"), dict) else {}
    locations_count = int(scope.get("locations_count") or 1)
    source_builders = {
        "maps": (_build_maps_area, "Карты и репутация", "/dashboard/card"),
        "content": (_build_content_area, "Контент", "/dashboard/content"),
        "partnerships": (_build_partnerships_area, "Партнёры", "/dashboard/partnerships"),
        "automation": (_build_automation_area, "Автоматизация", "/dashboard/agents"),
        "upsells": (_build_upsells_area, "Допродажи", "/dashboard/average-ticket"),
    }
    areas = []
    for key in AREA_ORDER:
        builder, label, url = source_builders[key]
        source = snapshot.get(key)
        if not isinstance(source, dict) or source.get("available") is False:
            areas.append(_unavailable_area(key, label, url))
            continue
        if key == "maps":
            areas.append(builder(source, locations_count))
        else:
            areas.append(builder(source))

    focus_candidates = [area["action"] for area in areas if area["status"] != "unavailable"]
    focus_action = max(focus_candidates, key=lambda item: int(item.get("priority") or 0)) if focus_candidates else None
    completed_milestones = sum(area["progress"]["completed"] for area in areas)
    total_milestones = sum(area["progress"]["total"] for area in areas)
    achievements = []
    for area in areas:
        for item in area["milestones"]:
            if item["status"] != "done" or not item.get("achieved_at"):
                continue
            achievements.append(
                {
                    "key": f"{area['key']}:{item['key']}",
                    "area": area["key"],
                    "title": item["label"],
                    "description": item.get("evidence") or area["summary"],
                    "occurred_at": item["achieved_at"],
                }
            )
    achievements.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
    recent_achievements = achievements[:8]
    now = datetime.now(timezone.utc)
    recent_30 = 0
    for item in achievements:
        try:
            occurred = datetime.fromisoformat(str(item["occurred_at"]).replace("Z", "+00:00"))
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone.utc)
            if (now - occurred).days <= 30:
                recent_30 += 1
        except ValueError:
            continue
    return {
        "summary": {
            "completed_milestones": completed_milestones,
            "total_milestones": total_milestones,
            "active_areas": len([area for area in areas if area["status"] in {"healthy", "in_progress", "needs_attention"}]),
            "needs_attention": len([area for area in areas if area["status"] == "needs_attention"]),
            "completed_last_30_days": recent_30,
            "locations_count": locations_count,
        },
        "focus_action": focus_action,
        "areas": areas,
        "recent_achievements": recent_achievements,
        "recent_activity": recent_achievements,
        "scope": scope,
        "generated_at": now.isoformat(),
    }


def _load_scope(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute("SELECT id, name, owner_id, network_id FROM businesses WHERE id = %s", (business_id,))
    business = cursor.fetchone()
    if not business:
        raise ValueError("Бизнес не найден")
    network_id = _row_value(business, "network_id")
    owner_id = _row_value(business, "owner_id")
    if network_id:
        cursor.execute(
            "SELECT id, name FROM businesses WHERE network_id = %s AND owner_id = %s ORDER BY name",
            (network_id, owner_id),
        )
        locations = [dict(row) for row in (cursor.fetchall() or [])]
    else:
        locations = [{"id": business_id, "name": _row_value(business, "name") or "Бизнес"}]
    return {
        "business_id": business_id,
        "business_name": _row_value(business, "name") or "Бизнес",
        "network_id": network_id,
        "is_network": len(locations) > 1,
        "locations_count": len(locations),
        "locations": locations,
        "business_ids": [str(item["id"]) for item in locations],
    }


def _load_maps(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    links_table = _table_exists(cursor, "businessmaplinks")
    parse_table = _table_exists(cursor, "mapparseresults")
    reviews_table = _table_exists(cursor, "externalbusinessreviews")
    if not links_table and not parse_table:
        return {"available": False}
    result: dict[str, Any] = {"available": True, "linked_locations": 0, "parsed_locations": 0, "services_count": 0, "reviews_count": 0, "unanswered_reviews": 0}
    if links_table:
        cursor.execute(
            "SELECT COUNT(DISTINCT business_id) AS count, MIN(created_at) AS first_at FROM businessmaplinks WHERE business_id::text = ANY(%s)",
            (business_ids,),
        )
        row = cursor.fetchone()
        result["linked_locations"] = int(_row_value(row, "count") or 0)
        result["link_created_at"] = _row_value(row, "first_at")
    if parse_table:
        cursor.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (business_id)
                    business_id, created_at, reviews_count, services_count, unanswered_reviews_count
                FROM mapparseresults
                WHERE business_id::text = ANY(%s)
                ORDER BY business_id, created_at DESC
            )
            SELECT COUNT(*) AS parsed_locations,
                   COALESCE(SUM(reviews_count), 0) AS reviews_count,
                   COALESCE(SUM(services_count), 0) AS services_count,
                   COALESCE(SUM(unanswered_reviews_count), 0) AS unanswered_reviews,
                   MAX(created_at) AS latest_at
            FROM latest
            """,
            (business_ids,),
        )
        row = cursor.fetchone()
        result["parsed_locations"] = int(_row_value(row, "parsed_locations") or 0)
        result["reviews_count"] = int(_row_value(row, "reviews_count") or 0)
        result["services_count"] = int(_row_value(row, "services_count") or 0)
        result["unanswered_reviews"] = int(_row_value(row, "unanswered_reviews") or 0)
        result["latest_at"] = _row_value(row, "latest_at")
        if len(business_ids) > 1 and int(result["unanswered_reviews"]) > 0:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (business_id) business_id, unanswered_reviews_count
                    FROM mapparseresults
                    WHERE business_id::text = ANY(%s)
                    ORDER BY business_id, created_at DESC
                )
                SELECT b.name
                FROM latest
                JOIN businesses b ON b.id::text = latest.business_id::text
                ORDER BY latest.unanswered_reviews_count DESC, b.name
                LIMIT 1
                """,
                (business_ids,),
            )
            location_row = cursor.fetchone()
            result["attention_location"] = _row_value(location_row, "name")
    if reviews_table:
        cursor.execute(
            """
            SELECT COUNT(*) AS reviews_count,
                   COUNT(*) FILTER (WHERE COALESCE(NULLIF(TRIM(response_text), ''), '') IN ('', '—')) AS unanswered_reviews,
                   MAX(COALESCE(published_at, created_at)) AS latest_at
            FROM externalbusinessreviews
            WHERE business_id::text = ANY(%s)
            """,
            (business_ids,),
        )
        row = cursor.fetchone()
        normalized_count = int(_row_value(row, "reviews_count") or 0)
        if normalized_count > 0:
            result["reviews_count"] = normalized_count
            result["unanswered_reviews"] = int(_row_value(row, "unanswered_reviews") or 0)
            result["latest_at"] = _row_value(row, "latest_at") or result.get("latest_at")
            if len(business_ids) > 1 and int(result["unanswered_reviews"]) > 0:
                cursor.execute(
                    """
                    SELECT b.name
                    FROM externalbusinessreviews r
                    JOIN businesses b ON b.id::text = r.business_id::text
                    WHERE r.business_id::text = ANY(%s)
                      AND COALESCE(NULLIF(TRIM(r.response_text), ''), '') IN ('', '—')
                    GROUP BY b.id, b.name
                    ORDER BY COUNT(*) DESC, b.name
                    LIMIT 1
                    """,
                    (business_ids,),
                )
                location_row = cursor.fetchone()
                result["attention_location"] = _row_value(location_row, "name") or result.get("attention_location")
    return result


def _load_content(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    if not _table_exists(cursor, "contentplans") or not _table_exists(cursor, "contentplanitems"):
        return {"available": False}
    cursor.execute(
        "SELECT COUNT(*) AS count, MAX(created_at) AS latest_at FROM contentplans WHERE business_id::text = ANY(%s)",
        (business_ids,),
    )
    plan_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE COALESCE(NULLIF(TRIM(draft_text), ''), '') <> '') AS drafts,
               COUNT(*) FILTER (WHERE status = 'published' OR COALESCE(NULLIF(TRIM(usernews_id), ''), '') <> '') AS published,
               MAX(created_at) FILTER (WHERE COALESCE(NULLIF(TRIM(draft_text), ''), '') <> '') AS draft_at,
               MAX(updated_at) FILTER (WHERE status = 'published' OR COALESCE(NULLIF(TRIM(usernews_id), ''), '') <> '') AS published_at
        FROM contentplanitems
        WHERE business_id::text = ANY(%s)
        """,
        (business_ids,),
    )
    item_row = cursor.fetchone()
    published = int(_row_value(item_row, "published") or 0)
    published_at = _row_value(item_row, "published_at")
    if _table_exists(cursor, "social_posts"):
        cursor.execute(
            "SELECT COUNT(*) AS count, MAX(published_at) AS latest_at FROM social_posts WHERE business_id::text = ANY(%s) AND status = 'published'",
            (business_ids,),
        )
        social_row = cursor.fetchone()
        published += int(_row_value(social_row, "count") or 0)
        published_at = _row_value(social_row, "latest_at") or published_at
    return {
        "available": True,
        "plans": int(_row_value(plan_row, "count") or 0),
        "plan_at": _row_value(plan_row, "latest_at"),
        "drafts": int(_row_value(item_row, "drafts") or 0),
        "draft_at": _row_value(item_row, "draft_at"),
        "published": published,
        "published_at": published_at,
    }


def _load_partnerships(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    if not _table_exists(cursor, "prospectingleads"):
        return {"available": False}
    cursor.execute(
        """
        SELECT COUNT(*) AS leads,
               COUNT(*) FILTER (WHERE COALESCE(partnership_stage, '') IN ('matched','audited','proposal_draft_ready','selected_for_outreach','channel_selected','proposal_approved','approved_for_send','queued_for_send','sent')) AS proposals,
               COUNT(*) FILTER (WHERE COALESCE(pipeline_status, '') IN ('contacted','waiting_reply','sent','delivered','second_message_sent','replied','responded','converted')) AS contacted,
               COUNT(*) FILTER (WHERE COALESCE(pipeline_status, '') IN ('replied','responded','converted')) AS results,
               MAX(created_at) AS lead_at,
               MAX(updated_at) FILTER (WHERE COALESCE(partnership_stage, '') IN ('matched','audited','proposal_draft_ready','selected_for_outreach','channel_selected','proposal_approved','approved_for_send','queued_for_send','sent')) AS proposal_at,
               MAX(updated_at) FILTER (WHERE COALESCE(pipeline_status, '') IN ('contacted','waiting_reply','sent','delivered','second_message_sent','replied','responded','converted')) AS contact_at,
               MAX(updated_at) FILTER (WHERE COALESCE(pipeline_status, '') IN ('replied','responded','converted')) AS result_at
        FROM prospectingleads
        WHERE business_id::text = ANY(%s)
          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
        """,
        (business_ids,),
    )
    row = cursor.fetchone()
    return {"available": True, **dict(row or {})}


def _load_automation(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    if not _table_exists(cursor, "agent_blueprints") or not _table_exists(cursor, "agent_runs"):
        return {"available": False}
    cursor.execute(
        """
        SELECT COUNT(DISTINCT b.id) FILTER (WHERE b.status <> 'archived') AS agents,
               COUNT(DISTINCT b.id) FILTER (WHERE b.status = 'active') AS active,
               MIN(b.updated_at) FILTER (WHERE b.status = 'active') AS active_at,
               COUNT(DISTINCT r.id) FILTER (WHERE COALESCE(r.input_json->>'preview_mode', 'false') = 'true' AND r.status = 'completed') AS tests,
               MAX(r.completed_at) FILTER (WHERE COALESCE(r.input_json->>'preview_mode', 'false') = 'true' AND r.status = 'completed') AS test_at,
               COUNT(DISTINCT r.id) FILTER (WHERE COALESCE(r.input_json->>'preview_mode', 'false') <> 'true' AND r.status = 'completed') AS completed,
               MAX(r.completed_at) FILTER (WHERE COALESCE(r.input_json->>'preview_mode', 'false') <> 'true' AND r.status = 'completed') AS completed_at,
               COUNT(DISTINCT b.id) FILTER (WHERE last_run.status = 'failed') AS failed
        FROM agent_blueprints b
        LEFT JOIN agent_runs r ON r.blueprint_id = b.id AND r.status <> 'superseded'
        LEFT JOIN LATERAL (
            SELECT status
            FROM agent_runs
            WHERE blueprint_id = b.id AND status <> 'superseded'
            ORDER BY COALESCE(queued_at, started_at, updated_at) DESC
            LIMIT 1
        ) last_run ON TRUE
        WHERE b.business_id::text = ANY(%s)
        """,
        (business_ids,),
    )
    row = cursor.fetchone()
    return {"available": True, **dict(row or {})}


def _load_upsells(cursor: Any, business_ids: list[str]) -> dict[str, Any]:
    if not _table_exists(cursor, "averageticketmatrices"):
        return {"available": False}
    cursor.execute(
        "SELECT COUNT(*) AS count, MAX(generated_at) AS latest_at FROM averageticketmatrices WHERE business_id::text = ANY(%s)",
        (business_ids,),
    )
    matrix_row = cursor.fetchone()
    active = 0
    active_at = None
    if _table_exists(cursor, "averageticketpackages"):
        cursor.execute(
            "SELECT COUNT(*) AS count, MAX(updated_at) AS latest_at FROM averageticketpackages WHERE business_id::text = ANY(%s) AND status = 'active'",
            (business_ids,),
        )
        active_row = cursor.fetchone()
        active = int(_row_value(active_row, "count") or 0)
        active_at = _row_value(active_row, "latest_at")
    bought, revenue, bought_at = 0, 0.0, None
    if _table_exists(cursor, "averageticketevents"):
        cursor.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS revenue, MAX(created_at) AS latest_at
            FROM averageticketevents
            WHERE business_id::text = ANY(%s) AND event_type IN ('bought', 'package_bought')
            """,
            (business_ids,),
        )
        event_row = cursor.fetchone()
        bought = int(_row_value(event_row, "count") or 0)
        revenue = float(_row_value(event_row, "revenue") or 0)
        bought_at = _row_value(event_row, "latest_at")
    return {
        "available": True,
        "matrices": int(_row_value(matrix_row, "count") or 0),
        "matrix_at": _row_value(matrix_row, "latest_at"),
        "active": active,
        "active_at": active_at,
        "bought": bought,
        "revenue": revenue,
        "bought_at": bought_at,
    }


def load_growth_overview(business_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        scope = _load_scope(cursor, business_id)
        business_ids = scope.pop("business_ids")
        snapshot = {"scope": scope}
        loaders = {
            "maps": _load_maps,
            "content": _load_content,
            "partnerships": _load_partnerships,
            "automation": _load_automation,
            "upsells": _load_upsells,
        }
        for key, loader in loaders.items():
            try:
                snapshot[key] = loader(cursor, business_ids)
            except Exception:
                db.conn.rollback()
                logger.warning("Growth overview source is unavailable: %s", key, exc_info=True)
                snapshot[key] = {"available": False}
        overview = build_growth_overview(snapshot)
        if _table_exists(cursor, "business_action_events"):
            cursor.execute(
                """
                SELECT id, business_id, action_type, status, source_type, source_id,
                       limitations_json, occurred_at
                FROM business_action_events
                WHERE business_id::text = ANY(%s)
                  AND status NOT IN ('reverted', 'superseded')
                ORDER BY occurred_at DESC
                LIMIT 12
                """,
                (business_ids,),
            )
            action_labels = {
                "service_optimization_applied": "Оптимизация услуг применена",
                "content_published": "Публикация подтверждена",
                "map_change_confirmed": "Изменение карточки подтверждено",
                "external_change_detected": "В карточке обнаружено внешнее изменение",
            }
            action_activity = []
            for row in cursor.fetchall() or []:
                action_type = str(_row_value(row, "action_type") or "")
                status = str(_row_value(row, "status") or "")
                action_activity.append(
                    {
                        "key": f"knowledge-action:{_row_value(row, 'id')}",
                        "area": (
                            "content" if action_type == "content_published"
                            else "maps" if "map" in action_type
                            else "upsells" if "upsell" in action_type
                            else "automation"
                        ),
                        "title": action_labels.get(action_type, "Подтверждённое действие"),
                        "description": (
                            "Изменение найдено по новому снимку; LocalOS не приписывает его себе."
                            if status == "external_change_detected"
                            else "Действие сохранено с источником и будет сопоставлено с последующими метриками."
                        ),
                        "occurred_at": _iso(_row_value(row, "occurred_at")),
                        "evidence_level": "insufficient_evidence",
                    }
                )
            combined_activity = action_activity + list(overview.get("recent_activity") or [])
            combined_activity.sort(key=lambda item: str(item.get("occurred_at") or ""), reverse=True)
            overview["recent_activity"] = combined_activity[:12]
        return overview
    finally:
        db.close()
