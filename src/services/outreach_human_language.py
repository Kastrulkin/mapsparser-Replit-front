"""Deterministic human-language checks for supervised outreach drafts."""

from __future__ import annotations

import re
from typing import Any


SLOP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("точка роста", re.compile(r"\bточк\w*\s+рост\w*\b", re.IGNORECASE)),
    ("вывести на новый уровень", re.compile(r"\bвывест\w*\s+.{0,24}\bнов\w*\s+уров\w*\b", re.IGNORECASE)),
    ("масштабировать бизнес", re.compile(r"\bмасштаб\w*\s+бизнес\w*\b", re.IGNORECASE)),
    ("повысить эффективность", re.compile(r"\bповыс\w*\s+эффективност\w*\b", re.IGNORECASE)),
    ("комплексное решение", re.compile(r"\bкомплексн\w*\s+решени\w*\b", re.IGNORECASE)),
    ("раскрыть потенциал", re.compile(r"\bраскры\w*\s+потенциал\w*\b", re.IGNORECASE)),
    ("усилить присутствие", re.compile(r"\bусил\w*\s+присутстви\w*\b", re.IGNORECASE)),
    ("уникальная возможность", re.compile(r"\bуникальн\w*\s+возможност\w*\b", re.IGNORECASE)),
    ("оптимизировать процессы", re.compile(r"\bоптимиз\w*\s+процесс\w*\b", re.IGNORECASE)),
    ("освободить ресурс", re.compile(r"\bосвобод\w*\s+ресурс\w*\b", re.IGNORECASE)),
    ("улучшить видимость", re.compile(r"\bулучш\w*\s+видимост\w*\b", re.IGNORECASE)),
    ("инновационный", re.compile(r"\bинновационн\w*\b", re.IGNORECASE)),
    ("революционный", re.compile(r"\bреволюционн\w*\b", re.IGNORECASE)),
    ("бесшовный", re.compile(r"\bбесшовн\w*\b", re.IGNORECASE)),
    ("синергия", re.compile(r"\bсинерги\w*\b", re.IGNORECASE)),
    ("лидирующий", re.compile(r"\bлидирующ\w*\b", re.IGNORECASE)),
    ("прокачать", re.compile(r"\bпрокача\w*\b", re.IGNORECASE)),
    ("мощный инструмент", re.compile(r"\bмощн\w*\s+инструмент\w*\b", re.IGNORECASE)),
    ("кратный рост", re.compile(r"\bкратн\w*\s+рост\w*\b", re.IGNORECASE)),
    ("продажи на автопилоте", re.compile(r"\bпродаж\w*\s+на\s+автопилот\w*\b", re.IGNORECASE)),
    ("автоматизировать всё", re.compile(r"\bавтоматиз\w*\s+вс[её]\b", re.IGNORECASE)),
    ("выйти на новый уровень", re.compile(r"\bвы(?:йт|ход)\w*\s+на\s+нов\w*\s+уров\w*\b", re.IGNORECASE)),
    ("изменить правила игры", re.compile(r"\bизмен\w*\s+правил\w*\s+игр\w*\b", re.IGNORECASE)),
    (
        "в современном быстро меняющемся мире",
        re.compile(r"\bв\s+современн\w*\s+быстро\s+меняющ\w*\s+мир\w*\b", re.IGNORECASE),
    ),
    ("хотел бы предложить", re.compile(r"\bхотел\w*\s+бы\s+предлож\w*\b", re.IGNORECASE)),
    ("уверен, что", re.compile(r"\bуверен\w*\s*,?\s+что\b", re.IGNORECASE)),
    ("вам точно нужно", re.compile(r"\bвам\s+точно\s+(?:нужн\w*|необходим\w*)\b", re.IGNORECASE)),
    ("закрыть боль", re.compile(r"\bзакры\w*\s+бол\w*\b", re.IGNORECASE)),
    ("без усилий", re.compile(r"\bбез\s+усил\w*\b", re.IGNORECASE)),
    (
        "единая экосистема для устойчивого развития бизнеса",
        re.compile(r"\bедин\w*\s+экосистем\w*\s+для\s+устойчив\w*\s+развит\w*\s+бизнес\w*\b", re.IGNORECASE),
    ),
    (
        "экспертный подход к развитию бренда",
        re.compile(r"\bэкспертн\w*\s+подход\w*\s+к\s+развит\w*\s+бренд\w*\b", re.IGNORECASE),
    ),
    ("трансформировать клиентский путь", re.compile(r"\bтрансформ\w*\s+клиентск\w*\s+пут\w*\b", re.IGNORECASE)),
    ("дать мощный импульс развитию", re.compile(r"\bда\w*\s+мощн\w*\s+импульс\w*\s+развит\w*\b", re.IGNORECASE)),
    (
        "инфоповоды остаются в расписании и прайсе",
        re.compile(
            r"\bинфоповод\w*\s+оста\w*\s+(?:только\s+)?в\s+расписани\w*\s+и\s+прайс\w*\b",
            re.IGNORECASE,
        ),
    ),
    (
        "держать в голове все подходящие дополнения",
        re.compile(
            r"\bдержа\w*\s+в\s+голов\w*\s+все\s+подходящ\w*\s+дополнени\w*\b",
            re.IGNORECASE,
        ),
    ),
    (
        "проверить сценарии увеличения среднего чека",
        re.compile(
            r"\bпровер\w*\s+сценари\w*\s+увеличени\w*\s+средн\w*\s+чек\w*\b",
            re.IGNORECASE,
        ),
    ),
)

UNCERTAINTY_MARKERS = (
    "обычно",
    "часто",
    "как правило",
    "может",
    "могут",
    "возможно",
    "если",
    "при таком",
    "бывает",
    "актуально ли",
    "знакома проблема",
)

CONCRETE_VERB_RE = re.compile(
    r"\b(?:готов\w*|подготов\w*|обнов\w*|перенос\w*|провер\w*|свер\w*|собир\w*|собер\w*|собра\w*|"
    r"отслеж\w*|публи\w*|настра\w*|анализ\w*|группир\w*|пиш\w*|"
    r"подтвержд\w*|копир\w*|добав\w*|сокращ\w*|сократ\w*|разлож\w*|сохран\w*)\b",
    re.IGNORECASE,
)
CONCRETE_OBJECT_RE = re.compile(
    r"\b(?:прайс(?:-лист)?\w*|цен\w*|карт\w*|сайт\w*|площадк\w*|карточк\w*|"
    r"услуг\w*|отзыв\w*|ответ\w*|пост\w*|публикац\w*|контент\w*|текст\w*|"
    r"новост\w*|описани\w*|фото\w*|данн\w*|верси\w*|исходн\w*|"
    r"изменени\w*|список\w*|правк\w*|инструкц\w*|расхождени\w*|черновик\w*|материал\w*)\b",
    re.IGNORECASE,
)
DIRECT_PAIN_RE = re.compile(
    r"\b(?:вы\s+(?:тратите|теряете|вынуждены|не\s+успеваете|тонете)|"
    r"у\s+вас\s+(?:нет|мало|низк\w*|плохо\w*)|"
    r"вам\s+(?:приходится|нужно|сложно|трудно))\b",
    re.IGNORECASE,
)
SIGNAL_RE = re.compile(
    r"\b(?:вижу|увидел\w*|заметил\w*|сообщил\w*|обновил\w*|анонсир\w*|"
    r"опубликов\w*|в\s+карточк\w*|карточк\w*[^.!?]{0,100}яндекс\w*\s+карт\w*|"
    r"на\s+сайт\w*|в\s+telegram|в\s+официальн\w*\s+канал\w*)\b",
    re.IGNORECASE,
)

SALON_PRICE_300PLUS_PROOF = (
    "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. "
    "Вам может быть интересно также сэкономить время?"
)

APPROVED_GENERIC_CTA_EXCEPTIONS = {
    "salon_price_300plus_clicks_v1": SALON_PRICE_300PLUS_PROOF.lower(),
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sentences(text: str) -> list[str]:
    return [
        _clean(item)
        for item in re.split(r"(?<=[.!?])\s+|\n+", text)
        if _clean(item)
    ]


def _approved_generic_cta(text: str, proof_keys: list[str]) -> bool:
    normalized = _clean(text).lower()
    return any(
        key in APPROVED_GENERIC_CTA_EXCEPTIONS
        and APPROVED_GENERIC_CTA_EXCEPTIONS[key] in normalized
        for key in proof_keys
    )


def _publication_claim_supported(
    normalized: str,
    publication_capabilities: dict[str, Any] | None,
) -> bool:
    claim_present = bool(re.search(
        r"(?:автоматически\s+(?:о?публиков\w*|публику\w*)|"
        r"\bавтопублик|localos\s+готовит\s+и\s+публику)",
        normalized,
        flags=re.IGNORECASE,
    ))
    if not claim_present:
        return True
    if re.search(r"яндекс(?:\s+карт\w*)?|2гис", normalized, flags=re.IGNORECASE):
        return False
    approval_present = bool(re.search(
        r"после[^.!?]{0,80}подтвержден",
        normalized,
        flags=re.IGNORECASE,
    ))
    if not approval_present:
        return False
    capabilities = publication_capabilities if isinstance(publication_capabilities, dict) else {}
    ready_platforms = {
        _clean(item.get("platform")).lower()
        for item in capabilities.get("channels") or []
        if isinstance(item, dict)
        and item.get("connected") is True
        and item.get("provider_ready") is True
        and _clean(item.get("publish_mode")).lower() == "api"
        and _clean(item.get("status")).lower() == "ready"
    }
    named_platforms = set()
    if re.search(r"\btelegram\b", normalized, flags=re.IGNORECASE):
        named_platforms.add("telegram")
    if re.search(r"(?:^|[^a-zа-яё0-9])vk(?:[^a-zа-яё0-9]|$)", normalized, flags=re.IGNORECASE):
        named_platforms.add("vk")
    if re.search(r"google\s+business(?:\s+profile)?", normalized, flags=re.IGNORECASE):
        named_platforms.add("google_business")
    if named_platforms:
        if not named_platforms.issubset(ready_platforms):
            return False
        if "google_business" in named_platforms and "beta-режим" not in normalized:
            return False
        return True
    conditional_connection = bool(re.search(
        r"после\s+подключения\s+канал",
        normalized,
        flags=re.IGNORECASE,
    ))
    return conditional_connection and "поддерживаем" in normalized


def review_human_language(
    text: str,
    *,
    pain_hypothesis: str | None = None,
    pain_is_recipient_fact: bool = False,
    approved_proof_keys: list[str] | None = None,
    language_support: dict[str, Any] | None = None,
    require_signal_flow: bool = False,
    publication_capabilities: dict[str, Any] | None = None,
    approved_copy_contract: str | None = None,
) -> dict[str, Any]:
    """Return explainable checks; corpus similarity is never the sole verdict."""

    normalized = _clean(text).lower()
    proof_keys = [str(item) for item in approved_proof_keys or [] if str(item)]
    matched_phrases = [label for label, pattern in SLOP_PATTERNS if pattern.search(normalized)]
    sentences = _sentences(text)
    localos_sentences = [item for item in sentences if "localos" in item.lower()]
    concrete_solution = bool(
        localos_sentences
        and any(
            CONCRETE_VERB_RE.search(item) and CONCRETE_OBJECT_RE.search(item)
            for item in localos_sentences
        )
    )
    if not localos_sentences:
        concrete_solution = bool(
            CONCRETE_VERB_RE.search(normalized) and CONCRETE_OBJECT_RE.search(normalized)
        )
    if (
        _clean(approved_copy_contract) == "fgf_partnership_acquisition_owner_v1"
        and "localos подберёт местные бизнесы со смежной аудиторией" in normalized
        and "подготовит предложение о партнёрстве" in normalized
    ):
        # This founder-approved wording is a concrete partnership offer even
        # though the generic object lexicon does not include "партнёрство".
        concrete_solution = True

    pain_as_fact = False
    if pain_hypothesis and not pain_is_recipient_fact:
        for sentence in sentences:
            lowered = sentence.lower()
            if not DIRECT_PAIN_RE.search(lowered):
                continue
            if not any(marker in lowered for marker in UNCERTAINTY_MARKERS):
                pain_as_fact = True
                break

    approved_generic_cta = _approved_generic_cta(text, proof_keys)
    protected_proof_selected = "salon_price_300plus_clicks_v1" in proof_keys
    proof_wording_changed = protected_proof_selected and not approved_generic_cta
    generic_cta = bool(
        re.search(
            r"\bвам\s+может\s+быть\s+интересно\b[^?!.]{0,100}\?",
            normalized,
        )
        and not approved_generic_cta
    )
    uncertainty_present = bool(any(marker in normalized for marker in UNCERTAINTY_MARKERS))
    signal_position = SIGNAL_RE.search(normalized)
    pain_positions = [normalized.find(marker) for marker in UNCERTAINTY_MARKERS]
    pain_positions = [position for position in pain_positions if position >= 0]
    solution_position = normalized.find(
        "localos",
        signal_position.end() if signal_position else 0,
    )
    cta_position = normalized.rfind("?")
    signal_pain_solution_cta_detected = bool(
        signal_position
        and solution_position > signal_position.start()
        and cta_position > solution_position
        and (not pain_hypothesis or (pain_positions and min(pain_positions) < solution_position))
    )
    signal_pain_solution_cta = signal_pain_solution_cta_detected or not require_signal_flow
    support = language_support if isinstance(language_support, dict) else {}
    support_status = _clean(support.get("status") or "not_checked")
    conditional_operator_support = bool(
        support_status == "conditional_operator_approved"
        and approved_generic_cta
        and "если" in normalized
    )
    publication_claim_supported = _publication_claim_supported(
        normalized,
        publication_capabilities,
    )

    checks = {
        "cliche_free": not matched_phrases,
        "concrete_solution": concrete_solution,
        "pain_uncertainty": not pain_as_fact,
        "generic_cta_free": not generic_cta,
        "signal_pain_solution_cta": signal_pain_solution_cta,
        "language_support": support_status in {"supported", "not_checked", "unavailable"}
        or conditional_operator_support,
        "publication_claim_supported": publication_claim_supported,
    }
    reason_codes: list[str] = []
    if matched_phrases:
        reason_codes.append("SLOP_CLICHE")
    if not concrete_solution:
        reason_codes.append("ABSTRACT_SOLUTION")
    if pain_as_fact:
        reason_codes.append("INFERENCE_AS_FACT")
    if generic_cta:
        reason_codes.append("GENERIC_CTA")
    if not signal_pain_solution_cta:
        reason_codes.append("WEAK_OFFER_BRIDGE")
    if (
        pain_hypothesis
        and support
        and support_status not in {"supported", "recipient_explicit"}
        and not conditional_operator_support
    ):
        reason_codes.append("PAIN_SUPPORT_INSUFFICIENT")
    if proof_wording_changed:
        reason_codes.append("PROOF_WORDING_CHANGED")
    if not publication_claim_supported:
        reason_codes.append("UNSUPPORTED_PUBLICATION_CLAIM")

    return {
        "passed": not reason_codes,
        "verdict": "approve" if not reason_codes else "revise",
        "checks": checks,
        "reason_codes": reason_codes,
        "matched_phrases": matched_phrases,
        "proof_wording_changed": proof_wording_changed,
        "signal_flow_required": require_signal_flow,
        "signal_flow_detected": signal_pain_solution_cta_detected,
        "language_support_status": support_status,
        "similarity_is_sole_approval_criterion": False,
    }
