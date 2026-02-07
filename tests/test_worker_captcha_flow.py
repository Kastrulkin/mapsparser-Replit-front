import os
import uuid

import pytest


def test_worker_sets_captcha_waiting(monkeypatch):
    """
    Проверяет, что при captcha_detected воркер переводит задачу
    в status='captcha' с корректными полями.
    """
    if "TEST_DATABASE_URL" not in os.environ:
        pytest.skip("TEST_DATABASE_URL is not set")

    # Настраиваем DATABASE_URL для слоя БД проекта
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

    import worker

    # Готовим таблицу ParseQueue и вставляем pending-задачу
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
        INSERT INTO parsequeue (id, url, status, created_at)
        VALUES (%s, %s, %s, NOW())
        """,
        (task_id, "https://yandex.ru/maps/org/123/", "pending"),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Мокаем parse_yandex_card так, чтобы он возвращал капчу
    def fake_parse_yandex_card(url, **kwargs):
        return {
            "error": "captcha_detected",
            "captcha_url": "https://captcha.test/",
            "captcha_session_id": "S1",
            "captcha_needs_human": True,
        }

    monkeypatch.setattr(worker, "parse_yandex_card", fake_parse_yandex_card)
    worker.ACTIVE_CAPTCHA_SESSIONS.clear()

    # Запускаем обработку одной задачи
    worker.process_queue()

    # Проверяем состояние в ParseQueue
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

    assert status == "captcha"
    assert captcha_required == 1
    assert captcha_status == "waiting"
    assert captcha_session_id == "S1"
    assert captcha_started_at is not None
    assert resume_requested == 0

