from __future__ import annotations

from typing import Any, Dict, List


COMMUNICATION_SOURCES = ["appointments", "services", "packages", "business_profile"]


COMMUNICATION_AGENT_TEMPLATE_KEYS = [
    "appointment_reminder",
    "post_visit_followup",
    "inactive_client_winback",
    "package_offer_after_service",
    "inbound_request_reply_draft",
]


COMMUNICATION_AGENT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "appointment_reminder": {
        "name": "Агент напоминаний о записи",
        "goal": "Напомнить клиентам о ближайшей записи и мягко предложить релевантный пакет, если он уместен.",
        "trigger": "appointment.reminder.before",
        "audience": "clients_with_upcoming_appointments",
        "audience_rules": [
            "appointment starts within configured reminder window",
            "appointment status is confirmed or pending confirmation",
            "client has reachable communication channel",
        ],
        "consent_rules": [
            "transactional reminder is allowed",
            "marketing/package block is included only when marketing consent is present",
            "skip clients with opt_out or suppressed channel",
        ],
        "message_template": "Здравствуйте, {client_name}! Напоминаем о записи {appointment_at} на {service_name}. Если хотите, администратор может рассказать о пакете {package_name}.",
        "persona": "Вежливый администратор: коротко, спокойно, без давления и неподтвержденных обещаний.",
        "approval_type": "communications_send",
        "send_capability": "communications.send_reminder",
        "mode": "approved_batch_only",
        "frequency_cap": "one_message_per_client_per_appointment",
        "daily_cap": 10,
    },
    "post_visit_followup": {
        "name": "Агент сообщения после визита",
        "goal": "Отправить заботливое сообщение после завершенного визита и зафиксировать реакцию клиента.",
        "trigger": "visit.completed.after",
        "audience": "clients_with_recent_completed_visits",
        "audience_rules": [
            "visit completed within configured follow-up window",
            "client has no unresolved complaint block",
            "one follow-up per completed visit",
        ],
        "consent_rules": [
            "service follow-up is allowed for the selected channel",
            "skip clients with opt_out or suppressed channel",
            "offer text is excluded unless marketing consent is present",
        ],
        "message_template": "Здравствуйте, {client_name}! Спасибо, что были у нас на {service_name}. Всё ли прошло хорошо? Если нужна помощь после визита, ответьте на это сообщение.",
        "persona": "Заботливый администратор: дружелюбно, без навязчивых продаж, с быстрым переходом к помощи.",
        "approval_type": "communications_send",
        "send_capability": "communications.send_reminder",
        "mode": "approved_batch_only",
        "frequency_cap": "one_message_per_client_per_visit",
        "daily_cap": 10,
    },
    "inactive_client_winback": {
        "name": "Агент возврата клиентов",
        "goal": "Подготовить безопасное winback-сообщение клиентам, которые давно не были, и отправлять только подтвержденной пачкой.",
        "trigger": "client.inactive.since",
        "audience": "clients_without_recent_visits",
        "audience_rules": [
            "last visit is older than configured inactivity threshold",
            "client has no upcoming appointment",
            "client is not already in an active winback sequence",
        ],
        "consent_rules": [
            "marketing consent is required",
            "skip clients with opt_out or suppressed channel",
            "respect frequency cap across all promotional communications",
        ],
        "message_template": "Здравствуйте, {client_name}! Давно вас не видели. Если хотите вернуться к {service_name}, мы подготовим удобное время и расскажем о подходящем варианте ухода.",
        "persona": "Тактичный администратор: без давления, с уважением к паузе клиента и прозрачным предложением.",
        "approval_type": "communications_send",
        "send_capability": "communications.send_offer",
        "mode": "approved_batch_only",
        "frequency_cap": "one_winback_message_per_client_per_60_days",
        "daily_cap": 10,
    },
    "package_offer_after_service": {
        "name": "Агент пакетного предложения",
        "goal": "Предложить пакет после релевантной услуги, когда это полезно клиенту и разрешено правилами согласия.",
        "trigger": "service.completed.relevant",
        "audience": "clients_after_relevant_service",
        "audience_rules": [
            "completed service matches package eligibility rules",
            "package is active and relevant for the client",
            "client has no duplicate package offer in the cooldown window",
        ],
        "consent_rules": [
            "marketing consent is required",
            "skip clients with opt_out or suppressed channel",
            "include only packages available for this business and service",
        ],
        "message_template": "Здравствуйте, {client_name}! После {service_name} вам может подойти пакет {package_name}. Можем прислать детали и варианты записи, если интересно.",
        "persona": "Консультирующий администратор: полезно, конкретно, без скидочных обещаний без подтверждения.",
        "approval_type": "communications_send",
        "send_capability": "communications.send_offer",
        "mode": "approved_batch_only",
        "frequency_cap": "one_package_offer_per_client_per_package_per_30_days",
        "daily_cap": 10,
    },
    "inbound_request_reply_draft": {
        "name": "Агент черновика ответа на запрос",
        "goal": "Подготовить черновик ответа на входящий запрос без внешней отправки.",
        "trigger": "inbound.message.received",
        "audience": "clients_or_prospects_with_inbound_request",
        "audience_rules": [
            "inbound message is open and not already answered",
            "request is linked to the current business",
            "conversation channel is available for manual reply",
        ],
        "consent_rules": [
            "reply is allowed inside the active inbound conversation",
            "do not add promotional block without marketing consent",
            "escalate sensitive, legal, medical, billing, or conflict cases to human",
        ],
        "message_template": "Здравствуйте, {client_name}! Спасибо за сообщение. По вашему вопросу: {answer_draft}. Если удобно, администратор уточнит детали и предложит следующий шаг.",
        "persona": "Аккуратный администратор: отвечает по делу, отмечает неизвестные факты и не подтверждает запись без правил.",
        "approval_type": "final_output",
        "send_capability": "communications.draft",
        "mode": "draft_only",
        "frequency_cap": "one_draft_per_inbound_message",
        "daily_cap": 0,
    },
}


def infer_communication_agent_template_key(description: str) -> str:
    text = str(description or "").lower()
    if _has_any(text, ["входящ", "запрос", "ответ на запрос", "входное сообщение", "reply draft"]):
        return "inbound_request_reply_draft"
    if _has_any(text, ["давно не был", "давно не были", "верни", "возврат", "вернуть", "inactive", "winback"]):
        return "inactive_client_winback"
    if _has_any(text, ["после визита", "после посещения", "после услуги", "follow-up", "followup"]):
        return "post_visit_followup"
    if _has_any(text, ["пакетное предложение", "пакет", "package"]) and not _has_any(text, ["напом", "запис"]):
        return "package_offer_after_service"
    return "appointment_reminder"


def get_communication_agent_template(template_key: str) -> Dict[str, Any]:
    key = template_key if template_key in COMMUNICATION_AGENT_TEMPLATES else "appointment_reminder"
    template = COMMUNICATION_AGENT_TEMPLATES[key]
    return {
        **template,
        "key": key,
        "data_sources": list(COMMUNICATION_SOURCES),
        "audience_rules": list(template["audience_rules"]),
        "consent_rules": list(template["consent_rules"]),
        "delivery_outcome_journal": build_delivery_outcome_journal(key),
    }


def list_communication_agent_templates() -> List[Dict[str, Any]]:
    return [get_communication_agent_template(key) for key in COMMUNICATION_AGENT_TEMPLATE_KEYS]


def build_delivery_outcome_journal(template_key: str) -> Dict[str, Any]:
    return {
        "journal_type": "communications_delivery_outcome",
        "agent_template": template_key,
        "fields": [
            "run_id",
            "blueprint_id",
            "recipient_id",
            "channel",
            "draft_id",
            "approval_id",
            "send_request_id",
            "delivery_state",
            "outcome",
            "outcome_reason",
            "created_at",
            "updated_at",
        ],
        "states": ["drafted", "pending_human", "queued_not_dispatched", "sent_manually_or_by_approved_dispatcher", "delivered", "failed", "responded", "suppressed"],
        "outcomes": ["no_response", "reply_received", "booking_created", "package_interest", "opt_out", "complaint", "manual_followup_required"],
        "external_dispatch_performed": False,
    }


def _has_any(text: str, markers: List[str]) -> bool:
    return any(marker in text for marker in markers)
