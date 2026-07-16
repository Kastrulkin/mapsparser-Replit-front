import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from psycopg2.extras import Json, RealDictCursor

from services.knowledge_graph_service import (
    add_evidence,
    canonical_key,
    content_hash,
    upsert_assertion,
    upsert_concept,
    upsert_document,
    upsert_source,
)


TELEGRAM_ANALYSIS_VERSION = "telegram-facets-v1"
SERVICE_ANALYSIS_VERSION = "services-v1"
AUDIT_ANALYSIS_VERSION = "audits-v1"

MESSAGE_RE = re.compile(
    r"^\[(?P<when>\d{4}-\d{2}-\d{2} [^|]+)\| (?P<title>.*?) \| id=(?P<message_id>\d+)\]\n"
    r"(?P<text>.*?)(?=\n---\n\n\[|\Z)",
    flags=re.MULTILINE | re.DOTALL,
)

FACET_RULES: dict[str, dict[str, str]] = {
    "pain": {
        "ручная рутина": r"хаос|рутин|вручную|не успева|все на себе|всё на себе",
        "нестабильная запись": r"нет клиентов|мало запис|пуст[ыое] окн|нестабильн.*запис|спрос",
        "команда и управление": r"текуч|увол|мастер.*уш|администратор|команд.*не|персонал",
        "деньги и прибыль": r"убыт|кассов|денег нет|прибыл.*пада|маржин|долг",
        "контент не работает": r"не знаю.*пост|контент.*не|охват.*пада|не смотрят",
    },
    "topic": {
        "карты и репутация": r"яндекс|2гис|google|карты|отзывы|рейтинг|гео|локальн.*выдач",
        "запись и возврат клиентов": r"запис[ьи]|возврат клиент|повторн|лояльн|crm",
        "команда": r"команд|персонал|мастер|администратор|найм|мотивац|делегир",
        "контент и продвижение": r"контент|рилс|reels|сторис|пост[ыа]?|smm|охват|подписчик",
        "автоматизация": r"автоматизац|нейросет|\bии\b|\bai\b|бот|агент|gpt",
        "финансы и стратегия": r"деньг|касс|маржин|финанс|цена|прайс|расход|стратег",
    },
    "format": {
        "инструкция": r"как |шаг|чек.?лист|инструкц|алгоритм|правил",
        "кейс": r"кейс|истори|до/после|результат|пример|как мы",
        "ошибка": r"ошибк|проблем|не работает|почему.*не|теря[ею]т",
        "мнение": r"я считаю|думаю|мне кажется|мой опыт",
        "вопрос аудитории": r"как вы|а вы|расскажите|поделитесь|что думаете",
    },
    "sales_angle": {
        "разбор текущей ситуации": r"разбор|аудит|диагност|проверим|найд[её]м.*ошиб",
        "экономия времени": r"эконом.*врем|быстрее|рутин|автоматизац",
        "предсказуемая запись": r"стабильн.*запис|предсказуем|заполн.*окн",
        "рост среднего чека": r"средн.*чек|допродаж|комплекс|пакет",
    },
    "cta": {
        "ответить на вопрос": r"напишите|ответьте|поделитесь|что думаете|как у вас",
        "получить материал": r"получить|скачать|забрать|чек.?лист|гайд",
        "записаться": r"записаться|регистрац|места|оставить заявку|заявк",
    },
    "objection": {
        "нет времени": r"нет времени|не успева",
        "дорого": r"дорого|нет бюджета|стоимость.*высок",
        "не верит в продвижение": r"не работает.*реклам|не верю|бесполезн.*маркет",
    },
    "practice": {
        "регулярно измерять": r"метрик|аналитик|измер|отслеж|цифр",
        "работать с базой клиентов": r"клиентск.*баз|возврат|повторн.*визит|crm",
        "обучать команду": r"обуч|тренинг|стандарт|скрипт|регламент",
    },
    "offer": {
        "консультация": r"консультац|созвон|разбор",
        "курс или программа": r"курс|программ|обучен|поток",
        "сервис или инструмент": r"сервис|приложен|платформ|бот|crm",
    },
    "market_signal": {
        "изменение спроса": r"спрос.*измен|клиент.*стал|рынок.*меня|сезон",
        "рост издержек": r"расход.*раст|аренд.*раст|себестоим|подорож",
        "новое правило": r"закон|требован|маркировк|штраф|санпин|лицензи",
        "смена инструмента": r"перешли|заменили|отказались|миграц|новая crm",
    },
}

SOURCE_ROLE_HINTS = {
    "yclients": "vendor",
    "1с": "vendor",
    "wahelp": "vendor",
    "kpi": "vendor",
    "салон": "salon",
    "студия": "salon",
    "мастер": "expert",
    "бизнес": "expert",
    "директор": "expert",
    "маркетинг": "expert",
}

BELESHKO_CHANNEL_KEY = "Белешко_про_стабильные_деньги_в_салоне_красоты"
BELESHKO_MESSAGE_ID = "2950"
BELESHKO_PRIMARY_TOPIC = "долгосрочные основы салонного бизнеса"


def _source_role(folder_name: str) -> str:
    lowered = folder_name.lower()
    for hint, role in SOURCE_ROLE_HINTS.items():
        if hint in lowered:
            return role
    return "unknown"


def _public_channel_url(value: str | None) -> str | None:
    url = str(value or "").strip()
    if not url.startswith("https://t.me/") or "+" in url or "joinchat" in url:
        return None
    return url.rstrip("/")


def parse_telegram_file(path: Path, channel_key: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    messages: list[dict[str, Any]] = []
    for match in MESSAGE_RE.finditer(text):
        body = match.group("text").strip()
        if not body:
            continue
        try:
            published_at = datetime.fromisoformat(match.group("when").strip())
        except ValueError:
            continue
        messages.append(
            {
                "channel_key": channel_key,
                "title": match.group("title").strip(),
                "external_id": match.group("message_id"),
                "published_at": published_at,
                "content_text": body,
            }
        )
    return messages


def iter_telegram_archive(root: Path) -> Iterable[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    for folder in sorted(item for item in root.iterdir() if item.is_dir()):
        for path in sorted(folder.glob("*.txt")):
            for message in parse_telegram_file(path, folder.name):
                key = (folder.name, message["external_id"], content_hash(message["content_text"]))
                if key in seen:
                    continue
                seen.add(key)
                yield message


def telegram_archive_dry_run(root: Path, source_urls: dict[str, str] | None = None) -> dict[str, Any]:
    urls = source_urls or {}
    counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter(
        {item.name: 0 for item in root.iterdir() if item.is_dir()}
    )
    for message in iter_telegram_archive(root):
        counts["messages"] += 1
        source_counts[message["channel_key"]] += 1
    sources = []
    for channel_key, message_count in sorted(source_counts.items()):
        public_url = _public_channel_url(urls.get(channel_key))
        sources.append(
            {
                "external_key": channel_key,
                "title": channel_key.replace("_", " "),
                "message_count": message_count,
                "source_role": _source_role(channel_key),
                "visibility": "public" if public_url else "internal",
                "canonical_url": public_url,
                "status": "candidate",
            }
        )
    return {"sources_count": len(sources), "messages_count": counts["messages"], "sources": sources}


def analyze_facets(text: str, *, channel_key: str, message_id: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    facets: list[dict[str, Any]] = []
    for concept_type, rules in FACET_RULES.items():
        for label, pattern in rules.items():
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                facets.append(
                    {
                        "concept_type": concept_type,
                        "label": label,
                        "confidence": 0.72,
                        "method": "retrieval_rule",
                    }
                )
    if channel_key == BELESHKO_CHANNEL_KEY and message_id == BELESHKO_MESSAGE_ID:
        facets = [item for item in facets if item["concept_type"] != "topic"]
        facets.append(
            {
                "concept_type": "topic",
                "label": BELESHKO_PRIMARY_TOPIC,
                "confidence": 0.98,
                "method": "regression_override",
            }
        )
    return facets


def _excerpt(text: str, limit: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def import_telegram_archive(
    conn,
    *,
    root: Path,
    source_urls: dict[str, str] | None = None,
    analyze: bool = False,
    selected_documents: set[tuple[str, str]] | None = None,
    max_documents: int | None = None,
) -> dict[str, Any]:
    urls = source_urls or {}
    selected = selected_documents or set()
    source_cache: dict[str, dict[str, Any]] = {}
    imported = 0
    updated = 0
    analyzed = 0
    failed: list[dict[str, str]] = []
    run_id = str(uuid.uuid4())
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO knowledge_analysis_runs (
            id, run_type, analysis_version, status, token_budget, metadata_json, started_at
        ) VALUES (%s, 'telegram_import', %s, 'running', %s, %s, NOW())
        """,
        (
            run_id,
            TELEGRAM_ANALYSIS_VERSION,
            None,
            Json({"archive_root": str(root), "semantic_analysis": False}),
        ),
    )
    cursor.close()
    for folder in sorted(item for item in root.iterdir() if item.is_dir()):
        public_url = _public_channel_url(urls.get(folder.name))
        source_cache[folder.name] = upsert_source(
            conn,
            source_type="telegram",
            external_key=folder.name,
            title=folder.name.replace("_", " "),
            canonical_url=public_url,
            source_role=_source_role(folder.name),
            visibility="public" if public_url else "internal",
            sensitivity_class="public" if public_url else "internal",
            allowed_uses=(
                ["market", "outreach", "localos_content", "client_content", "industry_recommendations"]
                if public_url
                else ["localos_content"]
            ),
            status="candidate",
            metadata={"archive_folder": folder.name},
        )
    try:
        for message in iter_telegram_archive(root):
            if max_documents is not None and imported + updated >= max_documents:
                break
            channel_key = message["channel_key"]
            try:
                source = source_cache.get(channel_key)
                if not source:
                    public_url = _public_channel_url(urls.get(channel_key))
                    source = upsert_source(
                        conn,
                        source_type="telegram",
                        external_key=channel_key,
                        title=message["title"] or channel_key.replace("_", " "),
                        canonical_url=public_url,
                        source_role=_source_role(channel_key),
                        visibility="public" if public_url else "internal",
                        sensitivity_class="public" if public_url else "internal",
                        allowed_uses=(
                            ["market", "outreach", "localos_content", "client_content", "industry_recommendations"]
                            if public_url
                            else ["localos_content"]
                        ),
                        status="candidate",
                        metadata={"archive_folder": channel_key},
                    )
                    source_cache[channel_key] = source
                base_url = _public_channel_url(urls.get(channel_key))
                document, inserted = upsert_document(
                    conn,
                    source_id=str(source["id"]),
                    external_id=message["external_id"],
                    document_type="telegram_message",
                    title=message["title"],
                    content_text=message["content_text"],
                    permalink=f"{base_url}/{message['external_id']}" if base_url else None,
                    published_at=message["published_at"],
                    sensitivity_class="public" if base_url else "internal",
                    allowed_uses=(
                        ["market", "outreach", "localos_content", "client_content", "industry_recommendations"]
                        if base_url
                        else ["localos_content"]
                    ),
                    metadata={"channel_key": channel_key},
                )
                imported += 1 if inserted else 0
                updated += 0 if inserted else 1
                should_analyze = analyze and (not selected or (channel_key, message["external_id"]) in selected)
                if should_analyze:
                    facets = analyze_facets(
                        message["content_text"],
                        channel_key=channel_key,
                        message_id=message["external_id"],
                    )
                    _store_document_facets(
                        conn,
                        document=document,
                        source=source,
                        facets=facets,
                        content_text=message["content_text"],
                        observed_at=message["published_at"],
                        analysis_run_id=run_id,
                        analysis_version=TELEGRAM_ANALYSIS_VERSION,
                        industry="beauty",
                    )
                    analyzed += 1
            except Exception as error:
                failed.append({"source": channel_key, "external_id": message["external_id"], "error": str(error)[:300]})
        status = "completed" if not failed else "partial"
    except Exception as error:
        status = "failed"
        failed.append({"source": "archive", "external_id": "", "error": str(error)[:300]})

    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE knowledge_analysis_runs
        SET status = %s, document_count = %s, processed_count = %s,
            failed_count = %s, error_json = %s, completed_at = NOW()
        WHERE id = %s
        """,
        (status, imported + updated, analyzed if analyze else imported + updated, len(failed), Json({"items": failed[:50]}), run_id),
    )
    cursor.close()
    return {
        "run_id": run_id,
        "status": status,
        "sources": len(source_cache),
        "imported": imported,
        "updated": updated,
        "analyzed": analyzed,
        "failed": len(failed),
        "errors": failed[:50],
    }


def _store_document_facets(
    conn,
    *,
    document: dict[str, Any],
    source: dict[str, Any],
    facets: list[dict[str, Any]],
    content_text: str,
    observed_at: datetime | None,
    analysis_run_id: str,
    analysis_version: str,
    industry: str,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO knowledge_document_analyses (
            id, document_id, analysis_run_id, content_hash, analysis_version,
            analyzer_kind, status, facets_json, confidence
        ) VALUES (%s, %s, %s, %s, %s, 'retrieval', 'completed', %s, %s)
        ON CONFLICT (document_id, content_hash, analysis_version, analyzer_kind) DO NOTHING
        """,
        (
            str(uuid.uuid4()),
            str(document["id"]),
            analysis_run_id,
            str(document["content_hash"]),
            analysis_version,
            Json(facets),
            max([float(item["confidence"]) for item in facets], default=0),
        ),
    )
    cursor.close()
    allowed_uses = list(document.get("allowed_uses") or [])
    sensitivity_class = str(document.get("sensitivity_class") or "public")
    for facet in facets:
        concept = upsert_concept(
            conn,
            concept_type=facet["concept_type"],
            label=facet["label"],
            industry=industry,
            sensitivity_class=sensitivity_class,
            allowed_uses=allowed_uses,
            metadata={"method": facet["method"]},
        )
        assertion = upsert_assertion(
            conn,
            assertion_type="DOCUMENT_EXPRESSES",
            subject_type="document",
            subject_id=str(document["id"]),
            predicate="EXPRESSES",
            object_type="concept",
            object_id=str(concept["id"]),
            confidence=float(facet["confidence"]),
            industry=industry,
            allowed_uses=allowed_uses,
            sensitivity_class=sensitivity_class,
            analysis_version=analysis_version,
            metadata={"facet_type": facet["concept_type"], "method": facet["method"]},
        )
        add_evidence(
            conn,
            assertion_id=str(assertion["id"]),
            document_id=str(document["id"]),
            source_id=str(source["id"]),
            excerpt=_excerpt(content_text),
            observed_at=observed_at,
            confidence=float(facet["confidence"]),
            analysis_version=analysis_version,
            allowed_uses=allowed_uses,
            sensitivity_class=sensitivity_class,
            pii_flags=list(document.get("pii_flags") or []),
        )


def import_services(conn, *, limit: int | None = None) -> dict[str, Any]:
    source = upsert_source(
        conn,
        source_type="domain_table",
        external_key="userservices",
        title="Услуги компаний",
        source_role="service",
        visibility="internal",
        sensitivity_class="internal",
        allowed_uses=["market", "industry_recommendations"],
        status="active",
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    params: list[Any] = []
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(max(1, limit))
    cursor.execute(
        f"""
        SELECT DISTINCT ON (u.business_id, LOWER(REGEXP_REPLACE(TRIM(u.name), '\\s+', ' ', 'g')))
               u.id, u.business_id, u.name, u.description, u.category, u.price,
               COALESCE(u.source, 'manual') AS source, u.external_id, u.updated_at, u.created_at
        FROM userservices u
        JOIN businesses b ON b.id = u.business_id
        WHERE COALESCE(u.is_active, TRUE) AND NULLIF(TRIM(u.name), '') IS NOT NULL
        ORDER BY u.business_id, LOWER(REGEXP_REPLACE(TRIM(u.name), '\\s+', ' ', 'g')),
                 u.updated_at DESC NULLS LAST, u.created_at DESC
        {limit_sql}
        """,
        params,
    )
    rows = [_row for _row in cursor.fetchall()]
    cursor.close()
    imported = 0
    public_count = 0
    internal_count = 0
    for row in rows:
        payload = dict(row)
        service_source = str(payload.get("source") or "manual").lower()
        is_public = service_source in {"yandex", "google", "2gis", "maps", "yandex_maps"}
        allowed_uses = ["market", "industry_recommendations"] if is_public else ["industry_recommendations"]
        sensitivity = "public" if is_public else "tenant_confidential"
        body = json.dumps(
            {
                "name": payload.get("name"),
                "category": payload.get("category"),
                "price": payload.get("price"),
                "description": payload.get("description"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        document, inserted = upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=f"{payload.get('business_id')}:{payload.get('external_id') or payload.get('id')}",
            document_type="service_observation",
            title=str(payload.get("name") or "Услуга"),
            content_text=body,
            business_id=str(payload.get("business_id") or "") or None,
            published_at=payload.get("updated_at") or payload.get("created_at"),
            sensitivity_class=sensitivity,
            allowed_uses=allowed_uses,
            metadata={
                "service_id": payload.get("id"),
                "source": service_source,
                "normalized_name": canonical_key(payload.get("name")),
                "category": payload.get("category"),
                "price": payload.get("price"),
                "one_vote_per_business": True,
            },
        )
        concept = upsert_concept(
            conn,
            concept_type="service",
            label=str(payload.get("name") or "Услуга"),
            industry="beauty",
            business_id=None if is_public else str(payload.get("business_id") or "") or None,
            sensitivity_class=sensitivity,
            allowed_uses=allowed_uses,
            metadata={"category": payload.get("category")},
        )
        assertion = upsert_assertion(
            conn,
            assertion_type="BUSINESS_OFFERS_SERVICE",
            subject_type="business",
            subject_id=str(payload.get("business_id") or ""),
            predicate="OFFERS",
            object_type="concept",
            object_id=str(concept["id"]),
            confidence=0.96,
            business_id=None if is_public else str(payload.get("business_id") or "") or None,
            industry="beauty",
            allowed_uses=allowed_uses,
            sensitivity_class=sensitivity,
            analysis_version=SERVICE_ANALYSIS_VERSION,
            metadata={"service_document_id": str(document["id"]), "one_vote_per_business": True},
        )
        add_evidence(
            conn,
            assertion_id=str(assertion["id"]),
            document_id=str(document["id"]),
            source_id=str(source["id"]),
            excerpt=_excerpt(f"{payload.get('name')}. {payload.get('category') or ''}. {payload.get('price') or ''}"),
            observed_at=payload.get("updated_at") or payload.get("created_at"),
            confidence=0.96,
            analysis_version=SERVICE_ANALYSIS_VERSION,
            allowed_uses=allowed_uses,
            sensitivity_class=sensitivity,
        )
        imported += 1 if inserted else 0
        public_count += 1 if is_public else 0
        internal_count += 0 if is_public else 1
    return {
        "status": "completed",
        "observations": len(rows),
        "imported": imported,
        "public": public_count,
        "tenant_confidential": internal_count,
    }


def import_card_audits(conn, *, limit: int | None = None) -> dict[str, Any]:
    fact_source = upsert_source(
        conn,
        source_type="domain_table",
        external_key="cards",
        title="Публичные данные карточек",
        source_role="service",
        visibility="public",
        sensitivity_class="public",
        allowed_uses=["market", "industry_recommendations"],
        status="active",
    )
    recommendation_source = upsert_source(
        conn,
        source_type="domain_table",
        external_key="localos-card-recommendations",
        title="Рекомендации LocalOS по карточкам",
        source_role="service",
        visibility="internal",
        sensitivity_class="tenant_confidential",
        allowed_uses=["industry_recommendations"],
        status="active",
    )
    public_audit_source = upsert_source(
        conn,
        source_type="domain_table",
        external_key="adminprospectingleadpublicoffers",
        title="Публичные аудиты карточек",
        source_role="service",
        visibility="public",
        sensitivity_class="public",
        allowed_uses=["market", "industry_recommendations"],
        status="active",
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    params: list[Any] = []
    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(max(1, limit))
    cursor.execute(
        f"""
        SELECT c.id, c.business_id, c.url, c.title, c.address, c.rating, c.reviews_count,
               c.categories, c.seo_score, c.recommendations, c.ai_analysis,
               c.version, c.is_latest, c.created_at, c.updated_at
        FROM cards c
        JOIN businesses b ON b.id = c.business_id
        ORDER BY c.updated_at DESC NULLS LAST, c.created_at DESC
        {limit_sql}
        """,
        params,
    )
    rows = [dict(row) for row in cursor.fetchall()]
    imported_facts = 0
    imported_recommendations = 0
    card_recommendations = 0
    for row in rows:
        facts = {
            "title": row.get("title"),
            "address": row.get("address"),
            "rating": row.get("rating"),
            "reviews_count": row.get("reviews_count"),
            "categories": row.get("categories"),
            "seo_score": row.get("seo_score"),
        }
        _, fact_inserted = upsert_document(
            conn,
            source_id=str(fact_source["id"]),
            external_id=f"card:{row.get('id')}:facts",
            document_type="card_public_facts",
            title=str(row.get("title") or "Карточка на картах"),
            content_text=json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str),
            business_id=str(row.get("business_id") or "") or None,
            permalink=row.get("url"),
            published_at=row.get("updated_at") or row.get("created_at"),
            sensitivity_class="public",
            allowed_uses=["market", "industry_recommendations"],
            metadata={"card_id": row.get("id"), "version": row.get("version"), "fact_source": True},
        )
        recommendations = row.get("recommendations")
        if recommendations in (None, "", {}, []):
            imported_facts += 1 if fact_inserted else 0
            continue
        card_recommendations += 1
        recommendation_text = json.dumps(recommendations, ensure_ascii=False, sort_keys=True, default=str)
        recommendation_document, recommendation_inserted = upsert_document(
            conn,
            source_id=str(recommendation_source["id"]),
            external_id=f"card:{row.get('id')}:recommendations",
            document_type="localos_recommendation",
            title=f"Рекомендации для {row.get('title') or 'карточки'}",
            content_text=recommendation_text,
            business_id=str(row.get("business_id") or "") or None,
            published_at=row.get("updated_at") or row.get("created_at"),
            sensitivity_class="tenant_confidential",
            allowed_uses=["industry_recommendations"],
            metadata={
                "card_id": row.get("id"),
                "version": row.get("version"),
                "assertion_type": "LOCALOS_RECOMMENDS",
                "not_prevalence_evidence": True,
            },
        )
        recommendation_concept = upsert_concept(
            conn,
            concept_type="intervention",
            label="Оптимизировать карточку по аудиту LocalOS",
            industry="beauty",
            business_id=str(row.get("business_id") or "") or None,
            sensitivity_class="tenant_confidential",
            allowed_uses=["industry_recommendations"],
        )
        assertion = upsert_assertion(
            conn,
            assertion_type="LOCALOS_RECOMMENDS",
            subject_type="business",
            subject_id=str(row.get("business_id") or ""),
            predicate="LOCALOS_RECOMMENDS",
            object_type="concept",
            object_id=str(recommendation_concept["id"]),
            confidence=0.7,
            business_id=str(row.get("business_id") or "") or None,
            industry="beauty",
            allowed_uses=["industry_recommendations"],
            sensitivity_class="tenant_confidential",
            analysis_version=AUDIT_ANALYSIS_VERSION,
            metadata={"not_prevalence_evidence": True},
        )
        add_evidence(
            conn,
            assertion_id=str(assertion["id"]),
            document_id=str(recommendation_document["id"]),
            source_id=str(recommendation_source["id"]),
            excerpt=_excerpt(recommendation_text),
            observed_at=row.get("updated_at") or row.get("created_at"),
            confidence=0.7,
            analysis_version=AUDIT_ANALYSIS_VERSION,
            allowed_uses=["industry_recommendations"],
            sensitivity_class="tenant_confidential",
        )
        imported_facts += 1 if fact_inserted else 0
        imported_recommendations += 1 if recommendation_inserted else 0

    cursor.execute("SELECT to_regclass('public.adminprospectingleadpublicoffers')")
    public_audit_rows: list[dict[str, Any]] = []
    if cursor.fetchone()[0]:
        cursor.execute(
            f"""
            SELECT lead_id, slug, page_json, published_json, is_active, created_at, updated_at
            FROM adminprospectingleadpublicoffers
            WHERE page_json IS NOT NULL
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            {limit_sql}
            """,
            params,
        )
        public_audit_rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()

    for row in public_audit_rows:
        page = dict(row.get("published_json") or row.get("page_json") or {})
        audit = dict(page.get("audit") or {})
        facts = {
            "name": page.get("name"),
            "category": page.get("category"),
            "city": page.get("city"),
            "address": page.get("address"),
            "rating": page.get("rating"),
            "reviews_count": page.get("reviews_count"),
            "has_website": page.get("has_website"),
            "has_recent_activity": page.get("has_recent_activity"),
            "photos_state": page.get("photos_state"),
            "services_count": page.get("services_count"),
        }
        _, fact_inserted = upsert_document(
            conn,
            source_id=str(public_audit_source["id"]),
            external_id=f"public-audit:{row.get('slug')}:facts",
            document_type="lead_audit_public_facts",
            title=str(page.get("name") or "Публичный аудит карточки"),
            content_text=json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str),
            permalink=f"/{row.get('slug')}",
            published_at=row.get("updated_at") or row.get("created_at"),
            sensitivity_class="public",
            allowed_uses=["market", "industry_recommendations"],
            metadata={"lead_id": row.get("lead_id"), "slug": row.get("slug"), "fact_source": True},
        )
        recommendation_text = json.dumps(audit, ensure_ascii=False, sort_keys=True, default=str)
        recommendation_document, recommendation_inserted = upsert_document(
            conn,
            source_id=str(public_audit_source["id"]),
            external_id=f"public-audit:{row.get('slug')}:recommendations",
            document_type="localos_public_audit",
            title=f"Аудит LocalOS для {page.get('name') or 'карточки'}",
            content_text=recommendation_text,
            permalink=f"/{row.get('slug')}",
            published_at=row.get("updated_at") or row.get("created_at"),
            sensitivity_class="public",
            allowed_uses=["industry_recommendations"],
            metadata={
                "lead_id": row.get("lead_id"),
                "slug": row.get("slug"),
                "assertion_type": "LOCALOS_RECOMMENDS",
                "not_prevalence_evidence": True,
            },
        )
        recommendation_concept = upsert_concept(
            conn,
            concept_type="intervention",
            label="Оптимизировать карточку по публичному аудиту LocalOS",
            industry="beauty",
            sensitivity_class="public",
            allowed_uses=["industry_recommendations"],
        )
        assertion = upsert_assertion(
            conn,
            assertion_type="LOCALOS_RECOMMENDS",
            subject_type="lead",
            subject_id=str(row.get("lead_id") or row.get("slug") or ""),
            predicate="LOCALOS_RECOMMENDS",
            object_type="concept",
            object_id=str(recommendation_concept["id"]),
            confidence=0.7,
            industry="beauty",
            allowed_uses=["industry_recommendations"],
            sensitivity_class="public",
            analysis_version=AUDIT_ANALYSIS_VERSION,
            metadata={"not_prevalence_evidence": True, "public_audit_slug": row.get("slug")},
        )
        add_evidence(
            conn,
            assertion_id=str(assertion["id"]),
            document_id=str(recommendation_document["id"]),
            source_id=str(public_audit_source["id"]),
            excerpt=_excerpt(recommendation_text),
            observed_at=row.get("updated_at") or row.get("created_at"),
            confidence=0.7,
            analysis_version=AUDIT_ANALYSIS_VERSION,
            allowed_uses=["industry_recommendations"],
            sensitivity_class="public",
        )
        imported_facts += 1 if fact_inserted else 0
        imported_recommendations += 1 if recommendation_inserted else 0
    return {
        "status": "completed",
        "audits": len(public_audit_rows),
        "card_snapshots": len(rows),
        "card_recommendations": card_recommendations,
        "fact_documents": imported_facts,
        "recommendation_documents": imported_recommendations,
        "circularity_guard": "recommendations_not_used_for_prevalence",
    }
