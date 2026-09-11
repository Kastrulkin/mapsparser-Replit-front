"""Private owner-facing outcomes; candidates never count as confirmed partners."""
from copy import deepcopy
from datetime import datetime, timezone
from psycopg2.extras import Json

TERM_FIELDS = ("details", "our_actions", "partner_actions", "client_benefit", "validity", "responsible", "contact", "trigger", "record_result", "promo_code")


def instruction_draft(terms):
    def field(key):
        return terms.get(key) or "Не указано в договорённости — уточните перед применением."
    return "\n\n".join([
        "1. Когда предлагать\n" + field("trigger"),
        "2. Что объяснить клиенту\n" + field("client_benefit"),
        "3. Что сделать\n" + field("our_actions") + "\nДействия партнёра: " + field("partner_actions") + "\nПромокод: " + (terms.get("promo_code") or "Не указан"),
        "4. Где отметить результат\n" + field("record_result"),
        "5. К кому обратиться\n" + field("responsible") + "\n" + field("contact"),
        "Сроки\n" + field("validity"),
    ])


def change_agreement(previous, command, payload, user_id):
    data = deepcopy(previous or {})
    revision = int(data.get("revision", 0))
    if payload.get("revision") != revision:
        last = (data.get("history") or [{}])[-1]
        if command in {"confirm", "approve_instruction"} and last.get("command") == command and last.get("user_id") == user_id and payload.get("revision") == revision - 1:
            return data
        raise ValueError("Договорённость изменилась. Откройте её заново.")
    now = datetime.now(timezone.utc).isoformat()
    if command == "save":
        if not isinstance(payload.get("terms"), dict):
            raise ValueError("Укажите условия договорённости")
        terms = {key: str((payload.get("terms") or {}).get(key) or "").strip() for key in TERM_FIELDS}
        if not terms["details"]:
            raise ValueError("Запишите условия договорённости")
        if any(len(value) > 20000 for value in terms.values()):
            raise ValueError("Поле слишком длинное")
        if terms == data.get("terms"):
            return data
        data["terms"] = terms
        data["terms_version"] = int(data.get("terms_version", 0)) + 1
        data["status"] = "needs_confirmation"
    elif command == "confirm":
        if not (data.get("terms") or {}).get("details"):
            raise ValueError("Сначала сохраните условия")
        if data.get("status") == "confirmed":
            return data
        data.update(status="confirmed", confirmed_at=now, confirmed_by=user_id)
    elif command == "prepare_instruction":
        if data.get("status") != "confirmed":
            raise ValueError("Сначала подтвердите условия")
        data["instruction_draft"] = instruction_draft(data["terms"])
        data["draft_terms_version"] = data["terms_version"]
    elif command == "save_instruction":
        if data.get("status") != "confirmed" or data.get("draft_terms_version") != data.get("terms_version"):
            raise ValueError("Сначала подготовьте черновик по актуальным условиям")
        text = str(payload.get("text") or "").strip()
        if not text or len(text) > 30000:
            raise ValueError("Введите инструкцию до 30 000 символов")
        data["instruction_draft"] = text
        data["draft_terms_version"] = data.get("terms_version")
    elif command == "approve_instruction":
        if data.get("status") != "confirmed" or not data.get("instruction_draft") or data.get("draft_terms_version") != data.get("terms_version"):
            raise ValueError("Обновите черновик по подтверждённым условиям")
        if data.get("instruction") == data["instruction_draft"] and data.get("instruction_terms_version") == data["terms_version"]:
            return data
        data.update(instruction=data["instruction_draft"], instruction_terms_version=data["terms_version"], instruction_approved_at=now, instruction_approved_by=user_id)
    else:
        raise ValueError("Неизвестное действие")
    snapshot = {key: value for key, value in (previous or {}).items() if key != "history"}
    data["history"] = [*(data.get("history") or []), {"command": command, "user_id": user_id, "at": now, "previous": snapshot}]
    data.update(revision=revision + 1, updated_at=now, updated_by=user_id)
    return data


def read_results(cursor, business_ids):
    if not business_ids:
        return []
    cursor.execute("""SELECT w.id, w.client_business_id, w.agreement_json, w.partnership_launched_at,
        w.partnership_outcome_json, p.company_id, p.name, b.name AS business_name
        FROM lead_workstreams w JOIN prospectingleads p ON p.id=w.lead_id
        JOIN businesses b ON b.id=w.client_business_id
        WHERE w.workstream_type='client_partnership' AND w.client_business_id=ANY(%s)
        ORDER BY w.updated_at DESC, w.id""", (list(business_ids),))
    columns = [column[0] for column in cursor.description]
    return [dict(row) if hasattr(row, "keys") else dict(zip(columns, row)) for row in cursor.fetchall()]


def save_agreement(cursor, workstream_id, business_ids, command, payload, user_id):
    cursor.execute("SELECT agreement_json FROM lead_workstreams WHERE id=%s AND client_business_id=ANY(%s) AND workstream_type='client_partnership' FOR UPDATE", (workstream_id, list(business_ids)))
    row = cursor.fetchone()
    if not row:
        raise PermissionError("Партнёр недоступен")
    old = row.get("agreement_json") if hasattr(row, "get") else row[0]
    data = change_agreement(old, command, payload, user_id)
    cursor.execute("UPDATE lead_workstreams SET agreement_json=%s, updated_at=NOW() WHERE id=%s", (Json(data), workstream_id))
    return data
