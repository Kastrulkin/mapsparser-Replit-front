"""Dependency-free capability aliases shared by handlers and risk admission."""

from typing import Any


LEGACY_CAPABILITY_ALIASES = {
    "reviews.reply": "reviews.reply.draft",
    "appointments.create": "appointments.create_request",
    "appointments.update": "appointments.create_request",
    "appointments.cancel": "appointments.create_request",
    "reminders.send": "communications.send_reminder",
    "communications.send": "communications.send_reminder",
    "google_sheets.append_row": "sheets.append_row_request",
    "sheets.append_row": "sheets.append_row_request",
    "google_sheets.read": "google_sheets.read_rows",
    "finance.create_transaction": "finance.transaction.create",
    "finance.manual_entry": "finance.transaction.create",
    "finance.transaction.create_request": "finance.transaction.create",
    "partners.audit_card": "partnership.audit_card",
    "partners.match_services": "partnership.match_services",
    "partners.draft_first_offer": "partnership.draft_offer",
    "partners.draft_commercial_offer": "partnership.draft_offer",
    "billing.reserve/settle": "billing.reserve",
}


def normalize_capability_name(value: Any) -> str:
    name = str(value or "").strip()
    return LEGACY_CAPABILITY_ALIASES.get(name, name)
