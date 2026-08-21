import json
import os

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

from core.audit_editorial import audit_quality_gate
from services.outreach_human_language import SLOP_PATTERNS


SOURCE = "/app/debug_data/localos-template-review-v8-20260811.json"
payload = json.load(open(SOURCE, encoding="utf-8"))
lead_ids = [
    item["lead_id"]
    for item in payload["results"]
    if item["classification"] == "content_ready"
]
connection = psycopg2.connect(
    os.environ["DATABASE_URL"], cursor_factory=RealDictCursor
)
connection.set_session(readonly=True, autocommit=False)
cursor = connection.cursor()
cursor.execute("SET TRANSACTION READ ONLY")
cursor.execute(
    """
    SELECT
        lead.id,
        lead.name,
        lead.rating,
        lead.reviews_count,
        lead.source_url,
        offer.slug,
        offer.page_json #>> '{audit,current_state,rating}' AS audit_rating,
        offer.page_json #>> '{audit,current_state,reviews_count}' AS audit_reviews,
        offer.page_json #>> '{audit,current_state,services_count}' AS audit_services,
        offer.page_json #>> '{audit,current_state,services_with_price_count}' AS audit_services_with_price,
        offer.page_json,
        offer.edit_status,
        (offer.edited_json IS NOT NULL) AS has_edited_json,
        offer.updated_at
    FROM prospectingleads lead
    LEFT JOIN adminprospectingleadpublicoffers offer ON offer.lead_id = lead.id
    WHERE lead.id = ANY(%s)
    ORDER BY lead.name
    """,
    (lead_ids,),
)
rows = [dict(row) for row in cursor.fetchall()]
connection.rollback()
connection.close()


def number(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


mismatches = [
    row
    for row in rows
    if number(row["rating"]) != number(row["audit_rating"])
    or number(row["reviews_count"]) != number(row["audit_reviews"])
]
copy_failures = []
for row in rows:
    page = row.get("page_json") if isinstance(row.get("page_json"), dict) else {}
    audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
    current = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
    gate = audit_quality_gate(audit)
    audit_text = json.dumps(audit, ensure_ascii=False)
    slop = [label for label, pattern in SLOP_PATTERNS if pattern.search(audit_text)]
    dash_count = audit_text.count("—") + audit_text.count("–")
    description_failure = (
        "yandex." in str(row.get("source_url") or "").lower()
        and not (
            current.get("description_applicable") is False
            and current.get("description_present") is None
            and "positioning_description_gap" not in audit_text
            and "добавить описание" not in audit_text.lower()
            and "понятного описания" not in audit_text.lower()
            and "показать в описании" not in audit_text.lower()
        )
    )
    if gate.get("status") != "pass" or slop or dash_count or description_failure:
        copy_failures.append(
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "editorial_gate": gate,
                "slop": slop,
                "long_dash_count": dash_count,
                "description_failure": description_failure,
            }
        )
public_failures = []
for row in rows:
    slug = str(row.get("slug") or "")
    url = f"https://localos.pro/api/partnership/public/offer/{slug}"
    try:
        response = requests.get(url, timeout=20)
        payload = response.json() if response.ok else {}
        page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
        audit = page.get("audit") if isinstance(page.get("audit"), dict) else {}
        rendered = json.dumps(audit, ensure_ascii=False)
        slop = [label for label, pattern in SLOP_PATTERNS if pattern.search(rendered)]
        problems = []
        if response.status_code != 200:
            problems.append(f"http_{response.status_code}")
        if str(page.get("lead_id") or "") != str(row.get("id") or ""):
            problems.append("lead_id_mismatch")
        if str(page.get("name") or "") != str(row.get("name") or ""):
            problems.append("name_mismatch")
        if slop:
            problems.append("slop:" + ",".join(slop))
        if "—" in rendered or "–" in rendered:
            problems.append("long_dash")
        current = audit.get("current_state") if isinstance(audit.get("current_state"), dict) else {}
        if "yandex." in str(row.get("source_url") or "").lower() and not (
            current.get("description_applicable") is False
            and current.get("description_present") is None
            and "positioning_description_gap" not in rendered
            and "добавить описание" not in rendered.lower()
            and "понятного описания" not in rendered.lower()
            and "показать в описании" not in rendered.lower()
        ):
            problems.append("yandex_description_gap_present")
        if problems:
            public_failures.append({"name": row.get("name"), "url": url, "problems": problems})
    except Exception as exc:
        public_failures.append({"name": row.get("name"), "url": url, "problems": [type(exc).__name__]})
print(
    json.dumps(
        {
            "rows": len(rows),
            "with_audit": sum(bool(row["slug"]) for row in rows),
            "edit_statuses": {
                status: sum(row.get("edit_status") == status for row in rows)
                for status in sorted({str(row.get("edit_status") or "") for row in rows})
            },
            "has_edited_json": sum(bool(row.get("has_edited_json")) for row in rows),
            "mismatches": len(mismatches),
            "items": [
                {
                    key: row.get(key)
                    for key in (
                        "id", "name", "rating", "reviews_count", "slug",
                        "audit_rating", "audit_reviews", "updated_at",
                    )
                }
                for row in mismatches
            ],
            "copy_failures": len(copy_failures),
            "copy_failure_names": [row["name"] for row in copy_failures],
            "public_pages_checked": len(rows),
            "public_page_failures": len(public_failures),
            "public_failure_items": public_failures,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
)
