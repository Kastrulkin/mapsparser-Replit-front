"""Explicit copy routing. Private identifiers never enter the drafting prompt."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from services.llm import LLMTaskRequest, run_llm_task
from services.llm.policy import CREDENTIAL_PATTERN, EMAIL_PATTERN

# Additional languages require an evaluated model-specific rollout, not geography.
VERIFIED_REVIEW_LANGUAGES = frozenset({"ru"})
LANGUAGE_CANDIDATES = frozenset({"kk", "uz", "hy"})
PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)")
URL = re.compile(r"https?://[^\s\"<>]+")


class CopyRoutingError(ValueError):
    retryable = False

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def enabled(business_id: str = "") -> bool:
    cohort = {value.strip() for value in os.getenv("OUTREACH_DEEPSEEK_BUSINESS_IDS", "").split(",") if value.strip()}
    return business_id in cohort and os.getenv("OUTREACH_DEEPSEEK_DRAFTING_ENABLED", "false").lower() in {"1", "true", "yes"}


def preparation_ready(business_id: str) -> bool:
    gateway_cohort = {value.strip() for value in os.getenv("LLM_DEEPSEEK_BUSINESS_IDS", "").split(",") if value.strip()}
    return (enabled(business_id) and business_id in gateway_cohort
            and os.getenv("LLM_ROUTER_ENABLED", "false").lower() in {"1", "true", "yes"}
            and bool(str(os.getenv("DEEPSEEK_API_KEY") or "").strip()))


def review_language(language: str) -> bool:
    return language.lower().replace("_", "-").split("-")[0] in VERIFIED_REVIEW_LANGUAGES


@dataclass
class PublicCopyContext:
    record: dict[str, Any]
    substitutions: dict[str, str]

    def restore(self, value: str) -> str:
        for token, original in self.substitutions.items():
            value = value.replace(token, original)
        if re.search(r"__LOCALOS_PRIVATE_\d+__", value):
            raise CopyRoutingError("unrecognized_private_placeholder")
        return value


def public_context(record: dict[str, Any]) -> PublicCopyContext:
    """Only public evidence + approved copy enter this route; never CRM conversations.

    The caller constructs this record from the existing evidence/offer contract.
    Identity values, URLs and contact identifiers are replaced with opaque tokens,
    including occurrences in the approved example copy. The original PII registry
    task remains unchanged and cannot be routed to DeepSeek.
    """
    raw = json.dumps(record, ensure_ascii=False)
    if CREDENTIAL_PATTERN.search(raw):
        raise CopyRoutingError("credentials_in_copy_context")
    for evidence in record.get("evidence") or []:
        source = str(evidence.get("source_type") or "").lower()
        if any(marker in source for marker in ("private", "confidential", "conversation", "inbound", "crm_note")):
            raise CopyRoutingError("non_public_copy_evidence")
    replacements: dict[str, str] = {}
    identity = record.get("identity") or {}
    sender = record.get("sender") or {}
    private_values = [str(identity.get(key) or "") for key in ("contact_name", "company_name")]
    private_values += [str(sender.get(key) or "") for key in ("name", "business")]
    private_values += EMAIL_PATTERN.findall(raw) + PHONE.findall(raw) + URL.findall(raw)
    for original in sorted(set(private_values), key=len, reverse=True):
        if not original:
            continue
        token = f"__LOCALOS_PRIVATE_{len(replacements)}__"
        encoded = json.dumps(original, ensure_ascii=False)[1:-1]
        if encoded in raw:
            raw = raw.replace(encoded, token)
            replacements[token] = original
    sanitized = json.loads(raw)
    # Unrestricted transcript/example corpora are not needed for drafting.
    sanitized.get("sender", {}).pop("voice_examples", None)
    return PublicCopyContext(record=sanitized, substitutions=replacements)


def run_copy(prompt: str, *, business_id: str, user_id: str, language: str,
             review: bool = False, runner=None) -> str:
    use_gigachat = review and review_language(language)
    key = "outreach_language_review" if use_gigachat else "outreach_public_copy"
    result = (runner or run_llm_task)(LLMTaskRequest(
        task_key=key, prompt=prompt, business_id=business_id, user_id=user_id,
        data_class="business_internal", pipeline_stage="review" if review else "copy"))
    expected = "gigachat" if use_gigachat else "deepseek"
    if result.status != "completed" or result.provider != expected or not result.content:
        raise CopyRoutingError("outreach_model_route_unavailable")
    return result.content
