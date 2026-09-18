"""Real-PostgreSQL reproducer for provider-accepted social publish commit ambiguity."""

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import urlsplit, urlunsplit
import uuid

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import TRANSACTION_STATUS_IDLE, parse_dsn
import pytest


ROOT = Path(__file__).parents[1]
OWNED_PREFIX = "localos_social_publish_amb_"


def isolated_base_dsn() -> str:
    database_url = os.getenv("LOCALOS_READINESS_JOURNEY_DATABASE_URL", "")
    if not database_url:
        pytest.skip("LOCALOS_READINESS_JOURNEY_DATABASE_URL is required")
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE") or os.getenv("PGSERVICEFILE") or os.getenv("PGOPTIONS"):
        raise RuntimeError("test refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    params = parse_dsn(database_url)
    port = str(params.get("port") or "")
    if (
        parsed.scheme != "postgresql"
        or parsed.query
        or parsed.fragment
        or str(params.get("host") or "") not in {"127.0.0.1", "::1"}
        or not port.isdigit()
        or int(port) < 32768
        or not str(params.get("dbname") or "").startswith("readiness_")
        or params.get("hostaddr")
        or params.get("service")
    ):
        raise RuntimeError("test requires an explicit loopback readiness DSN")
    return database_url


def database_url_for(database_url: str, database_name: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", "", ""))


def migrate(database_url: str) -> None:
    guard_path = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
    guard_file = Path(guard_path) / "sitecustomize.py"
    if not guard_path or not guard_file.is_file():
        raise RuntimeError("test requires the canonical no-egress sitecustomize guard first in PYTHONPATH")
    guard_hash = hashlib.sha256(guard_file.read_bytes()).hexdigest()
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "DATABASE_URL": database_url,
        "FLASK_APP": "src.main:app",
        "PYTHONPATH": os.pathsep.join((guard_path, str(ROOT / "src"), str(ROOT))),
        "PYTHON_DOTENV_DISABLED": "1",
        "BROWSER_COOKIE_AUTH_ENABLED": "false",
    }
    guard_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import hashlib,json,sitecustomize; print(json.dumps({'origin': sitecustomize.__file__, 'sha256': hashlib.sha256(open(sitecustomize.__file__, 'rb').read()).hexdigest()}))",
        ],
        env={
            "PATH": environment["PATH"],
            "HOME": environment["HOME"],
            "PYTHONPATH": guard_path,
            "PYTHON_DOTENV_DISABLED": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if guard_probe.returncode:
        raise RuntimeError("test no-egress guard probe failed")
    provenance = json.loads(guard_probe.stdout.strip())
    if Path(str(provenance.get("origin") or "")).resolve() != guard_file.resolve() or provenance.get("sha256") != guard_hash:
        raise RuntimeError("test no-egress guard provenance mismatch")
    completed = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-2000:])


@pytest.fixture
def social_publish_database(monkeypatch):
    base_dsn = isolated_base_dsn()
    database_name = OWNED_PREFIX + uuid.uuid4().hex
    admin = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
    cursor = admin.cursor()
    try:
        admin.autocommit = True
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    finally:
        cursor.close()
        admin.close()
    database_url = database_url_for(base_dsn, database_name)
    try:
        migrate(database_url)
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
        monkeypatch.setenv("BROWSER_COOKIE_AUTH_ENABLED", "false")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:synthetic-test-token")
        yield database_url
    finally:
        admin = psycopg2.connect(database_url_for(base_dsn, "postgres"), connect_timeout=5)
        cursor = admin.cursor()
        try:
            admin.autocommit = True
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
        finally:
            cursor.close()
            admin.close()


def seed_approved_post(database_url: str) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    business_id = str(uuid.uuid4())
    post_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users(id,email,is_active,is_verified,is_superadmin) VALUES (%s,%s,TRUE,TRUE,FALSE)",
            (user_id, f"{user_id}@example.invalid"),
        )
        cursor.execute(
            "INSERT INTO businesses(id,owner_id,name,entity_group,telegram_chat_id) VALUES (%s,%s,'Synthetic publish','client','@synthetic_channel')",
            (business_id, user_id),
        )
        cursor.execute(
            "INSERT INTO contentplans(id,business_id,title,period_days,period_start,period_end,plan_status,generated_plan_json) VALUES (%s,%s,'Plan',30,CURRENT_DATE,CURRENT_DATE + 30,'generated','{}')",
            (plan_id, business_id),
        )
        cursor.execute(
            "INSERT INTO contentplanitems(id,plan_id,business_id,theme,goal,scheduled_for,status,metadata_json) VALUES (%s,%s,%s,'Theme','Goal',CURRENT_DATE,'planned','{}')",
            (item_id, plan_id, business_id),
        )
        cursor.execute(
            "INSERT INTO social_posts(id,business_id,content_plan_id,content_plan_item_id,platform,publish_mode,status,base_text,platform_text,media_json,metadata_json,created_by) VALUES (%s,%s,%s,%s,'telegram','api','needs_review','Text','Text','[]','{}',%s)",
            (post_id, business_id, plan_id, item_id, user_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    approved = social_post_service.approve_social_post(user_id, post_id)
    assert approved["status"] == "approved"
    return user_id, post_id


def post_receipt(database_url: str, post_id: str) -> tuple[str, str | None]:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT status,provider_post_id FROM social_posts WHERE id=%s", (post_id,))
        row = cursor.fetchone()
        return str(row[0]), row[1]
    finally:
        cursor.close()
        connection.close()


def post_metadata(database_url: str, post_id: str) -> dict:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT metadata_json FROM social_posts WHERE id=%s", (post_id,))
        row = cursor.fetchone()
        return row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
    finally:
        cursor.close()
        connection.close()


def post_row(database_url: str, post_id: str) -> tuple:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT business_id,content_plan_id,content_plan_item_id,scheduled_for,publish_mode,status,metadata_json FROM social_posts WHERE id=%s",
            (post_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def accepted_response(sends: list[str]):
    class Response:
        status = 200

        def read(self):
            sends.append("accepted")
            return json.dumps({"ok": True, "result": {"message_id": len(sends)}}).encode("utf-8")

        def close(self):
            return None

    return Response()


def test_provider_success_then_local_commit_failure_blocks_second_send(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    sends: list[str] = []

    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))
    real_database_manager = social_post_service.DatabaseManager

    class FailingCommitManager:
        def __init__(self):
            self.delegate = real_database_manager()
            self.conn = FailingConnection(self.delegate.conn)

        def close(self):
            self.conn.close()

    class FailingConnection:
        def __init__(self, delegate):
            self.delegate = delegate

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def commit(self):
            raise RuntimeError("synthetic local commit failure after provider acceptance")

    manager_calls = {"count": 0}

    def database_manager():
        manager_calls["count"] += 1
        if manager_calls["count"] == 3:
            return FailingCommitManager()
        return real_database_manager()

    monkeypatch.setattr(social_post_service, "DatabaseManager", database_manager)

    with pytest.raises(RuntimeError, match="synthetic local commit failure"):
        social_post_service.publish_social_post(user_id, post_id)

    assert sends == ["accepted"]
    assert post_receipt(social_publish_database, post_id) == ("publishing", None)

    second = social_post_service.publish_social_post(user_id, post_id)

    assert sends == ["accepted"]
    assert second["status"] == "publishing"
    assert post_receipt(social_publish_database, post_id) == ("publishing", None)


def test_published_replay_keeps_receipt_and_sends_once(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    sends: list[str] = []
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))

    first = social_post_service.publish_social_post(user_id, post_id)
    second = social_post_service.publish_social_post(user_id, post_id)

    assert first["status"] == "published"
    assert second["status"] == "published"
    assert sends == ["accepted"]
    assert post_receipt(social_publish_database, post_id)[0] == "published"


def test_missing_approval_never_reaches_transport(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    connection = psycopg2.connect(social_publish_database, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE social_posts SET approval_id=NULL WHERE id=%s", (post_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    sends: list[str] = []
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))

    with pytest.raises(PermissionError, match="подтверждение человека"):
        social_post_service.publish_social_post(user_id, post_id)

    assert sends == []
    assert post_receipt(social_publish_database, post_id)[0] == "approved"


def test_provider_exception_keeps_intent_for_reconciliation(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    calls: list[str] = []

    def failing_transport(_request, timeout=15):
        calls.append("attempted")
        raise TimeoutError("synthetic transport timeout")

    monkeypatch.setattr(social_post_service, "telegram_urlopen", failing_transport)
    first = social_post_service.publish_social_post(user_id, post_id)
    second = social_post_service.publish_social_post(user_id, post_id)

    assert first["status"] == "publishing"
    assert second["status"] == "publishing"
    assert second["next_action"] == "reconcile_publication"
    assert calls == ["attempted"]
    assert post_metadata(social_publish_database, post_id)["publish_attempt"]["state"] == "uncertain"


def test_concurrent_publish_has_one_provider_call(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    entered = threading.Event()
    release = threading.Event()
    sends: list[str] = []
    results: list[dict] = []
    errors: list[Exception] = []

    def delayed_transport(_request, timeout=15):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test transport wait expired")
        return accepted_response(sends)

    def first_publish():
        try:
            results.append(social_post_service.publish_social_post(user_id, post_id))
        except Exception:
            errors.append(sys.exc_info()[1])

    monkeypatch.setattr(social_post_service, "telegram_urlopen", delayed_transport)
    worker = threading.Thread(target=first_publish)
    worker.start()
    assert entered.wait(5)
    second = social_post_service.publish_social_post(user_id, post_id)
    release.set()
    worker.join(5)

    assert errors == []
    assert second["status"] == "publishing"
    assert len(results) == 1
    assert results[0]["status"] == "published"
    assert sends == ["accepted"]


def test_stale_finalizer_and_manual_reconciliation_are_guarded(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    claimed = social_post_service._claim_social_post_publish(user_id, post_id)
    attempt = claimed["metadata_json"]["publish_attempt"]
    stale = social_post_service._finalize_social_post_publish(
        user_id,
        post_id,
        "wrong-attempt",
        {"publish_outcome": "accepted", "provider_post_id": "provider-1"},
    )

    assert stale["status"] == "publishing"
    assert post_receipt(social_publish_database, post_id) == ("publishing", None)
    with pytest.raises(ValueError, match="ссылку или ID"):
        social_post_service.mark_manual_published(user_id, post_id, content_confirmed=True)
    with pytest.raises(PermissionError):
        social_post_service.mark_manual_published(str(uuid.uuid4()), post_id, "https://example.invalid/p/1", content_confirmed=True)

    reconciled = social_post_service.mark_manual_published(
        user_id,
        post_id,
        "https://example.invalid/p/1",
        "provider-1",
        True,
    )

    assert reconciled["status"] == "published"
    metadata = post_metadata(social_publish_database, post_id)
    assert metadata["publish_attempt"]["id"] == attempt["id"]
    assert metadata["publish_attempt"]["state"] == "manual_confirmed"


def test_publishing_row_resists_stale_upsert_and_worker_preflight(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service
    from services.social_posts import dispatch_reports, workflow

    user_id, post_id = seed_approved_post(social_publish_database)
    claimed = social_post_service._claim_social_post_publish(user_id, post_id)
    before = post_row(social_publish_database, post_id)
    metadata_before = before[6] if isinstance(before[6], dict) else json.loads(before[6] or "{}")
    connection = psycopg2.connect(social_publish_database, connect_timeout=5)
    cursor = connection.cursor()
    try:
        dispatch_reports._upsert_social_post(
            cursor,
            user_id,
            {
                "id": str(before[2]),
                "plan_id": str(before[1]),
                "business_id": str(before[0]),
                "scheduled_for": "2040-01-01",
            },
            "telegram",
            "replacement text",
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    after_upsert = post_row(social_publish_database, post_id)
    metadata_after = after_upsert[6] if isinstance(after_upsert[6], dict) else json.loads(after_upsert[6] or "{}")
    assert after_upsert[3:6] == before[3:6]
    assert metadata_after == metadata_before
    monkeypatch.setattr(
        workflow,
        "_api_channel_preflight_for_platform",
        lambda _cursor, _business_id, _platform: {"ready": False, "status": "synthetic_not_ready"},
    )

    preflight = workflow._dispatch_live_api_preflight_block(user_id, post_id)

    assert preflight["status"] == "publishing"
    assert preflight["next_action"] == "reconcile_publication"
    assert post_metadata(social_publish_database, post_id)["publish_attempt"]["id"] == claimed["metadata_json"]["publish_attempt"]["id"]


def test_existing_provider_receipt_blocks_new_claim(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    connection = psycopg2.connect(social_publish_database, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE social_posts SET provider_post_url=%s WHERE id=%s", (" https://example.invalid/receipt ", post_id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    sends: list[str] = []
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))

    result = social_post_service.publish_social_post(user_id, post_id)

    assert result["status"] == "approved"
    assert sends == []


def test_bulk_manual_confirmation_rejects_publishing_row(social_publish_database):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    social_post_service._claim_social_post_publish(user_id, post_id)

    result = social_post_service.mark_manual_published_posts(
        user_id,
        [post_id],
        "https://example.invalid/receipt",
        "provider-1",
        True,
    )

    assert result["posts"] == []
    assert result["failed"][0]["id"] == post_id
    assert post_receipt(social_publish_database, post_id) == ("publishing", None)


def test_provider_phase_holds_idle_session_lock_and_blocks_manual_reconciliation(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    entered = threading.Event()
    release = threading.Event()
    results: list[dict] = []
    errors: list[Exception] = []

    def provider_stub(cursor, _post, snapshot):
        assert cursor.connection.get_transaction_status() == TRANSACTION_STATUS_IDLE
        assert snapshot["approval_id"]
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test provider wait expired")
        return {"publish_outcome": "accepted", "provider_post_id": "provider-1"}

    def publish():
        try:
            results.append(social_post_service.publish_social_post(user_id, post_id))
        except Exception:
            errors.append(sys.exc_info()[1])

    monkeypatch.setattr(social_post_service, "_publish_api_post", provider_stub)
    worker = threading.Thread(target=publish)
    worker.start()
    assert entered.wait(5)
    with pytest.raises(RuntimeError, match="сверяется"):
        social_post_service.mark_manual_published(user_id, post_id, "https://example.invalid/receipt", "provider-1", True)
    release.set()
    worker.join(5)

    assert errors == []
    assert results[0]["status"] == "published"


def test_manual_reconciliation_before_replay_prevents_transport(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    social_post_service._claim_social_post_publish(user_id, post_id)
    social_post_service.mark_manual_published(user_id, post_id, "https://example.invalid/receipt", "provider-1", True)
    sends: list[str] = []
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))

    replay = social_post_service.publish_social_post(user_id, post_id)

    assert replay["status"] == "published"
    assert sends == []


def test_manual_reconciliation_before_claimed_provider_phase_prevents_transport(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    claimed = social_post_service._claim_social_post_publish(user_id, post_id)
    social_post_service.mark_manual_published(user_id, post_id, "https://example.invalid/receipt", "provider-1", True)
    sends: list[str] = []
    monkeypatch.setattr(social_post_service, "_claim_social_post_publish", lambda _user_id, _post_id: claimed)
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda _request, timeout=15: accepted_response(sends))

    result = social_post_service.publish_social_post(user_id, post_id)

    assert result["status"] == "published"
    assert result["next_action"] == "collect_metrics"
    assert sends == []


def test_vk_refresh_persists_with_provider_autocommit_connection(social_publish_database, monkeypatch):
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from services import social_post_service

    user_id, post_id = seed_approved_post(social_publish_database)
    business_id = str(post_row(social_publish_database, post_id)[0])
    account_id = str(uuid.uuid4())
    connection = psycopg2.connect(social_publish_database, connect_timeout=5)
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO externalbusinessaccounts(id,business_id,source,external_id,auth_data_encrypted,is_active) VALUES (%s,%s,'vk','group-1','old',TRUE)",
            (account_id, business_id),
        )
        connection.commit()
        connection.set_session(autocommit=True)
        monkeypatch.setattr(
            social_post_service,
            "refresh_vk_oauth_tokens",
            lambda refresh_token, device_id: {"access_token": "fresh-token", "refresh_token": "fresh-refresh", "expires_in": 3600},
        )
        monkeypatch.setattr(social_post_service, "oauth_token_expiry", lambda _seconds: "2099-01-01T00:00:00+00:00")
        monkeypatch.setattr(social_post_service, "encrypt_auth_data", lambda value: f"encrypted:{value}")
        refreshed = social_post_service._vk_auth_data_with_fresh_token(
            cursor,
            {"id": account_id},
            {"auth_mode": "vk_id_oauth", "expires_at": "2000-01-01T00:00:00+00:00", "refresh_token": "old-refresh", "device_id": "device-1"},
        )
    finally:
        cursor.close()
        connection.close()
    verify_connection = psycopg2.connect(social_publish_database, connect_timeout=5)
    verify_cursor = verify_connection.cursor()
    try:
        verify_cursor.execute("SELECT auth_data_encrypted FROM externalbusinessaccounts WHERE id=%s", (account_id,))
        persisted = str(verify_cursor.fetchone()[0])
    finally:
        verify_cursor.close()
        verify_connection.close()

    assert refreshed["access_token"] == "fresh-token"
    assert "fresh-token" in persisted
