from __future__ import annotations

import re
from dataclasses import dataclass

from services.llm.contracts import DATA_CLASSES


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\w)")
NAMED_PERSON_PATTERN = re.compile(
    r"(?P<label>\b(?:фио|имя|клиент|пациент|заказчик|full[_\- ]?name|customer[_\- ]?name|"
    r"client[_\- ]?name|customer|client)[\"']?\s*[:=]\s*[\"']?)(?P<value>[^\"\n,;}]{2,80})",
    re.IGNORECASE,
)
CREDENTIAL_PATTERN = re.compile(
    r"\b(?:api[_\- ]?key|access[_\- ]?token|refresh[_\- ]?token|client[_\- ]?secret|password|"
    r"пароль|токен|секрет)[\"']?\s*[:=]\s*[\"']?\S+",
    re.IGNORECASE,
)
FINANCIAL_LINE_PATTERN = re.compile(
    r"(?:банковск|номер\s+карты|счёт|расчетный\s+счет|транзакц|card\s+number|bank\s+account)",
    re.IGNORECASE,
)
APPOINTMENT_LINE_PATTERN = re.compile(
    r"(?:запись\s+клиента|диалог\s+с\s+клиентом|appointment\s+record|customer\s+conversation)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DataPolicyDecision:
    allowed: bool
    prompt: str
    reason_code: str = ""
    redacted: bool = False


def most_restrictive_data_class(configured: str, requested: str = "") -> str:
    order = {
        "public": 0,
        "business_internal": 1,
        "financial_aggregated": 2,
        "pii": 3,
        "financial_sensitive": 4,
        "credentials": 5,
    }
    configured_clean = str(configured or "").strip()
    requested_clean = str(requested or "").strip()
    if configured_clean not in order:
        return configured_clean
    if not requested_clean:
        return configured_clean
    if requested_clean not in order:
        return requested_clean
    if order[requested_clean] > order[configured_clean]:
        return requested_clean
    return configured_clean


def prepare_prompt_for_provider(prompt: str, *, provider: str, data_class: str) -> DataPolicyDecision:
    clean_class = str(data_class or "").strip()
    if clean_class not in DATA_CLASSES:
        return DataPolicyDecision(False, "", "LLM_DATA_CLASS_UNKNOWN")
    text = str(prompt or "")
    if CREDENTIAL_PATTERN.search(text) or clean_class == "credentials":
        return DataPolicyDecision(False, "", "LLM_CREDENTIALS_BLOCKED")
    if provider != "deepseek":
        return DataPolicyDecision(True, text)
    if clean_class in {"pii", "financial_sensitive"}:
        return DataPolicyDecision(False, "", "DEEPSEEK_DATA_CLASS_BLOCKED")
    redacted = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
    redacted = PHONE_PATTERN.sub("[PHONE_REDACTED]", redacted)
    redacted = NAMED_PERSON_PATTERN.sub(
        lambda match: f"{match.group('label')}[NAME_REDACTED]",
        redacted,
    )
    safe_lines: list[str] = []
    removed_line = False
    for line in redacted.splitlines():
        if FINANCIAL_LINE_PATTERN.search(line) or APPOINTMENT_LINE_PATTERN.search(line):
            removed_line = True
            continue
        safe_lines.append(line)
    safe_prompt = "\n".join(safe_lines).strip()
    if not safe_prompt:
        return DataPolicyDecision(False, "", "DEEPSEEK_PROMPT_EMPTY_AFTER_REDACTION", True)
    changed = safe_prompt != text or removed_line
    return DataPolicyDecision(True, safe_prompt, redacted=changed)
