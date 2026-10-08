"""Read-only presentation of the existing outreach group; no execution or grants."""
from __future__ import annotations

from typing import Any


class GroupNotFound(ValueError):
    pass


def load_group_scope(cursor, business_id: str, task_id: str) -> dict[str, Any]:
    cursor.execute("""SELECT id, result_json, payload_json FROM operator_async_jobs
        WHERE id::text=%s AND business_id=%s AND kind='outreach_continue'""", (task_id, business_id))
    found = cursor.fetchone()
    if not found:
        raise GroupNotFound("search_task_not_found")
    row = dict(found) if hasattr(found, "keys") else dict(zip(("id", "result_json", "payload_json"), found))
    row["lead_ids"] = list(dict.fromkeys(str(value) for value in (row.get("result_json") or {}).get("lead_ids") or []))
    return row


def group_url(task, section="companies"):
    return f"/dashboard/partnerships?business_id={task['business_id']}&search_task_id={task['id']}&section={section}"


BLOCKERS = {
    "draft_quality_review_required": "Черновики сохранены, но требуют правки по результатам проверки. Отправка не запускалась.",
    "draft_generation_failed": "Не удалось создать письма. Подходящие компании сохранены; проверьте причину в истории поиска.",
    "draft_sender_setup": "Для подготовки писем нужно заполнить сведения об отправителе. Подходящие компании сохранены.",
    "search_provider_timed_out": "Поисковый источник не успел вернуть компании. Измените условия поиска; результаты и фактические расходы сохранены.",
    "search_provider_run_failed": "Поисковый источник завершился с ошибкой. Проверьте условия поиска; повторный запуск не выполнен.",
    "search_cost_receipt_missing": "Сверяем стоимость завершённого поиска. Резерв сохраняется до подтверждения расходов.",
    "insufficient_credits": "Не хватает кредитов для следующего действия. Прогресс сохранён.",
    "access_revoked": "Доступ к работе отозван. Проверьте права доступа.",
    "ai_rules_revoked_or_changed": "Правила отправки изменены или отозваны. Требуется согласование.",
    "search_result_uncertain": "Уточняем результат предыдущего поиска. Повтор пока недоступен.",
    "qualification_result_uncertain": "Результат проверки не получен. Сначала требуется сверка.",
    "campaign_result_uncertain": "Результат подготовки письма не получен. Сначала требуется сверка.",
    "search_budget_exhausted": "Достигнут согласованный предел поисковых запросов.",
    "model_budget_exhausted": "Достигнут согласованный предел проверок или подготовки писем.",
    "preparation_step_failed": "Проверка остановилась из-за ошибки. Сохранённые компании доступны; посмотрите подробности.",
    "candidate_budget_exhausted": "Достигнут согласованный предел обработки компаний.",
    "sources_or_budget_exhausted": "Доступные источники или согласованные ограничения исчерпаны.",
    "sources_exhausted": "В согласованных источниках больше нет новых компаний.",
    "search_provider_minimum_exceeds_call_limit": "Для продолжения нужно изменить условия поиска.",
    "audience_and_drafts_review_required": "Посмотрите найденные компании и подготовленные письма.",
    "enrichment_timeout": "Получение контактов затянулось. Требуется проверить результаты.",
    "qualification_unavailable": "Часть компаний не удалось проверить. Остальные результаты сохранены.",
}
NO_RESUME = set(BLOCKERS) - {"insufficient_credits", "enrichment_timeout", "qualification_unavailable"}


def presentation(task, *, draft_job=None, available_credits=None):
    config, state, report = task.get("config") or {}, task.get("state") or {}, task.get("report") or {}
    drafts = draft_job or {}
    draft_state = drafts.get("result_json") or {}
    draft_active = drafts.get("status") in {"queued", "running"}
    draft_blocked = drafts.get("status") in {"waiting_for_review", "failed"}
    search_active = task["status"] in {"queued", "running"}
    letters_phase = config.get("mode") != "find_only" and state.get("phase") == "prepare" and not report.get("awaiting_check") and not report.get("checking") and bool(report.get("eligible"))
    phase = "letters" if draft_active or draft_blocked or letters_phase else "companies"
    if not search_active and not draft_active and not draft_blocked:
        phase = "replies" if report.get("replies") or report.get("confirmed_sent") else "sending" if report.get("queued") else "letters" if report.get("prepared") else phase
    blocker = (draft_state.get("blocker") or ("insufficient_credits" if any(item.get("reason") == "insufficient_credits" for item in draft_state.get("errors") or []) else None)) if draft_blocked else state.get("blocker")
    unsettled = bool(state.get("inflight_search") or report.get("delivery_uncertain"))
    labels = {"companies": "Проверяем компании и контакты" if state.get("phase") == "prepare" else "Ищем компании",
              "letters": "Готовим письма", "sending": "Отправляем", "replies": "Ожидаем ответы"}
    stopped = task["status"] == "cancelled"
    if stopped:
        blocker = None
    running = (search_active or draft_active) and not stopped
    external_search_active = search_active and state.get("phase") == "search_poll" and bool((state.get("search_run") or {}).get("id")) and not blocker
    status = "queued" if (task["status"] == "queued" and not external_search_active) or drafts.get("status") == "queued" else "running" if running else "stopped" if task["status"] == "cancelled" else "completed" if task["status"] == "completed" and not draft_blocked else "needs_attention" if blocker or drafts.get("status") == "failed" else "paused" if state.get("started") else "ready"
    label = labels[phase] if running else "Результаты готовы" if status == "completed" else "Требуется действие" if status == "needs_attention" else "Поиск остановлен" if status == "stopped" else "Результаты готовы" if status == "completed" else "На паузе" if status == "paused" else "Ожидает запуска"
    if status == "queued":
        label = "Ожидает запуска"
    if not running and not stopped and not draft_blocked and phase == 'replies':
        label = 'Ожидаем ответы' if not report.get('replies') else 'Есть ответы'
    elif not running and not stopped and not draft_blocked and phase == 'sending':
        label = 'Отправляем' if report.get('sending') else 'Отправка ожидает запуска'
    elif not running and not stopped and not draft_blocked and not blocker and phase == 'letters':
        label = 'Письма готовы'
    action = {"kind": "link", "label": "Посмотреть письма" if phase == "letters" else "Посмотреть ответы" if phase == "replies" else "Посмотреть отправку" if phase == "sending" else "Посмотреть компании",
              "href": group_url(task, {"companies": "companies", "letters": "drafts", "sending": "queue", "replies": "sent"}[phase])}
    required = 1 if state.get("phase") == "prepare" or draft_blocked else report.get("search_credits_each")
    if stopped:
        pass
    elif blocker == "insufficient_credits" and (available_credits is None or required is None or available_credits < required):
        action = {"kind": "link", "label": "Пополнить баланс", "href": f"/dashboard/profile?business_id={task['business_id']}&focus=subscription#subscription"}
    elif blocker == "draft_quality_review_required":
        action = {"kind": "link", "label": "Проверить письма", "href": group_url(task, "drafts")}
    elif blocker == "draft_sender_setup":
        blocked = next((value for value in (state.get("campaign_results") or {}).values() if value.get("status") == "needs_sender_setup"), {})
        action = {"kind": "link", "label": "Настроить отправителя", "href": group_url(task) + "&lead=" + str(blocked.get("lead_id") or "")}
    elif blocker in {"search_provider_timed_out", "search_provider_run_failed", "search_cost_receipt_missing"}:
        action = {"kind": "link", "label": "Посмотреть условия поиска", "href": group_url(task)}
    elif drafts.get("status") == "waiting_for_review" and (not blocker or blocker == "insufficient_credits"):
        action = {"kind": "draft_resume", "label": "Продолжить подготовку писем", "job_id": str(drafts["id"])}
    elif not running and not draft_blocked and task["status"] in {"waiting_for_review", "failed"} and not unsettled and blocker not in NO_RESUME:
        action = {"kind": "control", "action": "resume" if state.get("started") else "start",
                  "label": "Продолжить подготовку писем" if letters_phase else "Продолжить поиск и проверку" if state.get("started") else "Начать поиск"}
    elif running:
        action = {"kind": "control", "action": "pause", "label": "Приостановить поиск" if phase == "companies" else "Приостановить подготовку писем" if phase == "letters" else "Приостановить работу"}
    reason = BLOCKERS.get(blocker, "Работа остановилась. Посмотрите подробности.") if blocker else None
    if status == "completed" and phase == "companies" and report.get("shortfall"):
        reason = f"Подходящих компаний: {report.get('eligible', 0)} из {config.get('target_count', 0)}. Доступные источники или согласованные ограничения исчерпаны."
    if drafts.get('status') == 'failed':
        reason = 'Подготовка писем прервана. Сохранённые тексты доступны; проверьте подробности.'
    elif int(draft_state.get('failed') or 0) and drafts.get('status') == 'completed':
        reason = f"Не удалось подготовить писем: {int(draft_state['failed'])}. Остальные тексты сохранены."
    if unsettled:
        reason = "Уточняем результат выполненного действия. Повтор не запустит новое действие до сверки."
    return {"phase": phase, "status": status, "label": label, "reason": reason, "blocker": blocker,
            "next_action": action, "active": running, "substeps": state.get("substeps") or [],
            "achievements": achievements(task),
            "updated_at": task.get("updated_at"), "reply_sync": task.get("reply_sync"), "available_credits": available_credits,
            "required_credits": required, "send_mode": "automatic_authorized" if report.get("automatic_send_authorized") else "manual",
            "metrics": {"found": report.get("found", report.get("imported", 0)), "eligible": report.get("eligible", 0),
                        "target": config.get("target_count"), "needs_decision": report.get("needs_decision", report.get("verification_failed", 0)),
                        "awaiting_check": report.get("awaiting_check", 0), "prepared": report.get("prepared", 0),
                        "queued": report.get("queued", 0), "sent": report.get("confirmed_sent", 0), "replies": report.get("replies", 0)},
            "expenses": {"charged": report.get("group_credits_charged", report.get("credits_charged")),
                         "estimate": report.get("credit_limit"), "estimate_only": report.get("credit_estimate_only", False)}}



def achievements(task):
    """Completed outputs from durable data, not a timer or inferred provider state."""
    report, state = task.get("report") or {}, task.get("state") or {}
    enrichment = next((step for step in state.get("substeps") or [] if step.get("id") == "enrichment"), {})
    values = [
        ("replies", report.get("replies"), "Получено ответов"),
        ("sent", report.get("confirmed_sent"), "Отправлено писем · подтверждено провайдером"),
        ("letters", report.get("prepared"), "Черновики требуют проверки" if report.get("blocker") == "draft_quality_review_required" else "Письма подготовлены"),
        ("qualified", report.get("eligible"), "Подходят с подтверждённым контактом"),
        ("enriched", enrichment.get("processed"), "Собраны сведения о компаниях"),
        ("found", report.get("found", report.get("imported")), "Найдено кандидатов"),
        ("duplicates", report.get("duplicates"), "Исключено дублей"),
    ]
    return [{"id": key, "label": label, "count": int(count)}
            for key, count, label in values if count and int(count) > 0][:3]

def company_substeps(task, jobs):
    """Completed collection is separate from suitability and letter readiness."""
    report, state = task.get("report") or {}, task.get("state") or {}
    total = len(set(str(value) for value in state.get("lead_ids") or []))
    collected = sum(bool(job.get("completed_at")) for job in jobs)
    collecting = sum(job.get("status") in {"collecting", "verifying", "researching"} for job in jobs)
    queued = sum(job.get("status") in {"queued", "retry_wait"} for job in jobs)
    contacts = sum(bool((job.get("result_json") or {}).get("selected_contact_point_id")) for job in jobs)
    checked = int(report.get("checked") or 0)
    paused = task.get("status") not in {"running", "queued"}
    def step(key, label, processed, active, waiting, detail):
        status = "running" if active else "completed" if total and processed >= total else "queued" if waiting else "paused" if paused else "pending"
        return {"id": key, "label": label, "status": status, "processed": processed,
                "remaining": max(0, total-processed), "total": total, "detail": detail}
    return [
        {"id": "search", "label": "Поиск", "status": "running" if state.get("phase") in {"search", "search_poll"} and (task.get("status") == "running" or (task.get("status") == "queued" and bool((state.get("search_run") or {}).get("id")))) else "completed" if report.get("found") else "queued" if task.get("status") == "queued" else "pending",
         "processed": int(report.get("found") or 0), "detail": "Найденные кандидаты"},
        step("enrichment", "Контакты и сведения", collected, collecting, queued,
             f"Сведения собраны: {collected}; контакт выбран: {contacts}"),
        step("qualification", "Проверка соответствия", checked,
             bool(report.get("checking")), False,
             f"Подходят с подтверждённым контактом: {report.get('eligible', 0)}"),
    ]


def enrich_group(cursor, task, *, viewer_id=None):
    """Aggregate by durable group membership, independently of visible pages."""
    from services.outreach_continuation import qualified_contact_ids
    qualified_ids = qualified_contact_ids(task.get("state") or {})
    ids = list(dict.fromkeys(str(value) for value in task.get("state", {}).get("lead_ids") or []))
    cursor.execute("""SELECT * FROM operator_async_jobs WHERE business_id=%s
        AND kind='partner_search_drafts' AND payload_json->>'search_task_id'=%s
        ORDER BY created_at DESC LIMIT 1""", (task["business_id"], task["id"]))
    draft_job = dict(cursor.fetchone() or {})
    cursor.execute("""SELECT COUNT(DISTINCT d.lead_id) AS prepared
        FROM outreachmessagedrafts d JOIN prospectingleads l ON l.id=d.lead_id
        WHERE l.business_id=%s AND l.id::text=ANY(%s::text[])""", (task["business_id"], ids))
    task["report"]["prepared"] = max(task["report"].get("prepared", 0), int((cursor.fetchone() or {}).get("prepared") or 0))
    cursor.execute("""SELECT COUNT(*) AS needs_decision FROM lead_workstreams ws
        WHERE ws.client_business_id=%s AND ws.lead_id::text=ANY(%s::text[])
          AND ws.workstream_type='client_partnership'
          AND COALESCE(ws.status,'unprocessed') NOT IN ('not_relevant','disqualified','closed_lost','in_progress','contacted','replied','responded','waiting_reply','sent','delivered')
          AND ws.id::text <> ALL(%s::text[])""",
        (task["business_id"], ids, qualified_ids))
    task["report"]["needs_decision"] = int((cursor.fetchone() or {}).get("needs_decision") or 0)
    cursor.execute("""SELECT COALESCE(SUM(charged_credits),0) AS charged FROM operatorcreditreservations
        WHERE business_id=%s AND (metadata->>'task_id'=%s OR metadata->>'search_task_id'=%s)""",
        (task["business_id"], task["id"], task["id"]))
    task["report"]["group_credits_charged"] = int((cursor.fetchone() or {}).get("charged") or 0)
    available = None
    if viewer_id:
        from services.operator_credit_reservation import _load_user_balance, _load_active_reserved_credits
        balance, reserved = _load_user_balance(cursor, viewer_id), _load_active_reserved_credits(cursor, user_id=viewer_id)
        if balance is not None and reserved is not None:
            available = max(0, balance - reserved)
    if task.get("config", {}).get("mode") == "auto_send":
        from services.outreach_ai_authorization import for_job
        cursor.execute("SELECT * FROM operator_async_jobs WHERE id=%s AND business_id=%s", (task["id"], task["business_id"]))
        row = cursor.fetchone()
        task["report"]["automatic_send_authorized"] = bool(row and for_job(cursor, dict(row), require_running=False))
    cursor.execute("""SELECT DISTINCT ON (job.workstream_id) job.status, job.completed_at,
        job.result_json, job.updated_at FROM lead_enrichment_jobs job
        JOIN lead_workstreams ws ON ws.id=job.workstream_id
        WHERE ws.client_business_id=%s AND ws.workstream_type='client_partnership'
          AND ws.lead_id::text=ANY(%s::text[])
        ORDER BY job.workstream_id, job.created_at DESC""", (task["business_id"], ids))
    task["state"]["substeps"] = company_substeps(task, [dict(row) for row in cursor.fetchall()])
    cursor.execute("""SELECT sender.id, sender.status, sender.last_reply_sync_at, sender.reply_sync_error
        FROM outreach_sender_accounts sender
        WHERE sender.business_id=%s AND sender.channel='email' AND sender.outreach_enabled=TRUE
          AND COALESCE((sender.capabilities_json->>'reply_sync')::boolean,FALSE)=TRUE
        ORDER BY sender.updated_at DESC""", (task["business_id"],))
    senders = [dict(row) for row in cursor.fetchall()]
    task["reply_sync"] = {"configured": bool(senders),
        "needs_attention": any(row.get("reply_sync_error") or row.get("status") != "connected" for row in senders),
        "last_checked_at": str(max((row["last_reply_sync_at"] for row in senders if row.get("last_reply_sync_at")), default="")) or None}
    task["presentation"] = presentation(task, draft_job=draft_job, available_credits=available)
    task["draft_job"] = {key: draft_job.get(key) for key in ("id", "status", "result_json")} if draft_job else None
    return task
