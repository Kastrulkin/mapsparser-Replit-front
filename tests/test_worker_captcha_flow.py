import uuid

def test_worker_schedules_automatic_captcha_retry(monkeypatch, postgres_container, run_migrations):
    """
    Проверяет, что при captcha_detected воркер переводит задачу
    в status='captcha', captcha_status='delayed_auto' с корректными полями.
    """
    raw_url = postgres_container.get_connection_url()
    database_url = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    monkeypatch.setenv("DATABASE_URL", database_url)

    import worker

    # Вставляем канонически валидную pending-задачу в схему миграций.
    task_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    conn = worker.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, "captcha@test.local"))
    cur.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
    cur.execute(
        """
        INSERT INTO parsequeue (id, url, user_id, status, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (task_id, "https://yandex.ru/maps/org/123/", user_id, "pending"),
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
    assert captcha_status == "delayed_auto"
    assert captcha_session_id == "S1"
    assert captcha_started_at is not None
    assert resume_requested == 0
