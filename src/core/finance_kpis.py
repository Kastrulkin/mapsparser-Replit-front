from __future__ import annotations

from datetime import date, datetime
from typing import Any


FIXED_EXPENSE_CATEGORIES = {"rent", "software", "utilities", "taxes", "admin"}
PAYROLL_CATEGORIES = {"payroll", "staff", "salary"}
MATERIAL_CATEGORIES = {"materials", "supplies"}

DEFAULT_FINANCE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "operating_margin": {
        "label": "Операционная маржа",
        "unit": "%",
        "green_min": 20,
        "green_max": None,
        "yellow_min": 10,
        "yellow_max": 19.99,
        "red_rule": "below_yellow_min",
    },
    "gross_margin": {
        "label": "Валовая маржа",
        "unit": "%",
        "green_min": 45,
        "green_max": None,
        "yellow_min": 30,
        "yellow_max": 44.99,
        "red_rule": "below_yellow_min",
    },
    "workplace_occupancy": {
        "label": "Загрузка рабочих мест",
        "unit": "%",
        "green_min": 60,
        "green_max": 85,
        "yellow_min": 45,
        "yellow_max": 100,
        "red_rule": "outside_yellow_range",
    },
    "rebooking_rate": {
        "label": "Повторная запись",
        "unit": "%",
        "green_min": 60,
        "green_max": None,
        "yellow_min": 40,
        "yellow_max": 59.99,
        "red_rule": "below_yellow_min",
    },
    "no_show_rate": {
        "label": "No-show",
        "unit": "%",
        "green_min": None,
        "green_max": 8,
        "yellow_min": 8.01,
        "yellow_max": 10,
        "red_rule": "above_yellow_max",
    },
    "low_margin_services_share": {
        "label": "Доля низкомаржинальных услуг",
        "unit": "%",
        "green_min": None,
        "green_max": 10,
        "yellow_min": 10.01,
        "yellow_max": 20,
        "red_rule": "above_yellow_max",
    },
    "payroll_share": {
        "label": "Доля ФОТ",
        "unit": "%",
        "green_min": None,
        "green_max": 40,
        "yellow_min": 40.01,
        "yellow_max": 50,
        "red_rule": "above_yellow_max",
    },
    "material_share": {
        "label": "Доля материалов",
        "unit": "%",
        "green_min": None,
        "green_max": 12,
        "yellow_min": 12.01,
        "yellow_max": 18,
        "red_rule": "above_yellow_max",
    },
    "gross_profit_per_workplace_hour": {
        "label": "Прибыль на кресло-час",
        "unit": "RUB",
        "green_min": 2500,
        "green_max": None,
        "yellow_min": 1200,
        "yellow_max": 2499.99,
        "red_rule": "below_yellow_min",
    },
    "revenue_per_workplace_hour": {
        "label": "Выручка на кресло-час",
        "unit": "RUB",
        "green_min": 3500,
        "green_max": None,
        "yellow_min": 2500,
        "yellow_max": 3499.99,
        "red_rule": "below_yellow_min",
    },
}


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_div(numerator: float, denominator: float, explanation: str) -> dict[str, Any]:
    if denominator <= 0:
        return {"value": None, "explanation": explanation}
    return {"value": numerator / denominator, "explanation": None}


def _pct(numerator: float, denominator: float, explanation: str) -> dict[str, Any]:
    result = _safe_div(numerator, denominator, explanation)
    if result["value"] is None:
        return result
    return {"value": result["value"] * 100, "explanation": None}


def _status(value: Any, green_check, yellow_check) -> str:
    if value is None:
        return "unknown"
    if green_check(value):
        return "green"
    if yellow_check(value):
        return "yellow"
    return "red"


def get_default_finance_thresholds() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in DEFAULT_FINANCE_THRESHOLDS.items()}


def merge_finance_thresholds(custom_thresholds: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    merged = get_default_finance_thresholds()
    for key, value in (custom_thresholds or {}).items():
        if key not in merged:
            continue
        updated = dict(merged[key])
        for field in ("green_min", "green_max", "yellow_min", "yellow_max", "red_rule", "label", "unit", "profile", "source"):
            if field in value:
                updated[field] = value.get(field)
        merged[key] = updated
    return merged


def _in_range(value: float, minimum: Any, maximum: Any) -> bool:
    if minimum is not None and value < float(minimum):
        return False
    if maximum is not None and value > float(maximum):
        return False
    return True


def threshold_status(value: Any, threshold: dict[str, Any] | None) -> str:
    if value is None:
        return "unknown"
    if not threshold:
        return "unknown"
    number = _num(value)
    if _in_range(number, threshold.get("green_min"), threshold.get("green_max")):
        return "green"
    if _in_range(number, threshold.get("yellow_min"), threshold.get("yellow_max")):
        return "yellow"
    return "red"


def format_threshold_value(value: Any, unit: str | None = None) -> str:
    if value is None:
        return "не задано"
    number = _num(value)
    if unit == "RUB":
        return f"{number:,.0f} ₽".replace(",", " ")
    if unit == "%":
        return f"{number:g}%"
    return f"{number:g}"


def describe_threshold_norm(metric_key: str, thresholds: dict[str, dict[str, Any]]) -> str:
    threshold = thresholds.get(metric_key) or {}
    unit = threshold.get("unit")
    green_min = threshold.get("green_min")
    green_max = threshold.get("green_max")
    if green_min is not None and green_max is not None:
        return f"норма {format_threshold_value(green_min, unit)}-{format_threshold_value(green_max, unit)}"
    if green_min is not None:
        return f"норма от {format_threshold_value(green_min, unit)}"
    if green_max is not None:
        return f"норма до {format_threshold_value(green_max, unit)}"
    return "норма не задана"


def describe_metric_value(metric_key: str, value: Any, thresholds: dict[str, dict[str, Any]]) -> str:
    threshold = thresholds.get(metric_key) or {}
    label = threshold.get("label") or metric_key
    unit = threshold.get("unit")
    return f"{label}: {format_threshold_value(value, unit)}, {describe_threshold_norm(metric_key, thresholds)}"


def classify_service(metric: dict[str, Any]) -> str:
    margin = metric.get("gross_margin")
    revenue = _num(metric.get("revenue"))
    visits = _num(metric.get("visits_count"))
    price = _num(metric.get("avg_price"))

    if margin is not None and margin < 30:
        return "busy_without_profit"
    if margin is not None and margin >= 45 and visits >= 5:
        return "star"
    if revenue >= 100000 or price >= 7000:
        return "money"
    return "entry_service"


def _has_positive(items: list[dict[str, Any]], field: str) -> bool:
    return any(_num(item.get(field)) > 0 for item in items)


def calculate_finance_snapshot(payload: dict[str, Any], thresholds: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    resolved_thresholds = merge_finance_thresholds(thresholds)
    entries = payload.get("entries") or []
    services = payload.get("services") or []
    staff = payload.get("staff") or []
    workplaces = payload.get("workplaces") or []
    workplace_metrics = payload.get("workplace_metrics") or []

    revenue_entries = [item for item in entries if _text(item.get("type")).lower() == "revenue"]
    expense_entries = [item for item in entries if _text(item.get("type")).lower() == "expense"]

    entry_revenue = sum(_num(item.get("amount")) for item in revenue_entries)
    service_revenue = sum(_num(item.get("revenue")) for item in services)
    workplace_revenue = sum(_num(item.get("revenue")) for item in workplace_metrics)
    revenue = max(entry_revenue, service_revenue, workplace_revenue)
    has_expense_data = len(expense_entries) > 0
    has_service_cost_data = _has_positive(services, "material_cost") or _has_positive(services, "staff_payout")

    expenses = sum(_num(item.get("amount")) for item in expense_entries)
    fixed_costs = sum(
        _num(item.get("amount"))
        for item in expense_entries
        if _text(item.get("category")).lower() in FIXED_EXPENSE_CATEGORIES
    )
    payroll_from_expenses = sum(
        _num(item.get("amount"))
        for item in expense_entries
        if _text(item.get("category")).lower() in PAYROLL_CATEGORIES
    )
    materials_from_expenses = sum(
        _num(item.get("amount"))
        for item in expense_entries
        if _text(item.get("category")).lower() in MATERIAL_CATEGORIES
    )

    staff_payouts = sum(_num(item.get("staff_payout")) for item in services)
    material_costs = sum(_num(item.get("material_cost")) for item in services)
    payroll_total = max(payroll_from_expenses, staff_payouts)
    materials_total = max(materials_from_expenses, material_costs)
    variable_costs = payroll_total + materials_total
    gross_profit = revenue - variable_costs if has_service_cost_data else None
    operating_profit = revenue - expenses if has_expense_data else None

    visits_count = sum(_num(item.get("visits_count")) for item in services)
    if visits_count <= 0:
        visits_count = sum(_num(item.get("visits_count")) for item in staff)
    if visits_count <= 0:
        visits_count = len(revenue_entries)

    no_show_count = sum(_num(item.get("no_show_count")) for item in staff)
    rebooking_count = sum(_num(item.get("rebooking_count")) for item in staff)
    booked_minutes = sum(_num(item.get("booked_minutes")) for item in staff)
    available_minutes = sum(_num(item.get("available_minutes")) for item in staff)

    active_workplaces = len([item for item in workplaces if item.get("is_active", True)])
    workplace_available_minutes = sum(_num(item.get("available_minutes")) for item in workplace_metrics)
    workplace_booked_minutes = sum(_num(item.get("booked_minutes")) for item in workplace_metrics)
    workplace_gross_profit = sum(_num(item.get("gross_profit")) for item in workplace_metrics)
    has_workplace_profit_data = workplace_gross_profit > 0
    if not has_workplace_profit_data and gross_profit is not None:
        workplace_gross_profit = gross_profit

    gross_margin = (
        _pct(gross_profit, revenue, "Недостаточно выручки для расчета валовой маржи")
        if gross_profit is not None
        else {"value": None, "explanation": "Добавьте себестоимость материалов и выплаты мастерам для расчета валовой маржи"}
    )
    operating_margin = (
        _pct(operating_profit, revenue, "Недостаточно выручки для расчета операционной маржи")
        if operating_profit is not None
        else {"value": None, "explanation": "Добавьте расходы для расчета операционной прибыли и маржи"}
    )
    average_ticket = _safe_div(revenue, visits_count, "Нет визитов для расчета среднего чека")
    no_show_rate = _pct(no_show_count, visits_count + no_show_count, "Нет записей со статусами для расчета no-show")
    rebooking_rate = _pct(rebooking_count, visits_count, "Нет визитов для расчета повторной записи")
    staff_occupancy = _pct(booked_minutes, available_minutes, "Нет рабочих часов мастеров")
    workplace_occupancy = _pct(
        workplace_booked_minutes,
        workplace_available_minutes,
        "Нет доступных часов рабочих мест",
    )

    gross_margin_decimal = None
    if gross_margin["value"] is not None:
        gross_margin_decimal = gross_margin["value"] / 100
    break_even = _safe_div(
        fixed_costs,
        gross_margin_decimal or 0,
        "Нужна валовая маржа и постоянные расходы для расчета точки безубыточности",
    )
    daily_target = _safe_div(
        break_even["value"] or 0,
        22,
        "Нужна точка безубыточности для расчета дневной цели",
    )

    workplace_available_hours = workplace_available_minutes / 60
    workplace_booked_hours = workplace_booked_minutes / 60
    revenue_per_workplace = _safe_div(
        revenue,
        active_workplaces,
        "Добавьте активные кресла, кабинеты или рабочие места",
    )
    gross_profit_per_workplace = (
        _safe_div(workplace_gross_profit, active_workplaces, "Добавьте активные кресла, кабинеты или рабочие места")
        if gross_profit is not None or has_workplace_profit_data
        else {"value": None, "explanation": "Добавьте себестоимость или валовую прибыль по рабочим местам"}
    )
    revenue_per_workplace_hour = _safe_div(
        revenue,
        workplace_available_hours,
        "Добавьте доступные часы рабочих мест",
    )
    gross_profit_per_workplace_hour = (
        _safe_div(workplace_gross_profit, workplace_available_hours, "Добавьте доступные часы рабочих мест")
        if gross_profit is not None or has_workplace_profit_data
        else {"value": None, "explanation": "Добавьте себестоимость или валовую прибыль по рабочим местам"}
    )

    service_rows = []
    low_margin_count = 0
    for item in services:
        item_revenue = _num(item.get("revenue"))
        item_visits = _num(item.get("visits_count"))
        item_materials = _num(item.get("material_cost"))
        item_payout = _num(item.get("staff_payout"))
        item_duration = _num(item.get("duration_minutes"))
        has_item_cost_data = item_materials > 0 or item_payout > 0
        item_profit = item_revenue - item_materials - item_payout if has_item_cost_data else None
        item_margin = (
            _pct(item_profit, item_revenue, "Нет выручки услуги")
            if item_profit is not None
            else {"value": None, "explanation": "Нет себестоимости или выплаты мастеру"}
        )
        item_hours = item_duration * item_visits / 60
        item_revenue_hour = _safe_div(item_revenue, item_hours, "Нет длительности или продаж услуги")
        item_profit_hour = (
            _safe_div(item_profit, item_hours, "Нет длительности или продаж услуги")
            if item_profit is not None
            else {"value": None, "explanation": "Нет себестоимости или выплаты мастеру"}
        )
        row = {
            "service_name": item.get("service_name"),
            "category": item.get("category"),
            "revenue": item_revenue,
            "visits_count": item_visits,
            "avg_price": _num(item.get("avg_price")),
            "duration_minutes": item_duration,
            "material_cost": item_materials,
            "staff_payout": item_payout,
            "gross_profit": item_profit,
            "gross_margin": item_margin["value"],
            "revenue_per_hour": item_revenue_hour["value"],
            "gross_profit_per_hour": item_profit_hour["value"],
        }
        row["status"] = classify_service(row)
        if item_margin["value"] is not None and item_margin["value"] < 30:
            low_margin_count += 1
        service_rows.append(row)

    low_margin_share = (
        _pct(low_margin_count, len(services), "Нет услуг для расчета доли низкомаржинальных")
        if has_service_cost_data
        else {"value": None, "explanation": "Добавьте себестоимость услуг для расчета низкомаржинальных услуг"}
    )
    payroll_share = (
        _pct(payroll_total, revenue, "Недостаточно выручки для расчета доли ФОТ")
        if payroll_total > 0
        else {"value": None, "explanation": "Добавьте ФОТ или выплаты мастерам для расчета доли ФОТ"}
    )
    material_share = (
        _pct(materials_total, revenue, "Недостаточно выручки для расчета доли материалов")
        if materials_total > 0
        else {"value": None, "explanation": "Добавьте себестоимость материалов для расчета доли материалов"}
    )

    staff_rows = []
    for item in staff:
        staff_visits = _num(item.get("visits_count"))
        staff_booked = _num(item.get("booked_minutes"))
        staff_available = _num(item.get("available_minutes"))
        staff_no_show = _num(item.get("no_show_count"))
        staff_rebooking = _num(item.get("rebooking_count"))
        staff_revenue = _num(item.get("revenue"))
        staff_rows.append(
            {
                "staff_name": item.get("staff_name"),
                "role": item.get("role"),
                "revenue": staff_revenue,
                "visits_count": staff_visits,
                "average_ticket": _safe_div(staff_revenue, staff_visits, "Нет визитов мастера")["value"],
                "occupancy": _pct(staff_booked, staff_available, "Нет рабочих часов мастера")["value"],
                "rebooking_rate": _pct(staff_rebooking, staff_visits, "Нет повторных записей мастера")["value"],
                "no_show_rate": _pct(staff_no_show, staff_visits + staff_no_show, "Нет статусов записей мастера")["value"],
            }
        )

    workplace_rows = []
    workplace_names = {item.get("id"): item.get("name") for item in workplaces}
    workplace_types = {item.get("id"): item.get("type") for item in workplaces}
    for item in workplace_metrics:
        available = _num(item.get("available_minutes"))
        booked = _num(item.get("booked_minutes"))
        item_revenue = _num(item.get("revenue"))
        item_profit = _num(item.get("gross_profit"))
        hours = available / 60
        workplace_id = item.get("workplace_id")
        workplace_rows.append(
            {
                "workplace_id": workplace_id,
                "name": workplace_names.get(workplace_id) or item.get("name") or "Рабочее место",
                "type": workplace_types.get(workplace_id) or item.get("type") or "other",
                "available_hours": hours,
                "booked_hours": booked / 60,
                "idle_hours": max((available - booked) / 60, 0),
                "occupancy": _pct(booked, available, "Нет доступных часов рабочего места")["value"],
                "revenue": item_revenue,
                "gross_profit": item_profit if has_workplace_profit_data or gross_profit is not None else None,
                "revenue_per_hour": _safe_div(item_revenue, hours, "Нет доступных часов рабочего места")["value"],
                "gross_profit_per_hour": _safe_div(item_profit, hours, "Нет валовой прибыли или доступных часов рабочего места")["value"] if has_workplace_profit_data or gross_profit is not None else None,
            }
        )

    kpis = {
        "revenue": revenue,
        "expenses": expenses,
        "operating_profit": operating_profit,
        "operating_margin": operating_margin["value"],
        "fixed_costs": fixed_costs,
        "variable_costs": variable_costs,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin["value"],
        "break_even_revenue": break_even["value"],
        "daily_revenue_target": daily_target["value"],
        "payroll_share": payroll_share["value"],
        "material_share": material_share["value"],
        "average_ticket": average_ticket["value"],
        "visits_count": visits_count,
        "no_show_rate": no_show_rate["value"],
        "rebooking_rate": rebooking_rate["value"],
        "staff_occupancy": staff_occupancy["value"],
        "low_margin_services_share": low_margin_share["value"],
        "active_workplaces": active_workplaces,
        "available_workplace_hours": workplace_available_hours,
        "booked_workplace_hours": workplace_booked_hours,
        "idle_workplace_hours": max(workplace_available_hours - workplace_booked_hours, 0),
        "workplace_occupancy": workplace_occupancy["value"],
        "revenue_per_workplace": revenue_per_workplace["value"],
        "gross_profit_per_workplace": gross_profit_per_workplace["value"],
        "revenue_per_workplace_hour": revenue_per_workplace_hour["value"],
        "gross_profit_per_workplace_hour": gross_profit_per_workplace_hour["value"],
    }

    explanations = {
        "operating_margin": operating_margin["explanation"],
        "gross_margin": gross_margin["explanation"],
        "break_even_revenue": break_even["explanation"],
        "daily_revenue_target": daily_target["explanation"],
        "average_ticket": average_ticket["explanation"],
        "no_show_rate": no_show_rate["explanation"],
        "rebooking_rate": rebooking_rate["explanation"],
        "workplace_occupancy": workplace_occupancy["explanation"],
        "revenue_per_workplace": revenue_per_workplace["explanation"],
        "revenue_per_workplace_hour": revenue_per_workplace_hour["explanation"],
    }

    data_quality = calculate_data_quality(payload, explanations)
    recommendations = build_finance_recommendations(kpis, resolved_thresholds)

    return {
        "kpis": kpis,
        "explanations": {key: value for key, value in explanations.items() if value},
        "data_quality": data_quality,
        "recommendations": recommendations,
        "services": service_rows,
        "staff": staff_rows,
        "workplaces": workplace_rows,
        "statuses": build_kpi_statuses(kpis, resolved_thresholds),
        "thresholds": resolved_thresholds,
    }


def calculate_data_quality(payload: dict[str, Any], explanations: dict[str, Any] | None = None) -> dict[str, Any]:
    services = payload.get("services") or []
    staff = payload.get("staff") or []
    workplaces = payload.get("workplaces") or []
    workplace_metrics = payload.get("workplace_metrics") or []
    entries = payload.get("entries") or []

    missing = []
    approximate = []
    precise = []
    score = 100
    has_revenue = any(_text(item.get("type")).lower() == "revenue" for item in entries) or _has_positive(services, "revenue")
    has_service_visits = _has_positive(services, "visits_count")
    has_staff_visits = _has_positive(staff, "visits_count")
    has_expenses = any(_text(item.get("type")).lower() == "expense" for item in entries)
    has_service_costs = _has_positive(services, "material_cost") or _has_positive(services, "staff_payout")

    if has_revenue:
        precise.append("выручка")
    if has_revenue and (has_service_visits or has_staff_visits or entries):
        precise.append("средний чек")
    if has_service_visits:
        precise.append("продажи услуг")
    if has_staff_visits:
        precise.append("визиты и записи")
    if staff and (_has_positive(staff, "no_show_count") or _has_positive(staff, "rebooking_count")):
        precise.append("no-show и повторные записи")
    if workplace_metrics and _has_positive(workplace_metrics, "available_minutes"):
        precise.append("загрузка рабочих мест")

    if not has_expenses:
        missing.append("расходы")
        score -= 15
    if not services:
        missing.append("услуги")
        score -= 10
    if services and any(_num(item.get("duration_minutes")) <= 0 for item in services):
        missing.append("длительность услуг")
        approximate.append("маржа и выручка на час по услугам")
        score -= 8
    if services and not has_service_costs:
        missing.append("себестоимость материалов")
        approximate.append("валовая маржа услуг")
        score -= 8
    if services and not _has_positive(services, "staff_payout"):
        missing.append("выплаты мастерам")
        approximate.append("прибыльность услуг")
        score -= 8
    if not staff:
        missing.append("мастера")
        score -= 8
    if staff and all(_num(item.get("no_show_count")) <= 0 for item in staff):
        missing.append("no-show")
        score -= 6
    if staff and all(_num(item.get("rebooking_count")) <= 0 for item in staff):
        missing.append("повторная запись")
        score -= 6
    if not workplaces:
        missing.append("кресла, кабинеты или рабочие места")
        score -= 12
    if workplaces and not workplace_metrics:
        missing.append("загрузка рабочих мест")
        approximate.append("выручка на кресло-час")
        score -= 10
    if workplace_metrics and any(_num(item.get("available_minutes")) <= 0 for item in workplace_metrics):
        missing.append("доступные часы рабочих мест")
        approximate.append("загрузка рабочих мест")
        score -= 10
    if workplace_metrics and any(_num(item.get("booked_minutes")) <= 0 for item in workplace_metrics):
        missing.append("занятые часы рабочих мест")
        approximate.append("простой рабочих мест")
        score -= 8

    if not explanations:
        explanations = {}
    blocked = [key for key, value in explanations.items() if value]

    return {
        "score": max(score, 0),
        "missing": list(dict.fromkeys(missing)),
        "approximate": list(dict.fromkeys(approximate)),
        "precise": precise,
        "blocked": blocked,
        "can_analyze": precise,
    }


def build_kpi_statuses(kpis: dict[str, Any], thresholds: dict[str, dict[str, Any]] | None = None) -> dict[str, str]:
    resolved_thresholds = merge_finance_thresholds(thresholds)
    return {
        key: threshold_status(kpis.get(key), threshold)
        for key, threshold in resolved_thresholds.items()
    }


def build_finance_recommendations(kpis: dict[str, Any], thresholds: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    items = []
    resolved_thresholds = merge_finance_thresholds(thresholds)
    statuses = build_kpi_statuses(kpis, resolved_thresholds)

    def add(
        code: str,
        title: str,
        text: str,
        severity: str = "medium",
        target_metric: str | None = None,
        data_needed: list[str] | None = None,
        actions: dict[str, list[str]] | None = None,
        localos_actions: list[dict[str, str]] | None = None,
    ) -> None:
        items.append({
            "code": code,
            "title": title,
            "text": text,
            "severity": severity,
            "target_metric": target_metric,
            "data_needed": data_needed or [],
            "actions": actions or {
                "today": [],
                "seven_days": [],
                "regular": [],
            },
            "localos_actions": localos_actions or [],
        })

    operating_margin = kpis.get("operating_margin")
    if operating_margin is not None and statuses.get("operating_margin") == "red":
        add(
            "low_operating_margin",
            "Бизнес в красной зоне по марже",
            f"{describe_metric_value('operating_margin', operating_margin, resolved_thresholds)}. Проверьте ФОТ, материалы, низкомаржинальные услуги и загрузку рабочих мест.",
            "high",
            "operating_margin",
            ["расходы", "ФОТ", "материалы", "маржа услуг", "загрузка рабочих мест"],
            {
                "today": [
                    "Сверить выручку и все расходы за последние 3 месяца.",
                    "Отметить 5 самых дорогих статей расходов.",
                ],
                "seven_days": [
                    "Проверить услуги с низкой маржей и долгой длительностью.",
                    "Собрать план повышения цен или сокращения затрат по каждой проблемной услуге.",
                ],
                "regular": [
                    "Раз в неделю смотреть операционную маржу и долю ФОТ.",
                    "Не запускать акции без проверки маржи и загрузки.",
                ],
            },
            [
                {
                    "label": "Проверить услуги",
                    "description": "Найти низкомаржинальные услуги и не продвигать их вслепую.",
                    "route": "/dashboard/card",
                },
                {
                    "label": "Запланировать публикации",
                    "description": "Заполнить спрос услугами с лучшей экономикой.",
                    "route": "/dashboard/card",
                },
            ],
        )

    payroll_share = kpis.get("payroll_share")
    if payroll_share is not None and statuses.get("payroll_share") == "red":
        add(
            "high_payroll_share",
            "ФОТ съедает слишком большую долю выручки",
            f"{describe_metric_value('payroll_share', payroll_share, resolved_thresholds)}. Проверьте выплаты, расписание и вклад мастеров в выручку.",
            "high",
            "payroll_share",
            ["выручка по мастерам", "выплаты мастерам", "рабочие часы", "визиты"],
            {
                "today": [
                    "Сравнить выручку и выплаты по каждому мастеру.",
                    "Найти смены, где выплаты есть, а загрузка низкая.",
                ],
                "seven_days": [
                    "Пересобрать расписание слабых смен.",
                    "Проверить, какие мастера дают низкий средний чек или мало повторных записей.",
                ],
                "regular": [
                    "Еженедельно смотреть долю ФОТ и вклад каждого мастера.",
                    "Привязывать продвижение к мастерам и услугам с лучшей экономикой.",
                ],
            },
            [
                {
                    "label": "Посмотреть записи",
                    "description": "Сверить загрузку мастеров и слабые смены.",
                    "route": "/dashboard/bookings",
                },
            ],
        )

    material_share = kpis.get("material_share")
    if material_share is not None and statuses.get("material_share") == "red":
        add(
            "high_material_share",
            "Материалы выше нормы",
            f"{describe_metric_value('material_share', material_share, resolved_thresholds)}. Проверьте себестоимость услуг, списания и расходники.",
            "medium",
            "material_share",
            ["себестоимость материалов", "списания", "услуги", "выручка"],
            {
                "today": [
                    "Проверить услуги с самым большим расходом материалов.",
                    "Отделить реальные материалы от общих закупок.",
                ],
                "seven_days": [
                    "Обновить себестоимость материалов в карточках услуг.",
                    "Найти услуги, где цена не покрывает материалы и выплату мастеру.",
                ],
                "regular": [
                    "Раз в месяц сверять закупки с фактическими продажами.",
                    "Не продвигать услуги, где материалы съедают маржу.",
                ],
            },
            [
                {
                    "label": "Открыть услуги",
                    "description": "Обновить себестоимость, длительность и приоритет продвижения.",
                    "route": "/dashboard/card",
                },
            ],
        )

    no_show_rate = kpis.get("no_show_rate")
    if no_show_rate is not None and statuses.get("no_show_rate") == "red":
        add(
            "high_no_show",
            "Неявки забирают деньги",
            f"{describe_metric_value('no_show_rate', no_show_rate, resolved_thresholds)}. Введите подтверждения, предоплату и лист ожидания на ближайшие окна.",
            "high",
            "no_show_rate",
            ["записи", "неявки", "отмены", "канал записи"],
            {
                "today": [
                    "Посчитать неявки за последние 30 дней по мастерам и дням недели.",
                    "Включить ручное подтверждение ближайших записей.",
                ],
                "seven_days": [
                    "Ввести напоминания и предоплату для дорогих или длинных услуг.",
                    "Собрать лист ожидания для заполнения внезапных окон.",
                ],
                "regular": [
                    "Каждую неделю смотреть no-show по каналам записи.",
                    "Отдельно обрабатывать клиентов, которые уже не приходили.",
                ],
            },
            [
                {
                    "label": "Проверить записи",
                    "description": "Найти ближайшие записи, где нужно подтверждение.",
                    "route": "/dashboard/bookings",
                },
                {
                    "label": "Настроить бота",
                    "description": "Подготовить напоминания и подтверждение записи.",
                    "route": "/dashboard/chats",
                },
            ],
        )

    rebooking_rate = kpis.get("rebooking_rate")
    if rebooking_rate is not None and statuses.get("rebooking_rate") == "red":
        add(
            "low_rebooking",
            "Клиенты уходят без следующей записи",
            f"{describe_metric_value('rebooking_rate', rebooking_rate, resolved_thresholds)}. Добавьте обязательное мягкое предложение следующего визита перед выходом клиента.",
            "medium",
            "rebooking_rate",
            ["визиты", "повторные записи", "мастера", "услуги"],
            {
                "today": [
                    "Попросить мастеров предлагать следующий визит до ухода клиента.",
                    "Подготовить 2 короткие фразы для записи на следующий визит.",
                ],
                "seven_days": [
                    "Проверить rebooking по каждому мастеру.",
                    "Добавить напоминание клиентам после первого визита.",
                ],
                "regular": [
                    "Раз в неделю смотреть клиентов без следующей записи.",
                    "Возвращать базу клиентов через сообщения и публикации.",
                ],
            },
            [
                {
                    "label": "Настроить коммуникации",
                    "description": "Подготовить мягкие сообщения для следующей записи.",
                    "route": "/dashboard/chats",
                },
                {
                    "label": "Проверить записи",
                    "description": "Найти клиентов без следующего визита.",
                    "route": "/dashboard/bookings",
                },
            ],
        )

    occupancy = kpis.get("workplace_occupancy")
    revenue_hour = kpis.get("revenue_per_workplace_hour")
    if occupancy is not None and statuses.get("workplace_occupancy") == "red":
        add(
            "low_workplace_occupancy",
            "Рабочие места простаивают",
            f"{describe_metric_value('workplace_occupancy', occupancy, resolved_thresholds)}. Сначала заполняйте окна на завтра и неделю: база клиентов, локальные партнерства, публикации.",
            "medium",
            "workplace_occupancy",
            ["рабочие места", "доступные часы", "занятые часы", "выручка по местам"],
            {
                "today": [
                    "Найти ближайшие пустые окна на завтра и послезавтра.",
                    "Сделать короткое предложение для возврата базы клиентов.",
                ],
                "seven_days": [
                    "Запустить публикации под слабые дни недели.",
                    "Найти 3 локальных партнера рядом с бизнесом.",
                ],
                "regular": [
                    "Каждую неделю смотреть простой по рабочим местам.",
                    "Продвигать услуги, которые заполняют пустые часы и дают маржу.",
                ],
            },
            [
                {
                    "label": "Сделать публикации",
                    "description": "Заполнить слабые дни недели через новости и соцсети.",
                    "route": "/dashboard/card",
                },
                {
                    "label": "Найти партнеров",
                    "description": "Подобрать локальные партнерства вокруг точки.",
                    "route": "/dashboard/partnerships",
                },
            ],
        )
    if occupancy is not None and occupancy > 85 and revenue_hour is not None and statuses.get("revenue_per_workplace_hour") == "red":
        add(
            "busy_low_revenue_hour",
            "Кресла загружены, но час стоит дешево",
            f"{describe_metric_value('revenue_per_workplace_hour', revenue_hour, resolved_thresholds)}. Проверьте цены, длительность процедур и меню услуг.",
            "high",
            "revenue_per_workplace_hour",
            ["длительность услуг", "цены", "выручка по рабочим местам", "занятые часы"],
            {
                "today": [
                    "Найти услуги, которые занимают много времени и дают низкую выручку в час.",
                    "Сравнить цену и длительность с услугами-лидерами.",
                ],
                "seven_days": [
                    "Поднять цену или сократить длительность для слабых услуг.",
                    "Перенести продвижение на услуги с большей выручкой в час.",
                ],
                "regular": [
                    "Раз в месяц пересматривать меню услуг по выручке на час.",
                    "Следить, чтобы высокая загрузка не маскировала низкую прибыль.",
                ],
            },
            [
                {
                    "label": "Оптимизировать услуги",
                    "description": "Пересобрать меню услуг по цене, длительности и спросу.",
                    "route": "/dashboard/card",
                },
            ],
        )

    idle_hours = kpis.get("idle_workplace_hours")
    if idle_hours is not None and idle_hours >= 20:
        add(
            "idle_workplace_hours",
            "Много пустых часов",
            "Начните с ближайших окон: завтра, выходные и самые слабые смены.",
            "medium",
            "idle_workplace_hours",
            ["доступные часы", "занятые часы", "расписание", "пустые окна"],
            {
                "today": [
                    "Выписать пустые окна на ближайшие 2 дня.",
                    "Отправить клиентам мягкое предложение на свободное время.",
                ],
                "seven_days": [
                    "Собрать регулярный план публикаций под свободные окна.",
                    "Проверить, какие мастера и услуги чаще простаивают.",
                ],
                "regular": [
                    "Каждое утро смотреть окна на сегодня и завтра.",
                    "Держать короткий список клиентов для быстрого дозаполнения.",
                ],
            },
            [
                {
                    "label": "Запустить публикации",
                    "description": "Дать повод записаться на ближайшие свободные окна.",
                    "route": "/dashboard/card",
                },
                {
                    "label": "Подключить партнерства",
                    "description": "Найти соседние бизнесы для обмена аудиторией.",
                    "route": "/dashboard/partnerships",
                },
            ],
        )

    profit_hour = kpis.get("gross_profit_per_workplace_hour")
    if profit_hour is not None and statuses.get("gross_profit_per_workplace_hour") == "red":
        add(
            "low_profit_per_workplace_hour",
            "Рабочее место приносит мало прибыли за час",
            f"{describe_metric_value('gross_profit_per_workplace_hour', profit_hour, resolved_thresholds)}. Проверьте себестоимость, выплату мастеру, цену и длительность услуги.",
            "medium",
            "gross_profit_per_workplace_hour",
            ["валовая прибыль", "материалы", "выплаты мастерам", "длительность услуг"],
            {
                "today": [
                    "Найти услуги с низкой прибылью на час.",
                    "Проверить, не занижены ли материалы или выплаты в учете.",
                ],
                "seven_days": [
                    "Обновить цены, длительность или состав услуги.",
                    "Убрать слабые услуги из активного продвижения.",
                ],
                "regular": [
                    "Раз в месяц проверять прибыль на кресло-час.",
                    "Продвигать услуги с понятной экономикой, а не просто высоким спросом.",
                ],
            },
            [
                {
                    "label": "Проверить карточку",
                    "description": "Сместить акцент на услуги с хорошей прибылью за час.",
                    "route": "/dashboard/card",
                },
            ],
        )

    low_margin_share = kpis.get("low_margin_services_share")
    if low_margin_share is not None and statuses.get("low_margin_services_share") == "red":
        add(
            "many_low_margin_services",
            "Слишком много услуг создают занятость без прибыли",
            f"{describe_metric_value('low_margin_services_share', low_margin_share, resolved_thresholds)}. Пересоберите меню услуг: что поднимать в цене, что сокращать, что не продвигать.",
            "high",
            "low_margin_services_share",
            ["маржа услуг", "цены", "материалы", "выплаты мастерам"],
            {
                "today": [
                    "Отметить все услуги с маржей ниже нормы.",
                    "Разделить их на входные, ошибочно дешевые и неприоритетные.",
                ],
                "seven_days": [
                    "Поднять цены или сократить затраты по ошибочно дешевым услугам.",
                    "Не ставить низкомаржинальные услуги в рекламу и публикации без причины.",
                ],
                "regular": [
                    "Раз в месяц пересматривать меню услуг.",
                    "Использовать входные услуги только как путь к следующей покупке.",
                ],
            },
            [
                {
                    "label": "Открыть услуги",
                    "description": "Убрать слабые услуги из активного продвижения.",
                    "route": "/dashboard/card",
                },
            ],
        )

    if not items:
        add(
            "fill_data",
            "Начните с полноты данных",
            "Заполните расходы, услуги, мастеров и рабочие места за последние 3 месяца, чтобы увидеть настоящие красные зоны.",
            "low",
            "data_quality",
            ["расходы", "услуги", "мастера", "рабочие места", "no-show", "rebooking"],
            {
                "today": [
                    "Внести выручку, расходы и количество визитов за 3 месяца.",
                    "Добавить хотя бы основные рабочие места или кабинеты.",
                ],
                "seven_days": [
                    "Заполнить длительность, материалы и выплаты по ключевым услугам.",
                    "Добавить данные по мастерам, no-show и повторным записям.",
                ],
                "regular": [
                    "Обновлять данные раз в неделю.",
                    "После каждого обновления смотреть красные зоны и план действий.",
                ],
            },
            [
                {
                    "label": "Остаться в финансах",
                    "description": "Дозаполнить данные для точных KPI.",
                    "route": "/dashboard/finance",
                },
            ],
        )

    return items


def default_period_range(today: date | None = None) -> tuple[str, str]:
    if today is None:
        today = datetime.utcnow().date()
    start = date(today.year, today.month, 1)
    if today.month <= 3:
        month = today.month + 9
        year = today.year - 1
    else:
        month = today.month - 3
        year = today.year
    start = date(year, month, 1)
    return start.isoformat(), today.isoformat()
