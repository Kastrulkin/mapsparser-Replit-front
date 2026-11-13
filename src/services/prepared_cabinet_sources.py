"""Read selected handoff materials from their existing business-owned records."""
import hashlib
import json

from services.creator_identity_service import creator_eligibility_sql


LABELS = {"services": "Услуги", "reviews": "Ответы на отзывы", "content": "Контент-план и посты", "partnerships": "Партнёрства", "influencers": "Блогеры"}
ROUTES = {"services": "/dashboard/card?tab=services", "reviews": "/dashboard/card?tab=reviews", "content": "/dashboard/content", "partnerships": "/dashboard/partnerships", "influencers": "/dashboard/influencers"}


def version(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _item(section, row, title, text):
    return {"title": str(title or "Материал")[:200], "text": str(text or "").strip()[:12000], "source_id": str(row["id"]), "source_type": section}


def candidates(cursor, business_id, selected=None):
    result = {key: [] for key in LABELS}
    cursor.execute("""SELECT id,name,optimized_name,optimized_description FROM userservices
        WHERE business_id=%s AND is_active IS NOT FALSE
          AND (COALESCE(optimized_name,'') <> '' OR COALESCE(optimized_description,'') <> '')
        AND (%s IS NULL OR id=ANY(%s))
        ORDER BY updated_at DESC NULLS LAST,id LIMIT 30""", (business_id, selected.get("services") if selected else None, selected.get("services") if selected else None))
    for row in cursor.fetchall():
        text = "Название: " + (row["optimized_name"] or row["name"] or "")
        if row["optimized_description"]:
            text += "\n\n" + row["optimized_description"]
        result["services"].append(_item("services", row, row["name"], text))
    cursor.execute("""SELECT id,author_name,COALESCE(NULLIF(edited_text,''),generated_text) AS text
        FROM reviewreplydrafts WHERE business_id=%s AND status IN ('draft','generated','pending_review','approved')
          AND COALESCE(NULLIF(edited_text,''),generated_text,'') <> ''
        AND (%s IS NULL OR id=ANY(%s))
        ORDER BY updated_at DESC,id LIMIT 30""", (business_id, selected.get("reviews") if selected else None, selected.get("reviews") if selected else None))
    for row in cursor.fetchall():
        result["reviews"].append(_item("reviews", row, "Ответ · " + (row["author_name"] or "Отзыв"), row["text"]))
    cursor.execute("""SELECT i.id,i.theme,i.goal,i.draft_text,i.scheduled_for,p.title AS plan_title
        FROM contentplanitems i JOIN contentplans p ON p.id=i.plan_id AND p.business_id=i.business_id
        WHERE i.business_id=%s AND i.status IN ('planned','draft_generated','edited','approved')
        AND (%s IS NULL OR i.id=ANY(%s))
        ORDER BY i.scheduled_for NULLS LAST,i.id LIMIT 30""", (business_id, selected.get("content") if selected else None, selected.get("content") if selected else None))
    for row in cursor.fetchall():
        text = ("Дата: " + str(row["scheduled_for"]) + "\n") if row["scheduled_for"] else ""
        text += row["draft_text"] or row["goal"] or row["theme"] or ""
        if text.strip():
            item = _item("content", row, (row["plan_title"] or "Контент-план") + " · " + (row["theme"] or "Публикация"), text)
            item["has_draft"] = bool((row["draft_text"] or "").strip())
            result["content"].append(item)
    cursor.execute("""SELECT w.id,l.name,l.address,l.source_url,l.description,w.partnership_outcome_json
        FROM lead_workstreams w JOIN prospectingleads l ON l.id=w.lead_id
        WHERE w.client_business_id=%s AND w.workstream_type='client_partnership'
          AND w.status NOT IN ('excluded','rejected','archived')
          AND COALESCE(l.disqualification_reason,'')=''
        AND (%s IS NULL OR w.id=ANY(%s))
        ORDER BY w.updated_at DESC,w.id LIMIT 30""", (business_id, selected.get("partnerships") if selected else None, selected.get("partnerships") if selected else None))
    for row in cursor.fetchall():
        parts = [row["address"], row["description"], row["source_url"]]
        result["partnerships"].append(_item("partnerships", row, row["name"], "\n".join(str(value) for value in parts if value) or "Кандидат из подборки компании. Условия сотрудничества требуют уточнения."))
    cursor.execute(f"""SELECT r.id,p.display_name,p.description,c.canonical_url,r.reasons_json
        FROM creator_search_results r JOIN creator_search_jobs j ON j.id=r.search_job_id
        JOIN creator_profiles p ON p.id=r.creator_profile_id
        JOIN LATERAL (SELECT canonical_url FROM creator_channels WHERE creator_profile_id=p.id
            AND verification_status <> 'rejected' ORDER BY created_at,id LIMIT 1) c ON TRUE
        WHERE j.business_id=%s AND r.shortlist_status='shortlisted' AND p.verification_status <> 'rejected' AND {creator_eligibility_sql('p')}
        AND (%s IS NULL OR r.id=ANY(%s))
        ORDER BY r.score DESC NULLS LAST,r.id LIMIT 30""", (business_id, selected.get("influencers") if selected else None, selected.get("influencers") if selected else None))
    for row in cursor.fetchall():
        reasons = row["reasons_json"]
        explanation = "\n".join(str(value) for value in reasons if isinstance(value, str)) if isinstance(reasons, list) else ""
        text = "\n".join(value for value in [row["description"], explanation, row["canonical_url"]] if value)
        result["influencers"].append(_item("influencers", row, row["display_name"], text or "Автор из персональной подборки компании."))
    return result


def preview(cursor, business_id):
    items = candidates(cursor, business_id)
    return {"version": version(items), "sections": [{"key": key, "label": LABELS[key], "href": ROUTES[key], "items": items[key]} for key in LABELS]}


def choose(cursor, business_id, selection, expected_version):
    fresh = preview(cursor, business_id)
    if fresh["version"] != expected_version:
        raise ValueError("Материалы изменились. Обновите предпросмотр и проверьте выбор ещё раз.")
    if not isinstance(selection, dict) or set(selection) != set(LABELS):
        raise ValueError("Выберите материалы во всех пяти разделах.")
    result = {}
    for section in fresh["sections"]:
        key = section["key"]
        ids = selection[key]
        available = {item["source_id"] for item in section["items"]}
        if not isinstance(ids, list) or not ids or len(ids) > 30 or any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids) or not set(ids).issubset(available):
            raise ValueError("Проверьте выбор материалов в разделе «" + LABELS[key] + "».")
        if key == "content" and not any(item["source_id"] in ids and item.get("has_draft") for item in section["items"]):
            raise ValueError("Добавьте хотя бы один готовый черновик поста в контент-план.")
        result[key] = [{"source_type": key, "source_id": item} for item in ids]
    return result


def resolve(cursor, business_id, materials):
    if not any("source_id" in item for items in materials.values() for item in items):
        return materials
    selected = {key: [item.get("source_id") for item in saved if item.get("source_type") == key] for key, saved in materials.items()}
    existing = candidates(cursor, business_id, selected)
    result = {}
    for key, saved in materials.items():
        available = {item["source_id"]: item for item in existing.get(key, [])}
        result[key] = [available[item["source_id"]] for item in saved if item.get("source_type") == key and item.get("source_id") in available]
    return result
