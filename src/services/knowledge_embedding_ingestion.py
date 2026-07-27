from __future__ import annotations

import json
from typing import Any

from psycopg2.extras import RealDictCursor

from core.knowledge_policy import redact_text
from services.knowledge_graph_service import upsert_document, upsert_source


USES = ["market", "industry_recommendations", "client_content", "localos_content"]


def _table_exists(conn, table_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = cursor.fetchone()
    cursor.close()
    return bool(row and row[0])


def _source(conn, *, key: str, title: str, visibility: str = "public") -> dict[str, Any]:
    return upsert_source(
        conn,
        source_type="domain_table",
        external_key=key,
        title=title,
        source_role="service",
        visibility=visibility,
        sensitivity_class="public" if visibility == "public" else "shared_deidentified",
        allowed_uses=USES,
        status="active",
        sync_mode="public_preview",
    )


def ingest_public_reviews(conn, *, limit: int = 1000) -> int:
    if not _table_exists(conn, "externalbusinessreviews"):
        return 0
    source = _source(conn, key="externalbusinessreviews-semantic", title="Публичные отзывы")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT r.id, r.business_id, r.source, r.rating, r.text, r.response_text,
               r.published_at, r.updated_at
        FROM externalbusinessreviews r
        WHERE NULLIF(TRIM(COALESCE(r.text, '')), '') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_documents d
              WHERE d.source_id = %s AND d.external_id = r.id AND d.invalidated_at IS NULL
                AND d.updated_at >= COALESCE(r.updated_at, r.created_at)
          )
        ORDER BY COALESCE(r.updated_at, r.created_at) ASC
        LIMIT %s
        """,
        (source["id"], max(1, min(int(limit), 10000))),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    for row in rows:
        review_text, _ = redact_text(row.get("text"))
        response_text, _ = redact_text(row.get("response_text"))
        body = json.dumps(
            {
                "rating": row.get("rating"),
                "review": review_text,
                "business_response": response_text or None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=str(row["id"]),
            document_type="public_review",
            title=f"Отзыв, оценка {row.get('rating') or 'не указана'}",
            content_text=body,
            business_id=str(row.get("business_id") or "") or None,
            published_at=row.get("published_at") or row.get("updated_at"),
            sensitivity_class="public",
            allowed_uses=USES,
            metadata={"review_id": row["id"], "provider": row.get("source"), "author_removed": True},
        )
    return len(rows)


def ingest_public_posts(conn, *, limit: int = 1000) -> int:
    if not _table_exists(conn, "externalbusinessposts"):
        return 0
    source = _source(conn, key="externalbusinessposts-semantic", title="Опубликованные посты бизнеса")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT p.id, p.business_id, p.source, p.title, p.text, p.published_at, p.updated_at
        FROM externalbusinessposts p
        WHERE NULLIF(TRIM(COALESCE(p.text, '')), '') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_documents d
              WHERE d.source_id = %s AND d.external_id = p.id AND d.invalidated_at IS NULL
                AND d.updated_at >= COALESCE(p.updated_at, p.created_at)
          )
        ORDER BY COALESCE(p.updated_at, p.created_at) ASC
        LIMIT %s
        """,
        (source["id"], max(1, min(int(limit), 10000))),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    for row in rows:
        text, _ = redact_text(row.get("text"))
        title, _ = redact_text(row.get("title"))
        upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=str(row["id"]),
            document_type="published_post",
            title=title or "Публикация бизнеса",
            content_text=f"{title}\n\n{text}".strip(),
            business_id=str(row.get("business_id") or "") or None,
            published_at=row.get("published_at") or row.get("updated_at"),
            sensitivity_class="public",
            allowed_uses=USES,
            metadata={"post_id": row["id"], "provider": row.get("source")},
        )
    return len(rows)


def ingest_approved_news(conn, *, limit: int = 1000) -> int:
    if not _table_exists(conn, "usernews"):
        return 0
    source = _source(conn, key="usernews-approved-semantic", title="Подтверждённые новости LocalOS")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT n.id, n.business_id, n.generated_text, n.created_at,
               COALESCE(n.updated_at, n.created_at) AS updated_at
        FROM usernews n
        WHERE COALESCE(n.approved, 0) = 1
          AND n.business_id IS NOT NULL
          AND NULLIF(TRIM(COALESCE(n.generated_text, '')), '') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_documents d
              WHERE d.source_id = %s AND d.external_id = n.id AND d.invalidated_at IS NULL
                AND d.updated_at >= COALESCE(n.updated_at, n.created_at)
          )
        ORDER BY COALESCE(n.updated_at, n.created_at) ASC
        LIMIT %s
        """,
        (source["id"], max(1, min(int(limit), 10000))),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    for row in rows:
        text, _ = redact_text(row.get("generated_text"))
        upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=str(row["id"]),
            document_type="approved_news",
            title="Подтверждённая новость бизнеса",
            content_text=text,
            business_id=str(row.get("business_id") or "") or None,
            published_at=row.get("updated_at") or row.get("created_at"),
            sensitivity_class="public",
            allowed_uses=USES,
            metadata={"news_id": row["id"], "approved": True},
        )
    return len(rows)


def ingest_deidentified_private_aggregates(conn, *, limit: int = 1000) -> int:
    source = _source(
        conn,
        key="private-telegram-aggregates-semantic",
        title="Обезличенные агрегаты закрытых Telegram-источников",
        visibility="internal",
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT a.business_id, c.concept_type, c.canonical_key, c.label,
               COUNT(DISTINCT a.id) AS observations,
               MAX(a.updated_at) AS observed_at
        FROM knowledge_assertions a
        JOIN knowledge_concepts c ON c.id::text = a.object_id
        WHERE a.business_id IS NOT NULL
          AND a.invalidated_at IS NULL
          AND a.sensitivity_class IN ('internal', 'tenant_confidential')
          AND c.concept_type IN ('pain', 'topic', 'format', 'market_signal', 'practice')
        GROUP BY a.business_id, c.concept_type, c.canonical_key, c.label
        HAVING COUNT(DISTINCT a.id) >= 3
        ORDER BY MAX(a.updated_at) ASC
        LIMIT %s
        """,
        (max(1, min(int(limit), 10000)),),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    for row in rows:
        body = (
            f"Обезличенный сигнал: {row['concept_type']} — {row['label']}. "
            f"Количество независимых наблюдений внутри бизнеса: {int(row['observations'])}."
        )
        upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=f"{row['business_id']}:{row['concept_type']}:{row['canonical_key']}",
            document_type="private_chat_aggregate",
            title=f"Агрегированный сигнал: {row['label']}",
            content_text=body,
            business_id=str(row["business_id"]),
            published_at=row.get("observed_at"),
            sensitivity_class="shared_deidentified",
            allowed_uses=["industry_recommendations", "client_content", "localos_content"],
            metadata={"observations": int(row["observations"]), "raw_messages_included": False},
        )
    return len(rows)


def ingest_company_profiles(conn, *, limit: int = 1000) -> int:
    """Build one provenance-rich semantic document per canonical company."""
    if not _table_exists(conn, "companies"):
        return 0
    source = _source(conn, key="company-registry-semantic", title="Канонический реестр компаний")
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT company.id, company.canonical_name, company.legal_name,
               company.primary_category, company.first_seen_source,
               locations.items AS locations, profiles.items AS external_profiles,
               observations.items AS observations, services.items AS public_services,
               social.items AS social_sources, audits.items AS public_audits,
               GREATEST(
                   company.updated_at,
                   locations.updated_at,
                   profiles.updated_at,
                   observations.updated_at,
                   services.updated_at,
                   social.updated_at,
                   audits.updated_at
               ) AS source_updated_at
        FROM companies company
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                       'location_id', location.id,
                       'name', location.display_name,
                       'address', location.address,
                       'city', location.city,
                       'region', location.region,
                       'country', location.country,
                       'is_primary', location.is_primary
                   ) ORDER BY location.is_primary DESC, location.created_at) AS items,
                   MAX(location.updated_at) AS updated_at
            FROM company_locations location
            WHERE location.company_id = company.id AND location.status = 'active'
        ) locations ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                       'provider', profile.provider,
                       'external_id', profile.external_id,
                       'url', profile.canonical_url,
                       'last_collected_at', profile.last_collected_at,
                       'source', profile.provider
                   ) ORDER BY profile.provider, profile.created_at) AS items,
                   MAX(profile.updated_at) AS updated_at
            FROM company_external_profiles profile
            JOIN company_locations location ON location.id = profile.company_location_id
            WHERE location.company_id = company.id AND profile.status = 'active'
        ) profiles ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                       'predicate', observation.predicate,
                       'value', observation.value_json,
                       'source_type', observation.source_type,
                       'source_url', observation.source_url,
                       'confidence', observation.confidence,
                       'observed_at', observation.observed_at
                   ) ORDER BY observation.observed_at DESC) AS items,
                   MAX(observation.updated_at) AS updated_at
            FROM company_observations observation
            WHERE observation.company_id = company.id
              AND observation.status IN ('observed', 'confirmed')
              AND observation.invalidated_at IS NULL
        ) observations ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                       'name', service.name,
                       'description', service.description,
                       'category', service.category,
                       'price', service.price_text,
                       'source_url', service.source_url,
                       'observed_at', service.observed_at
                   ) ORDER BY service.observed_at DESC) AS items,
                   MAX(service.updated_at) AS updated_at
            FROM company_public_services service
            JOIN company_locations location ON location.id = service.company_location_id
            WHERE location.company_id = company.id AND service.invalidated_at IS NULL
        ) services ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                       'relation_type', link.relation_type,
                       'verification_status', link.verification_status,
                       'confidence', link.confidence,
                       'source_title', knowledge.title,
                       'source_url', knowledge.canonical_url,
                       'evidence', link.evidence_json
                   ) ORDER BY link.confidence DESC, link.updated_at DESC) AS items,
                   MAX(link.updated_at) AS updated_at
            FROM company_social_source_links link
            JOIN knowledge_sources knowledge ON knowledge.id = link.source_id
            WHERE link.company_id = company.id
              AND knowledge.visibility = 'public'
              AND knowledge.sensitivity_class = 'public'
        ) social ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(entry.payload ORDER BY entry.updated_at DESC) AS items,
                   MAX(entry.updated_at) AS updated_at
            FROM (
                SELECT jsonb_build_object(
                           'audit_type', 'public_lead_audit',
                           'audit_id', audit.lead_id,
                           'source_url', audit.slug,
                           'content', LEFT(COALESCE(
                               audit.published_json,
                               audit.edited_json,
                               audit.generated_json,
                               audit.page_json
                           )::text, 12000)
                       ) AS payload,
                       audit.updated_at
                FROM adminprospectingleadpublicoffers audit
                WHERE audit.company_id = company.id AND audit.audit_context = 'public'
                UNION ALL
                SELECT jsonb_build_object(
                           'audit_type', 'sales_room_audit',
                           'audit_id', audit.id,
                           'source_url', audit.prepared_audit_url,
                           'title', audit.offer_title,
                           'summary', audit.offer_text
                       ) AS payload,
                       audit.updated_at
                FROM sales_room_audit_offers audit
                WHERE audit.company_id = company.id AND audit.audit_context = 'public'
            ) entry
        ) audits ON TRUE
        WHERE company.status IN ('observed', 'active')
          AND NOT EXISTS (
              SELECT 1 FROM knowledge_documents document
              WHERE document.source_id = %s AND document.external_id = company.id::text
                AND document.invalidated_at IS NULL
                AND document.updated_at >= GREATEST(
                    company.updated_at,
                    locations.updated_at,
                    profiles.updated_at,
                    observations.updated_at,
                    services.updated_at,
                    social.updated_at,
                    audits.updated_at
                )
          )
        ORDER BY GREATEST(
            company.updated_at,
            locations.updated_at,
            profiles.updated_at,
            observations.updated_at,
            services.updated_at,
            social.updated_at,
            audits.updated_at
        ) ASC
        LIMIT %s
        """,
        (source["id"], max(1, min(int(limit), 10000))),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    for row in rows:
        payload = {
            "company_id": str(row["id"]),
            "name": row.get("canonical_name"),
            "legal_name": row.get("legal_name"),
            "primary_category": row.get("primary_category"),
            "locations": row.get("locations") or [],
            "external_profiles": row.get("external_profiles") or [],
            "observations": row.get("observations") or [],
            "public_services": row.get("public_services") or [],
            "social_sources": row.get("social_sources") or [],
            "public_audits": row.get("public_audits") or [],
        }
        body, flags = redact_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
        upsert_document(
            conn,
            source_id=str(source["id"]),
            external_id=str(row["id"]),
            document_type="company_public_profile",
            title=str(row.get("canonical_name") or "Компания"),
            content_text=body,
            published_at=row.get("source_updated_at"),
            sensitivity_class="public",
            pii_flags=[flag for flag in flags if flag != "secret"],
            allowed_uses=USES,
            metadata={
                "company_id": str(row["id"]),
                "first_seen_source": row.get("first_seen_source"),
                "provenance_included": True,
                "source_text_redacted": bool(flags),
            },
        )
    return len(rows)


def ingest_semantic_sources(conn, *, limit_per_source: int = 1000) -> dict[str, int]:
    return {
        "reviews": ingest_public_reviews(conn, limit=limit_per_source),
        "posts": ingest_public_posts(conn, limit=limit_per_source),
        "news": ingest_approved_news(conn, limit=limit_per_source),
        "companies": ingest_company_profiles(conn, limit=limit_per_source),
        "private_aggregates": ingest_deidentified_private_aggregates(conn, limit=limit_per_source),
    }
