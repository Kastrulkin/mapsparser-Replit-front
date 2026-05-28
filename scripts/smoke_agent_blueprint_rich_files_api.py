#!/usr/bin/env python3
import io
import json
import os
import sys
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook


repo_root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
for candidate in (os.getenv("APP_SRC_DIR"), "/app/src", str(repo_root / "src")):
    if candidate and candidate not in sys.path:
        sys.path.insert(0, candidate)

from auth_system import hash_password
from database_manager import get_db_connection


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")
KEEP_FIXTURE = os.getenv("SMOKE_KEEP_FIXTURE", "").strip().lower() in {"1", "true", "yes"}
PASSWORD = os.getenv("SMOKE_PASSWORD", f"SmokePass-RichFiles-{uuid.uuid4().hex[:12]}-Aa1")


def request_json(method, path, payload=None, token=None, expected_status=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        kwargs["data"] = json.dumps(payload)
    response = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)
    try:
        data = response.json() if response.text.strip() else {}
    except Exception:
        raise RuntimeError(f"{method} {path}: non-json response {response.status_code}: {response.text[:200]}")
    if expected_status and response.status_code != expected_status:
        raise RuntimeError(f"{method} {path}: expected {expected_status}, got {response.status_code}: {data}")
    if response.status_code >= 400 and expected_status is None:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {data}")
    return response.status_code, data


def setup_fixture(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO users (
                id, email, name, phone, password_hash, is_active, is_verified,
                email_verified_at, personal_data_consent_at,
                personal_data_consent_version, credits_balance, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, NOW(), NOW(), %s, %s, %s, %s)
            """,
            (
                ids["user_id"],
                ids["email"],
                "Smoke Rich Files Agent User",
                "+10000000004",
                hash_password(PASSWORD),
                "localos-personal-data-v1-2026-05-11",
                100000,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            INSERT INTO businesses (
                id, owner_id, name, business_type, address, city, country,
                is_active, subscription_tier, subscription_status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                ids["business_id"],
                ids["user_id"],
                "Smoke Rich Files Agent Business",
                "beauty_salon",
                "Smoke Street 7",
                "Smoke City",
                "US",
                "starter",
                "active",
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cleanup_fixture(ids):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM agent_approvals
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_artifacts
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute(
            """
            DELETE FROM agent_run_steps
            WHERE run_id IN (SELECT id FROM agent_runs WHERE blueprint_id = %s)
            """,
            (ids["blueprint_id"],),
        )
        cursor.execute("DELETE FROM agent_runs WHERE blueprint_id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM agent_blueprint_versions WHERE blueprint_id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM agent_blueprints WHERE id = %s", (ids["blueprint_id"],))
        cursor.execute("DELETE FROM usersessions WHERE user_id = %s", (ids["user_id"],))
        cursor.execute("DELETE FROM businesses WHERE id = %s", (ids["business_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (ids["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_pdf_bytes(text):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("utf-8")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length "
        + str(len(stream)).encode("ascii")
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for item in objects:
        offsets.append(len(output))
        output.extend(item)
    xref_offset = len(output)
    output.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(b"trailer << /Root 1 0 R /Size 6 >>\n")
    output.extend(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def build_docx_bytes(text):
    buffer = io.BytesIO()
    archive = zipfile.ZipFile(buffer, "w")
    try:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
                "</w:document>"
            ),
        )
    finally:
        archive.close()
    return buffer.getvalue()


def build_xlsx_bytes():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Risks"
    sheet.append(["Field", "Value"])
    sheet.append(["Penalty", "10 percent"])
    sheet.append(["Deadline", "June 10"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload_source(token, blueprint_id, name, file_name, content, mime_type):
    _, payload = request_json(
        "POST",
        f"/api/agent-blueprints/{blueprint_id}/sources/upload",
        token=token,
        expected_status=201,
        data={"name": name},
        files={"file": (file_name, content, mime_type)},
    )
    return payload.get("source") or {}


def assert_source(source, expected_method, expected_text):
    if source.get("extraction_state") != "ready":
        raise RuntimeError(f"source extraction is not ready: {source}")
    if source.get("extraction_method") != expected_method:
        raise RuntimeError(f"source extraction method mismatch: {source}")
    if expected_text not in str(source.get("content_text") or ""):
        raise RuntimeError(f"source text missing expected fragment {expected_text!r}: {source}")


def main():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "user_id": f"smoke-rich-agent-user-{suffix}",
        "business_id": f"smoke-rich-agent-business-{suffix}",
        "blueprint_id": "",
        "run_id": "",
        "email": f"smoke-rich-agent-{suffix}@example.invalid",
    }
    fixture_created = False
    try:
        setup_fixture(ids)
        fixture_created = True
        _, login_payload = request_json(
            "POST",
            "/api/auth/login",
            {"email": ids["email"], "password": PASSWORD},
            expected_status=200,
        )
        token = login_payload.get("token")
        if not token:
            raise RuntimeError("login did not return token")

        _, draft_payload = request_json(
            "POST",
            "/api/agent-blueprints/draft",
            {
                "business_id": ids["business_id"],
                "description": "Проверь документы, выдели риски, факты и поля",
                "category": "documents",
            },
            token=token,
            expected_status=201,
        )
        ids["blueprint_id"] = draft_payload["blueprint"]["id"]
        request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/setup",
            {
                "workflow_description": "Проверить комплект документов перед ручным решением",
                "data_sources": ["uploaded_documents"],
                "extraction_rules": "Найти платежи, сроки, штрафы, обязательства и открытые вопросы",
                "processing_rules": "Не отправлять наружу и не публиковать. Использовать только извлеченный текст.",
                "output_format": "summary, facts, fields, risks, next_questions",
                "approval_boundaries": ["final_output", "external_delivery"],
                "manual_control": "Пользователь проверяет итог перед любым внешним действием",
            },
            token=token,
            expected_status=200,
        )

        pdf_source = upload_source(
            token,
            ids["blueprint_id"],
            "Smoke PDF contract",
            "contract.pdf",
            build_pdf_bytes("Payment 15000. Penalty 12 percent. Deadline June 10."),
            "application/pdf",
        )
        assert_source(pdf_source, "pypdf", "Payment 15000")

        docx_source = upload_source(
            token,
            ids["blueprint_id"],
            "Smoke DOCX contract",
            "contract.docx",
            build_docx_bytes("DOCX contract includes penalty and deadline."),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert_source(docx_source, "docx_xml", "DOCX contract")

        xlsx_source = upload_source(
            token,
            ids["blueprint_id"],
            "Smoke XLSX risks",
            "risks.xlsx",
            build_xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert_source(xlsx_source, "openpyxl", "Penalty")

        _, bad_type_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/sources/upload",
            token=token,
            expected_status=400,
            data={"name": "Unsafe file"},
            files={"file": ("payload.exe", b"bad", "application/octet-stream")},
        )
        if bad_type_payload.get("code") != "UNSUPPORTED_FILE_TYPE" or "поддерживается" not in str(bad_type_payload.get("error") or "").lower():
            raise RuntimeError(f"unsupported file error is not readable: {bad_type_payload}")

        _, empty_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/sources/upload",
            token=token,
            expected_status=400,
            data={"name": "Empty file"},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        if empty_payload.get("code") != "EMPTY_FILE" or "пуст" not in str(empty_payload.get("error") or "").lower():
            raise RuntimeError(f"empty file error is not readable: {empty_payload}")

        _, catalog_payload = request_json(
            "GET",
            f"/api/agent-blueprints/{ids['blueprint_id']}/sources/catalog",
            token=token,
            expected_status=200,
        )
        connected = [
            item
            for item in (catalog_payload.get("catalog") or [])
            if item.get("connected") is True and str(item.get("key") or "").startswith("agent_source:")
        ]
        connected_titles = {str(item.get("title") or "") for item in connected}
        for title in {"Smoke PDF contract", "Smoke DOCX contract", "Smoke XLSX risks"}:
            if title not in connected_titles:
                raise RuntimeError(f"catalog missing connected rich source {title}: {catalog_payload}")
        if any(item.get("state") != "ready" for item in connected if item.get("title") in connected_titles):
            raise RuntimeError(f"catalog has non-ready connected source: {catalog_payload}")

        _, run_payload = request_json(
            "POST",
            f"/api/agent-blueprints/{ids['blueprint_id']}/runs",
            {"input": {"source": "rich_files_smoke"}},
            token=token,
            expected_status=201,
        )
        run = run_payload["run"]
        ids["run_id"] = run["id"]
        if run.get("status") != "waiting_approval":
            raise RuntimeError(f"document run did not stop for approval: {run}")
        if any(item.get("step_type") == "capability" for item in run.get("steps", [])):
            raise RuntimeError(f"generic rich-file document run executed a capability: {run.get('steps')}")
        artifacts = [item for item in run.get("artifacts", []) if item.get("artifact_type") == "agent_output_draft"]
        if not artifacts:
            raise RuntimeError(f"rich-file document run missing output draft: {run}")
        output_payload = artifacts[-1].get("payload_json") or {}
        result = output_payload.get("result") or {}
        if output_payload.get("external_dispatch_performed") is not False or output_payload.get("dispatch_state") != "not_dispatched":
            raise RuntimeError(f"rich-file document output boundary failed: {output_payload}")
        if result.get("external_dispatch_performed") is not False:
            raise RuntimeError(f"rich-file document result boundary failed: {result}")
        if not output_payload.get("provenance"):
            raise RuntimeError(f"rich-file document output missing provenance: {output_payload}")
        if not result.get("facts") or not result.get("risks"):
            raise RuntimeError(f"rich-file document output is not useful enough: {result}")

        _, review_payload = request_json(
            "GET",
            f"/api/agent-blueprints/{ids['blueprint_id']}/review",
            token=token,
            expected_status=200,
        )
        journal = review_payload.get("review", {}).get("journal") or []
        journal_kinds = {str(item.get("kind") or "") for item in journal if isinstance(item, dict)}
        if not {"input", "extraction", "output", "approval"}.issubset(journal_kinds):
            raise RuntimeError(f"rich-file review journal is incomplete: {review_payload}")
        output_entries = [item for item in journal if isinstance(item, dict) and item.get("kind") == "output"]
        output_details = output_entries[-1].get("details") if output_entries else []
        labels = {str(item.get("label") or "") for item in output_details if isinstance(item, dict)}
        if "Источник анализа" not in labels or "Внешняя отправка" not in labels:
            raise RuntimeError(f"rich-file review output is too technical or incomplete: {review_payload}")

        print(
            json.dumps(
                {
                    "success": True,
                    "base_url": BASE_URL,
                    "business_id": ids["business_id"],
                    "blueprint_id": ids["blueprint_id"],
                    "run_id": ids["run_id"],
                    "uploaded_sources": [
                        {"name": pdf_source.get("name"), "method": pdf_source.get("extraction_method")},
                        {"name": docx_source.get("name"), "method": docx_source.get("extraction_method")},
                        {"name": xlsx_source.get("name"), "method": xlsx_source.get("extraction_method")},
                    ],
                    "catalog_connected_sources": sorted(connected_titles),
                    "journal_kinds": sorted(journal_kinds),
                    "analysis_source": output_payload.get("analysis_source"),
                    "llm_analysis_used": output_payload.get("llm_analysis_used"),
                    "external_dispatch_performed": False,
                    "fixture_cleaned": not KEEP_FIXTURE,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if KEEP_FIXTURE:
            print("SMOKE_KEEP_FIXTURE enabled; fixture was not removed.", file=sys.stderr)
        elif fixture_created:
            cleanup_fixture(ids)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
