import os
import uuid

import pytest


def test_worker_resume_clears_captcha_fields(monkeypatch):
    """
    Проверяет, что при resume (resume_requested=1) и успешном парсинге
    воркер очищает captcha_* поля и переводит задачу в status='processing'.
    """
    if "TEST_DATABASE_URL" not in os.environ:
        pytest.skip("TEST_DATABASE_URL is not set")

    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

    import worker

    task_id = str(uuid.uuid4())
    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS parsequeue (
            id TEXT PRIMARY KEY,
            url TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP,
            retry_after TIMESTAMP NULL,
            captcha_required INT DEFAULT 0,
            captcha_url TEXT,
            captcha_session_id TEXT,
            captcha_started_at TEXT,
            captcha_status TEXT,
            resume_requested INT DEFAULT 0,
            error_message TEXT,
            business_id TEXT,
            task_type TEXT DEFAULT 'parse_card',
            account_id TEXT,
            source TEXT,
            user_id TEXT
        );
        """
    )
    cur.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
    cur.execute(
        """
        INSERT INTO parsequeue (
            id, url, status, created_at,
            captcha_required, captcha_url, captcha_session_id,
            captcha_started_at, captcha_status, resume_requested
        )
        VALUES (%s, %s, 'captcha', NOW(),
                1, %s, %s, NOW(), 'waiting', 1)
        """,
        (task_id, "https://yandex.ru/maps/org/123/", "https://captcha.test/", "S1"),
    )
    conn.commit()
    cur.close()
    conn.close()

    # parse_yandex_card для resume возвращает успешный результат
    def fake_parse_yandex_card(url, **kwargs):
        return {
            "title": "OK",
            "address": "Address",
        }

    monkeypatch.setattr(worker, "parse_yandex_card", fake_parse_yandex_card)
    worker.ACTIVE_CAPTCHA_SESSIONS.clear()

    worker.process_queue()

    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status,
               captcha_required,
               captcha_status,
               captcha_session_id,
               captcha_started_at,
               resume_requested
        FROM parsequeue
        WHERE id = %s
        """,
        (task_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row is not None
    status = row["status"]
    captcha_required = row["captcha_required"]
    captcha_status = row["captcha_status"]
    captcha_session_id = row["captcha_session_id"]
    captcha_started_at = row["captcha_started_at"]
    resume_requested = row["resume_requested"]

    assert status == "processing"
    assert captcha_required == 0
    assert captcha_status is None
    assert captcha_session_id is None
    assert captcha_started_at is None
    assert resume_requested == 0

