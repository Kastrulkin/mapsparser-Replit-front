import uuid

def test_worker_marks_captcha_expired_after_ttl(monkeypatch, postgres_container, run_migrations):
    """
    Проверяет, что при истёкшем TTL воркер помечает captcha-задачу как expired
    и очищает captcha_* поля, а также закрывает сессию в ACTIVE_CAPTCHA_SESSIONS.
    """
    raw_url = postgres_container.get_connection_url()
    database_url = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    monkeypatch.setenv("DATABASE_URL", database_url)

    import worker

    task_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Вставляем канонически валидную задачу старше TTL.
    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, "expired@test.local"))
    cur.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
    # captcha_started_at делаем старше TTL (строка ISO)
    cur.execute(
        """
        INSERT INTO parsequeue (
            id, url, user_id, status, created_at,
            captcha_required, captcha_url, captcha_session_id,
            captcha_started_at, captcha_status, resume_requested
        )
        VALUES (%s, %s, %s, 'captcha', NOW(),
                1, %s, %s,
                to_char(NOW() - INTERVAL '60 minutes', 'YYYY-MM-DD\"T\"HH24:MI:SS'),
                'waiting', 0)
        """,
        (task_id, "https://yandex.ru/maps/org/123/", user_id, "https://captcha.test/", "S1"),
    )
    conn.commit()
    cur.close()
    conn.close()

    # Мокаем BrowserSessionManager, чтобы не трогать реальный Playwright
    closed = {"called": False}

    def fake_get(registry, session_id):
        return object()

    def fake_close_session(session):
        closed["called"] = True

    monkeypatch.setattr(worker.BROWSER_SESSION_MANAGER, "get", fake_get)
    monkeypatch.setattr(worker.BROWSER_SESSION_MANAGER, "close_session", fake_close_session)

    # Регаем фиктивную сессию
    worker.ACTIVE_CAPTCHA_SESSIONS["S1"] = object()

    worker.process_queue()

    # Проверяем, что сессия закрыта и удалена из реестра
    assert closed["called"] is True
    assert "S1" not in worker.ACTIVE_CAPTCHA_SESSIONS

    # Проверяем состояние записи в ParseQueue
    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status,
               captcha_status,
               captcha_required,
               captcha_url,
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
    captcha_status = row["captcha_status"]
    captcha_required = row["captcha_required"]
    captcha_url = row["captcha_url"]
    captcha_session_id = row["captcha_session_id"]
    captcha_started_at = row["captcha_started_at"]
    resume_requested = row["resume_requested"]

    assert status == "pending"
    assert captcha_status == "expired"
    assert captcha_required == 0
    assert captcha_url is None
    assert captcha_session_id is None
    assert captcha_started_at is None
    assert resume_requested == 0
