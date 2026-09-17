import uuid

def test_worker_resume_clears_captcha_fields(monkeypatch, postgres_container, run_migrations):
    """
    Проверяет, что при resume (resume_requested=1) и успешном парсинге
    воркер очищает captcha_* поля и завершает задачу.
    """
    raw_url = postgres_container.get_connection_url()
    database_url = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    monkeypatch.setenv("DATABASE_URL", database_url)

    import worker

    task_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, "resume@test.local"))
    cur.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
    cur.execute(
        """
        INSERT INTO parsequeue (
            id, url, user_id, status, created_at,
            captcha_required, captcha_url, captcha_session_id,
            captcha_started_at, captcha_status, resume_requested
        )
        VALUES (%s, %s, %s, 'captcha', NOW(),
                1, %s, %s, NOW(), 'waiting', 1)
        """,
        (task_id, "https://yandex.ru/maps/org/123/", user_id, "https://captcha.test/", "S1"),
    )
    conn.commit()
    cur.close()
    conn.close()

    # parse_yandex_card для resume возвращает успешный результат
    def fake_parse_yandex_card(url, **kwargs):
        return {
            "title": "OK",
            "address": "Address",
            "rating": 4.5,
            "reviews_count": 0,
            "categories": ["salon"],
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

    assert status == "completed"
    assert captcha_required == 0
    assert captcha_status is None
    assert captcha_session_id is None
    assert captcha_started_at is None
    assert resume_requested == 0
