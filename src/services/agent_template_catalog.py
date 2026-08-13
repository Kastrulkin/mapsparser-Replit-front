from copy import deepcopy
from typing import Any, Dict, List

from services.agent_blueprint_draft_builder import compile_agent_blueprint
from services.agent_template_certification import empty_certification_evidence, evaluate_template_certification
from services.agent_workflow_dsl import build_workflow_dsl_document, validate_workflow_dsl_document


TEMPLATE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "daily_owner_digest",
        "version": "1.0.0",
        "name": "Ежедневная сводка владельцу",
        "business_result": "К началу дня владелец видит один короткий список отклонений и задач, требующих решения.",
        "vertical": "operations",
        "prompt": "Каждый день собирай короткий внутренний отчёт: что требует внимания по отзывам, новостям, услугам, партнёрствам и финансам. Ничего не отправляй клиентам.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "negative_review_reply",
        "version": "1.0.0",
        "name": "Черновики ответов на негативные отзывы",
        "business_result": "Менеджер получает готовые черновики ответов и публикует их только после проверки.",
        "vertical": "reputation",
        "prompt": "Найди негативные отзывы без ответа и подготовь короткие черновики ответов в стиле компании. Публикация только после ручного подтверждения.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "service_seo_cleanup",
        "version": "1.0.0",
        "name": "SEO-проверка услуг",
        "business_result": "Владелец получает приоритетный список слабых названий, дублей и пустых описаний.",
        "vertical": "local_seo",
        "prompt": "Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "card_posts_from_signals",
        "version": "1.0.0",
        "name": "Новости из бизнес-сигналов",
        "business_result": "Контент-менеджер получает три черновика новостей на основе реальных данных бизнеса.",
        "vertical": "content",
        "prompt": "Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач. Только черновики.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "tomorrow_bookings_check",
        "version": "1.0.0",
        "name": "Проверка записей на завтра",
        "business_result": "Администратор заранее видит записи без предоплаты и риски отмены.",
        "vertical": "appointments",
        "prompt": "Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up. Не отправляй сообщения автоматически.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "google_sheets_business_result",
        "version": "1.0.0",
        "name": "Результат из Google Sheets",
        "business_result": "Ответственный получает нормализованную сводку новых строк таблицы и список исключений.",
        "vertical": "operations",
        "prompt": "Каждый вечер читай новые строки Google Sheets, нормализуй их и подготовь внутреннюю сводку с исключениями. Ничего не записывай обратно.",
        "required_connections": ["google_sheets"],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "partnership_outreach_draft",
        "version": "1.0.0",
        "name": "Черновик партнёрского предложения",
        "business_result": "Менеджер получает квалифицированный список партнёров и персональные черновики первого контакта.",
        "vertical": "partnerships",
        "prompt": "Возьми потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение. Отправка только после подтверждения.",
        "required_connections": [],
        "risk_level": "high",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "competitor_website_monitor",
        "version": "1.0.0",
        "name": "Мониторинг сайта конкурента",
        "business_result": "Владелец получает только значимые изменения цен, акций или меню.",
        "vertical": "market_intelligence",
        "prompt": "Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь внутренний короткий отчёт.",
        "required_connections": ["browser_use"],
        "risk_level": "medium",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "faq_miner",
        "version": "1.0.0",
        "name": "FAQ из обращений клиентов",
        "business_result": "Команда получает сгруппированные повторяющиеся вопросы и новые черновики ответов.",
        "vertical": "customer_service",
        "prompt": "Собирай повторяющиеся вопросы клиентов из доступных обращений, группируй их и предлагай новые ответы для FAQ.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "finance_import_assistant",
        "version": "1.0.0",
        "name": "Подготовка импорта расходов",
        "business_result": "Финансист получает проверяемые предложения категорий до применения транзакций.",
        "vertical": "finance",
        "prompt": "Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS. Применение только после ручного подтверждения.",
        "required_connections": ["google_sheets"],
        "risk_level": "high",
        "certification_status": "draft",
        "pilot_required": True,
    },
]


TEMPLATE_LOCALIZED_CONTENT: Dict[str, Dict[str, Dict[str, str]]] = {
    "daily_owner_digest": {
        "en": {"name": "Daily owner digest", "business_result": "The owner starts the day with one short list of exceptions and decisions."},
        "tr": {"name": "İşletme sahibi için günlük özet", "business_result": "İşletme sahibi güne istisnaları ve kararları gösteren tek bir kısa listeyle başlar."},
    },
    "negative_review_reply": {
        "en": {"name": "Negative-review reply drafts", "business_result": "The manager receives ready-to-review replies and publishes only after approval."},
        "tr": {"name": "Olumsuz yorum yanıt taslakları", "business_result": "Yönetici incelemeye hazır yanıtlar alır; yayınlama yalnızca onaydan sonra yapılır."},
    },
    "service_seo_cleanup": {
        "en": {"name": "Service SEO check", "business_result": "The owner gets a prioritized list of weak names, duplicates, and missing descriptions."},
        "tr": {"name": "Hizmet SEO kontrolü", "business_result": "İşletme sahibi zayıf adlar, tekrarlar ve eksik açıklamalar için öncelikli bir liste alır."},
    },
    "card_posts_from_signals": {
        "en": {"name": "Posts from business signals", "business_result": "The content manager receives three drafts grounded in real business data."},
        "tr": {"name": "İşletme sinyallerinden gönderiler", "business_result": "İçerik yöneticisi gerçek işletme verilerine dayalı üç taslak alır."},
    },
    "tomorrow_bookings_check": {
        "en": {"name": "Tomorrow's bookings check", "business_result": "The administrator sees missing prepayments and cancellation risks in advance."},
        "tr": {"name": "Yarının rezervasyonlarını kontrol et", "business_result": "Yönetici eksik ön ödemeleri ve iptal risklerini önceden görür."},
    },
    "google_sheets_business_result": {
        "en": {"name": "Business result from Google Sheets", "business_result": "The owner receives a normalized digest of new rows and exceptions."},
        "tr": {"name": "Google E-Tablolar'dan işletme sonucu", "business_result": "Sorumlu kişi yeni satırların ve istisnaların normalleştirilmiş özetini alır."},
    },
    "partnership_outreach_draft": {
        "en": {"name": "Partnership proposal draft", "business_result": "The manager gets qualified partners and personalized first-contact drafts."},
        "tr": {"name": "İş ortaklığı teklifi taslağı", "business_result": "Yönetici uygun iş ortaklarını ve kişiselleştirilmiş ilk temas taslaklarını alır."},
    },
    "competitor_website_monitor": {
        "en": {"name": "Competitor website monitor", "business_result": "The owner sees only meaningful price, promotion, or menu changes."},
        "tr": {"name": "Rakip web sitesi takibi", "business_result": "İşletme sahibi yalnızca önemli fiyat, kampanya veya menü değişikliklerini görür."},
    },
    "faq_miner": {
        "en": {"name": "FAQ from customer conversations", "business_result": "The team receives grouped recurring questions and new answer drafts."},
        "tr": {"name": "Müşteri görüşmelerinden SSS", "business_result": "Ekip tekrarlanan soruların gruplarını ve yeni yanıt taslaklarını alır."},
    },
    "finance_import_assistant": {
        "en": {"name": "Expense import preparation", "business_result": "Finance receives reviewable category suggestions before transactions are applied."},
        "tr": {"name": "Gider içe aktarma hazırlığı", "business_result": "Finans ekibi işlemler uygulanmadan önce incelenebilir kategori önerileri alır."},
    },
}


def build_agent_template_catalog() -> List[Dict[str, Any]]:
    return [_build_template_manifest(definition) for definition in TEMPLATE_DEFINITIONS]


def get_agent_template(template_key: str) -> Dict[str, Any]:
    for item in build_agent_template_catalog():
        if item["key"] == template_key:
            return item
    return {}


def build_agent_from_template(template_key: str) -> Dict[str, Any]:
    for definition in TEMPLATE_DEFINITIONS:
        if definition["key"] != template_key:
            continue
        draft = compile_agent_blueprint(str(definition["prompt"]), use_ai=False)
        return {
            "definition": deepcopy(definition),
            "draft": draft,
        }
    return {}


def _build_template_manifest(definition: Dict[str, Any]) -> Dict[str, Any]:
    draft = compile_agent_blueprint(str(definition["prompt"]), use_ai=False)
    version_payload = deepcopy(draft["version_payload"])
    metadata = deepcopy(draft["metadata"])
    workflow_dsl = build_workflow_dsl_document(version_payload, metadata)
    validation = validate_workflow_dsl_document(workflow_dsl)
    compiled_candidate = metadata.get("compiled_artifact_candidate")
    compiled_valid = bool(compiled_candidate and compiled_candidate.get("validation", {}).get("valid"))
    schema_gate = bool(validation.get("valid")) and compiled_valid
    security_gate = (
        version_payload.get("side_effects_performed") is not True
        and version_payload.get("limits", {}).get("autonomous_external_write_allowed") is not True
        and version_payload.get("limits", {}).get("autonomous_localos_write_allowed") is not True
    )
    fixture_keys = [
        "valid_input",
        "empty_input",
        "malformed_input",
        "missing_connection",
        "expired_oauth",
        "transient_provider_failure",
        "duplicate_idempotency_key",
        "worker_restart",
        "limit_exceeded",
    ]
    gates = {
        "security": {"passed": security_gate, "evidence": "No autonomous external write is allowed"},
        "schema": {"passed": schema_gate, "evidence": "DSL, topology and compiled artifact validation"},
        "execution": {"passed": False, "evidence": "Runtime fixture evidence is required"},
        "accuracy": {"passed": False, "evidence": "Golden dataset and pilot scoring are required"},
    }
    manifest = {
        "key": definition["key"],
        "version": definition["version"],
        "name": definition["name"],
        "business_result": definition["business_result"],
        "localized_content": TEMPLATE_LOCALIZED_CONTENT.get(str(definition["key"]), {}),
        "vertical": definition["vertical"],
        "trigger": version_payload.get("trigger") or "manual.run",
        "inputs_schema": version_payload.get("inputs_schema") or {},
        "workflow_dsl": workflow_dsl,
        "required_connections": definition.get("required_connections") or [],
        "approval_policy": version_payload.get("approval_policy") or {},
        "limits": version_payload.get("limits") or {},
        "output_schema": version_payload.get("output_schema") or {},
        "risk_level": definition["risk_level"],
        "certification_status": definition["certification_status"],
        "certification_gates": gates,
        "certification_evidence": {
            "template_version": definition["version"],
            "validation_timestamp": None,
            "security_result": gates["security"],
            "schema_result": gates["schema"],
            "execution_result": gates["execution"],
            "accuracy_result": gates["accuracy"],
            "fixtures_passed": 0,
            "golden_score": None,
            "model_and_prompt_versions": [],
            "approval_policy_hash": None,
            "certification_decision": "pilot_evidence_required",
        },
        "fixtures": [{"key": key, "status": "pending"} for key in fixture_keys],
        "golden_results": [],
        "creation_prompt": definition["prompt"],
        "category": draft["category"],
    }
    manifest["certification_evaluation"] = evaluate_template_certification(
        manifest,
        empty_certification_evidence(),
    )
    return manifest
