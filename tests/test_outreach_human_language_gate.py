from __future__ import annotations

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

from services import outreach_pain_library_service
from services.outreach_campaign_service import _message_for_angle, _quality_gate
from services.outreach_human_language import review_human_language


def test_approved_fgf_partnership_contract_accepts_exact_owner_offer_only():
    exact = (
        "LocalOS подберёт местные бизнесы со смежной аудиторией и подготовит "
        "предложение о партнёрстве. Вы сами решите, кому отправить."
    )

    approved = review_human_language(
        exact,
        approved_copy_contract="fgf_partnership_acquisition_owner_v1",
    )
    altered = review_human_language(
        "LocalOS подготовит предложение о партнёрстве.",
        approved_copy_contract="fgf_partnership_acquisition_owner_v1",
    )

    assert approved["checks"]["concrete_solution"] is True
    assert altered["checks"]["concrete_solution"] is False
from services.outreach_pain_library_service import (
    fetch_monitored_pain_documents,
    retrieve_language_support,
)
from services.outreach_playbook import beauty_outreach_guidance
from tests.conftest import PROJECT_ROOT, _run_flask_db_upgrade


def test_report_style_map_signal_fails_human_language_gate():
    result = review_human_language(
        "Карточка Am Estetik на Яндекс Картах: услуг - 15, с ценой - 10."
    )

    assert result["passed"] is False
    assert "SLOP_CLICHE" in result["reason_codes"]


def test_multi_channel_solution_rejects_maps_only_cta():
    old = review_human_language(
        "LocalOS подготовит черновики для Telegram, VK и Яндекс Карт. "
        "Вам было бы интересно привлекать больше клиентов с карт?"
    )
    corrected = review_human_language(
        "LocalOS подготовит черновики для Telegram, VK и Яндекс Карт. "
        "Вам было бы интересно привлекать больше клиентов онлайн?"
    )

    assert old["passed"] is False
    assert "CTA_SCOPE_MISMATCH" in old["reason_codes"]
    assert corrected["checks"]["cta_scope_aligned"] is True


PRICE_UPDATE_MESSAGE = (
    "Здравствуйте! Я Александр Демьянов из LocalOS.\n\n"
    "Увидел, что вы обновили цены и прайс-лист. Если после такого обновления "
    "новые цены приходится отдельно переносить на сайт, карты и другие площадки, "
    "а затем проверять, что нигде не осталась старая версия.\n\n"
    "LocalOS готовит обновления для каждой площадки - вам остаётся проверить и подтвердить.\n\n"
    "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. "
    "Вам может быть интересно также сэкономить время?"
)


def test_user_approved_price_update_example_passes_human_language_gate():
    result = review_human_language(
        PRICE_UPDATE_MESSAGE,
        pain_hypothesis=(
            "Если после обновления прайса цены приходится вручную переносить "
            "на сайт, карты и другие площадки."
        ),
        pain_is_recipient_fact=False,
        approved_proof_keys=["salon_price_300plus_clicks_v1"],
    )

    assert result["passed"] is True
    assert result["reason_codes"] == []
    assert result["checks"]["signal_pain_solution_cta"] is True
    assert result["checks"]["concrete_solution"] is True


def test_unsupported_publication_claim_fails_human_language_gate():
    result = review_human_language(
        (
            "Увидел ваш анонс клиентского дня.\n\n"
            "LocalOS автоматически публикует материалы в VK и Telegram.\n\n"
            "Показать на вашем анонсе?"
        ),
        publication_capabilities={
            "schema": "localos_outreach_publication_capabilities_v1",
            "approval_required": True,
            "channels": [],
            "supported_after_connection": ["telegram", "vk"],
            "manual_or_supervised_channels": ["yandex_maps", "two_gis"],
        },
    )

    assert result["passed"] is False
    assert "UNSUPPORTED_PUBLICATION_CLAIM" in result["reason_codes"]


def test_yandex_and_two_gis_are_never_allowed_as_autopublish_claims():
    result = review_human_language(
        (
            "Увидел ваш анонс.\n\n"
            "После подтверждения LocalOS автоматически публикует пост в Яндекс Картах и 2ГИС.\n\n"
            "Показать пример?"
        ),
        publication_capabilities={
            "schema": "localos_outreach_publication_capabilities_v1",
            "approval_required": True,
            "channels": [],
            "supported_after_connection": ["telegram", "vk"],
            "manual_or_supervised_channels": ["yandex_maps", "two_gis"],
        },
    )

    assert result["passed"] is False
    assert "UNSUPPORTED_PUBLICATION_CLAIM" in result["reason_codes"]


def test_infinitive_autopublish_claims_are_enforced():
    result = review_human_language(
        (
            "Увидел ваш анонс.\n\n"
            "После вашего подтверждения LocalOS может автоматически "
            "публиковать посты в Яндекс Картах и 2ГИС.\n\n"
            "Показать пример?"
        ),
        publication_capabilities={
            "schema": "localos_outreach_publication_capabilities_v1",
            "approval_required": True,
            "channels": [],
            "supported_after_connection": ["telegram", "vk"],
            "manual_or_supervised_channels": ["yandex_maps", "two_gis"],
        },
    )

    assert result["passed"] is False
    assert "UNSUPPORTED_PUBLICATION_CLAIM" in result["reason_codes"]


def test_price_update_preview_passes_full_gate_with_supported_public_language_refs():
    candidate = {
        "recipient": "Линия красоты",
        "recipient_category": "Салон красоты",
        "recipient_segment": "beauty_team",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "sender_company": "LocalOS",
        "sender_mode": "localos",
        "signal_combo": "recent_price_update_announcement",
        "observed_fact": "11 июля вы сообщили об изменении цен и обновили прайс-лист.",
        "problem_hypothesis": (
            "Если после обновления прайса новые цены приходится отдельно "
            "переносить на сайт, карты и другие площадки."
        ),
        "problem_hypothesis_status": "conditional_operator_approved",
        "localos_action": (
            "LocalOS готовит обновления цен для сайта, карт и других площадок - "
            "вам остаётся проверить и подтвердить."
        ),
        "pain_reference_ids": ["doc-1", "doc-2", "doc-3"],
        "language_support": {
            "status": "conditional_operator_approved",
            "pain_support_status": "unsupported",
            "language_support_status": "supported",
            "document_count": 3,
            "source_count": 3,
            "professional_source_count": 3,
            "vendor_source_count": 0,
            "recent_document_count": 3,
            "language_reference_ids": ["chunk-1", "chunk-2", "chunk-3"],
        },
        "outreach_playbook": beauty_outreach_guidance(),
        "bridge": "Обновление цен можно синхронизировать между площадками",
        "next_step": "Показать пример",
        "evidence_kind": "recent_official_price_update_post",
        "evidence_status": "observed",
        "source_url": "https://t.me/example/1",
        "freshness": "fresh",
        "trust_statement": "Подтверждённый опыт LocalOS",
    }
    candidate["pain_hypothesis"] = candidate["problem_hypothesis"]

    message = _message_for_angle("signal", candidate, {}, [])
    gate = _quality_gate(
        message,
        candidate,
        {"forbidden_claims": []},
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )

    assert message.endswith(
        "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. "
        "Вам может быть интересно также сэкономить время?"
    )
    assert gate["passed"] is True
    assert gate["score"] == 18
    assert gate["human_language_review"]["enforced_reason_codes"] == []
    assert "обычно" not in message.lower()
    assert gate["human_language_review"]["language_support_status"] == "conditional_operator_approved"

    candidate.update({
        "evidence_id": "actual-recipient-evidence",
        "evidence_ids": ["wrong-recipient-evidence"],
        "supporting_evidence": [{
            "evidence_id": "actual-recipient-evidence",
            "source_url": candidate["source_url"],
        }],
    })
    mismatch_gate = _quality_gate(
        message,
        candidate,
        {"forbidden_claims": []},
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="signal",
    )
    assert mismatch_gate["checks"]["source_alignment"] is False
    assert "SOURCE_MISMATCH" in mismatch_gate["reason_codes"]


def test_quality_gate_keeps_detected_language_issues_visible_when_not_blocking_legacy_flow():
    candidate = {
        "recipient": "Yes Apart",
        "recipient_type": "residential_complex",
        "sender_mode": "partner_business",
        "observed_fact": "Для семей гостей есть специальные условия.",
        "bridge": "Для семей гостей есть специальные условия",
        "next_step": "Обсудить",
        "evidence_kind": "operator_approved_partnership_reason",
        "evidence_status": "approved",
        "source_url": "https://example.test/yes-apart",
        "freshness": "fresh",
    }
    text = (
        "Yes Apart: для семей гостей есть специальные условия. "
        "LocalOS предлагает решение. Обсудить?"
    )

    gate = _quality_gate(
        text,
        candidate,
        {"forbidden_claims": []},
        channel="email",
        channel_status="ready",
        suppressed=False,
        angle="matching_authority",
    )
    review = gate["human_language_review"]

    assert review["passed"] is False
    assert review["detected_passed"] is False
    assert review["gate_passed"] is True
    assert "ABSTRACT_SOLUTION" in review["reason_codes"]
    assert review["enforced_reason_codes"] == []


def test_cliches_and_abstract_solution_are_rejected_with_explicit_codes():
    result = review_human_language(
        (
            "Ваш новый прайс - точка роста. LocalOS предлагает комплексное решение, "
            "которое поможет вывести бизнес на новый уровень. Вам может быть интересно?"
        ),
        pain_hypothesis="Обновление цен может отнимать время.",
        pain_is_recipient_fact=False,
    )

    assert result["passed"] is False
    assert "SLOP_CLICHE" in result["reason_codes"]
    assert "ABSTRACT_SOLUTION" in result["reason_codes"]
    assert "GENERIC_CTA" in result["reason_codes"]
    assert "точка роста" in result["matched_phrases"]


@pytest.mark.parametrize(
    "phrase",
    (
        "выйти на новый уровень",
        "изменить правила игры",
        "в современном быстро меняющемся мире",
        "хотел бы предложить",
        "уверен, что",
        "вам точно нужно",
        "закрыть боль",
        "без усилий",
        "единая экосистема для устойчивого развития бизнеса",
        "экспертный подход к развитию бренда",
        "трансформировать клиентский путь",
        "дать мощный импульс развитию",
    ),
)
def test_agreed_corpus_blacklist_is_rejected_deterministically(phrase):
    result = review_human_language(
        (
            "Увидел, что вы обновили прайс. Обычно цены проверяют на картах. "
            f"LocalOS готовит обновления цен для карт; это поможет {phrase}. "
            "Показать пример?"
        ),
        pain_hypothesis="Цены обычно проверяют на картах.",
    )
    assert "SLOP_CLICHE" in result["reason_codes"], phrase


@pytest.mark.parametrize(
    "text",
    (
        (
            "В карточке Padrina_studio нет новостей. "
            "Когда инфоповоды остаются только в расписании и прайсе, "
            "карточка не показывает текущую работу студии. "
            "LocalOS подготовит черновики постов. Показать пример?"
        ),
        (
            "В карточке Padrina_studio опубликованы услуги с ценами. "
            "Администратору сложно держать в голове все подходящие дополнения. "
            "LocalOS соберёт матрицу услуг. "
            "Вам было бы интересно проверить сценарии увеличения среднего чека?"
        ),
    ),
)
def test_padrina_owner_rejected_templates_do_not_pass_neuroslop_filter(text):
    result = review_human_language(text)

    assert result["passed"] is False
    assert "SLOP_CLICHE" in result["reason_codes"]


@pytest.mark.parametrize(
    "text",
    (
        (
            "В карточке Padrina_studio опубликована ссылка на запись через DIKIDI. "
            "Посты для нескольких площадок приходится писать и редактировать несколько раз, а это отнимает время. "
            "После загрузки выгрузки из DIKIDI LocalOS автоматически подготовит черновики постов о выполненных услугах. "
            "Вам было бы интересно сэкономить время на ведении соцсетей?"
        ),
        (
            "В карточке Padrina_studio опубликованы услуги с ценами. "
            "У салонов бывает так: услуг много, а средний чек всё равно маленький. "
            "LocalOS по вашему прайсу соберёт матрицу услуг и допродаж, подготовит подсказки для администратора и покажет результ. "
            "Вам было бы интересно увеличить средний чек?"
        ),
    ),
)
def test_padrina_owner_rewrites_pass_neuroslop_filter(text):
    result = review_human_language(text)

    assert result["passed"] is True
    assert result["reason_codes"] == []


@pytest.mark.parametrize(
    ("text", "pain_hypothesis", "proof_keys"),
    (
        (
            "Здравствуйте! Я Александр Демьянов, основатель LocalOS.\n\n"
            "29 июля вы анонсировали клиентский день 21 августа: семинар, мастер-класс и специальные предложения.\n\n"
            "Перед таким событием обычно нужно несколько раз напомнить о нём в Telegram и VK, а для карт подготовить отдельную новость. Один и тот же анонс приходится вручную подгонять под каждую площадку.\n\n"
            "LocalOS готовит версии из одного исходника, а вы проверяете и решаете, что публиковать.\n\n"
            "Показать на вашем анонсе?",
            "Перед событием анонс обычно приходится адаптировать для нескольких площадок.",
            [],
        ),
        (
            "Здравствуйте! Я Александр Демьянов из LocalOS.\n\n"
            "11 июля вы сообщили об изменении цен и написали, что новый прайс уже доступен.\n\n"
            "После смены цен старые цифры могут остаться на сайте, картах и других площадках. Если проверять позиции вручную, на это уходит время и легко что-то пропустить.\n\n"
            "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. Вам может быть интересно также сэкономить время?",
            "После смены цен старые цифры могут остаться на других площадках.",
            ["salon_price_300plus_clicks_v1"],
        ),
        (
            "Здравствуйте! Я Александр Демьянов, LocalOS.\n\n"
            "4 августа вы опубликовали разбор микронидлинга.\n\n"
            "Готовый разбор часто остаётся только в одном канале. Чтобы использовать его на картах и в VK, текст нужно сократить под формат и ещё раз проверить медицинские формулировки.\n\n"
            "LocalOS готовит такие версии из исходного текста, а публикация остаётся после вашей проверки.\n\n"
            "Подготовить пример на этом разборе?",
            "Готовый разбор часто остаётся в одном канале.",
            [],
        ),
    ),
)
def test_contract_rewritten_beauty_drafts_pass_language_gate(
    text, pain_hypothesis, proof_keys
):
    result = review_human_language(
        text,
        pain_hypothesis=pain_hypothesis,
        approved_proof_keys=proof_keys,
        language_support={"status": "supported"},
    )

    assert result["passed"] is True


def test_registered_salon_proof_cannot_be_paraphrased_with_same_numbers():
    result = review_human_language(
        PRICE_UPDATE_MESSAGE.replace("в пару кликов", "мгновенно"),
        pain_hypothesis="После обновления прайса цены обычно переносят между площадками.",
        approved_proof_keys=["salon_price_300plus_clicks_v1"],
    )

    assert "PROOF_WORDING_CHANGED" in result["reason_codes"]


@pytest.mark.parametrize(
    "altered_proof",
    (
        "Салоны через LocalOS гарантированно обновляют все цены без ошибок. Показать пример?",
        "Салон красоты обновляет через LocalOS прайс на 400 позиций. Интересно?",
        "LocalOS за минуту обновляет 300+ позиций без проверки. Показать?",
    ),
)
def test_registered_salon_proof_requires_exact_text(altered_proof):
    result = review_human_language(
        altered_proof,
        approved_proof_keys=["salon_price_300plus_clicks_v1"],
    )

    assert "PROOF_WORDING_CHANGED" in result["reason_codes"]


def test_generic_maybe_interesting_cta_with_extra_words_requires_registered_proof():
    result = review_human_language(
        (
            "Увидел, что вы обновили прайс. Обычно цены проверяют на картах. "
            "LocalOS готовит обновления цен для карт. "
            "Вам может быть интересно также сэкономить время?"
        ),
        pain_hypothesis="Цены обычно проверяют на картах.",
    )

    assert "GENERIC_CTA" in result["reason_codes"]


def test_segment_pain_stated_as_known_recipient_fact_is_rejected():
    result = review_human_language(
        (
            "Вы тратите много времени на перенос цен между площадками. "
            "LocalOS переносит цены на сайт и карты. Показать пример?"
        ),
        pain_hypothesis="Перенос цен между площадками может отнимать время.",
        pain_is_recipient_fact=False,
    )

    assert result["passed"] is False
    assert "INFERENCE_AS_FACT" in result["reason_codes"]


class RecordingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        self.sql = " ".join(str(sql).split())
        self.params = params

    def fetchall(self):
        return []


def test_pain_library_refresh_uses_same_fail_closed_public_professional_policy():
    cursor = RecordingCursor()

    fetch_monitored_pain_documents(cursor)

    sql = cursor.sql.lower()
    assert "cross join lateral" in sql
    assert "pain_voice_eligibility" in sql
    assert "source.status = 'active'" in sql
    assert "source.source_type = 'telegram'" in sql
    assert "source.visibility = 'public'" in sql
    assert "source.sensitivity_class = 'public'" in sql
    assert "document.sensitivity_class = 'public'" in sql
    assert "source.allowed_uses ? 'outreach'" in sql
    assert "document.allowed_uses ? 'outreach'" in sql
    assert "document.permalink like 'https://t.me/%%'" in sql
    assert "pain_support_eligible" in sql
    assert "voice_style_eligible" in sql
    assert "eligibility_confidence" in sql


def test_language_retrieval_fails_closed_to_curated_public_professional_beauty_corpus():
    cursor = RecordingCursor()

    result = retrieve_language_support(
        cursor,
        query="обновление прайса на картах и сайте",
        segment="beauty",
        theme="pricing_and_average_ticket",
        approved_document_ids=["11111111-1111-1111-1111-111111111111"],
        query_vector=None,
    )

    sql = cursor.sql.lower()
    assert "source.status = 'active'" in sql
    assert "source.visibility = 'public'" in sql
    assert "document.sensitivity_class = 'public'" in sql
    assert "subscription.is_active = true" in sql
    assert "source.sensitivity_class = 'public'" in sql
    assert "source.allowed_uses ? 'outreach'" in sql
    assert "document.allowed_uses ? 'outreach'" in sql
    assert "document.permalink like 'https://t.me/%%'" in sql
    assert "pain_voice_eligibility" in sql
    assert "pain_support_eligible" in sql
    assert "voice_style_eligible" in sql
    assert "websearch_to_tsquery" in sql
    assert "segments" in sql and "themes" in sql
    assert "document.id = any" in sql
    assert sql.count("%s") == len(cursor.params)
    assert result["status"] == "unsupported"
    assert result["raw_quotes_exposed"] is False


def test_language_retrieval_vector_query_keeps_policy_filters_before_reranking():
    cursor = RecordingCursor()

    result = retrieve_language_support(
        cursor,
        query="обновить прайс проверить старые цены",
        segment="beauty",
        theme="price_surface_sync",
        approved_document_ids=[],
        query_vector=[0.1] * 2560,
    )

    assert "chunk.embedding <=> %s::halfvec" in cursor.sql
    assert cursor.sql.count("%s") == len(cursor.params)
    assert result["retrieval_mode"] == "hybrid"


def test_price_theme_stays_unsupported_while_manual_time_can_support_voice(monkeypatch):
    def fake_retrieval(cursor, *, theme, **kwargs):
        if theme == "price_surface_sync":
            return {
                "status": "weak",
                "document_count": 2,
                "source_count": 2,
                "pain_reference_ids": ["price-doc-1", "price-doc-2"],
                "language_reference_ids": ["price-chunk-1", "price-chunk-2"],
                "sources": [],
            }
        assert theme == "manual_time"
        return {
            "status": "supported",
            "document_count": 3,
            "source_count": 3,
            "professional_source_count": 3,
            "pain_reference_ids": ["manual-doc-1", "manual-doc-2", "manual-doc-3"],
            "language_reference_ids": ["manual-chunk-1", "manual-chunk-2", "manual-chunk-3"],
            "sources": [],
        }

    monkeypatch.setattr(
        outreach_pain_library_service,
        "retrieve_language_support",
        fake_retrieval,
    )
    result = outreach_pain_library_service.language_support_for_candidate(
        object(),
        {
            "recipient_segment": "beauty_team",
            "signal_combo": "recent_price_update_announcement",
            "signal_pain_key": "pricing_and_average_ticket",
            "problem_hypothesis": "Если цены нужно перенести на карты.",
            "localos_action": "LocalOS готовит обновления на проверку.",
        },
        {"pain_library": []},
    )

    assert result["status"] == "conditional_operator_approved"
    assert result["pain_support_status"] == "weak"
    assert result["language_support_status"] == "supported"
    assert result["pain_reference_ids"] == []
    assert result["language_reference_ids"] == [
        "manual-chunk-1", "manual-chunk-2", "manual-chunk-3"
    ]
    assert result["frequency_claim_allowed"] is False


def _postgres_dsn(postgres_container):
    raw_url = postgres_container.get_connection_url()
    return raw_url.replace(
        "postgresql+psycopg2://",
        "postgresql://",
        1,
    )


@pytest.fixture(scope="module")
def pain_library_migrated_postgres(postgres_container):
    dsn = _postgres_dsn(postgres_container)
    connection = psycopg2.connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS userexamples (
                    id TEXT PRIMARY KEY,
                    example_type TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        connection.commit()
    finally:
        connection.close()

    _run_flask_db_upgrade(PROJECT_ROOT, dsn)
    return postgres_container


def test_pain_library_refresh_executes_with_real_psycopg2(
    pain_library_migrated_postgres,
):
    connection = psycopg2.connect(
        _postgres_dsn(pain_library_migrated_postgres),
        cursor_factory=RealDictCursor,
    )
    try:
        with connection.cursor() as cursor:
            assert fetch_monitored_pain_documents(cursor, limit=1) == []
    finally:
        connection.close()


def test_language_retrieval_executes_with_real_psycopg2_without_vector(
    pain_library_migrated_postgres,
    monkeypatch,
):
    monkeypatch.setattr(outreach_pain_library_service, "_query_vector", lambda _query: None)
    connection = psycopg2.connect(
        _postgres_dsn(pain_library_migrated_postgres),
        cursor_factory=RealDictCursor,
    )
    try:
        with connection.cursor() as cursor:
            result = retrieve_language_support(
                cursor,
                query="обновление прайса",
                segment="beauty",
                theme="manual_time",
                approved_document_ids=[],
                query_vector=None,
                limit=1,
            )
    finally:
        connection.close()

    assert result["status"] == "unsupported"
    assert result["raw_quotes_exposed"] is False
