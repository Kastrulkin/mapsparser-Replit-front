# Gate tests for /api/client-info (Postgres-only, businessmaplinks + businesses)
# A–B–C–D–E–F–H: требуют Docker + testcontainers Postgres + миграции (flask db upgrade).
# G: статический тест, всегда выполняется, без Docker.
from __future__ import annotations

import uuid
import pytest

# postgres_container и run_migrations — в tests/conftest.py


def _schema_name():
    return "test_" + uuid.uuid4().hex


@pytest.fixture
def test_db_client_info(postgres_container, run_migrations):
    """
    Схема test_<uuid>, таблицы users, businesses, parsequeue, businessmaplinks, userservices, businessprofiles.
    Миграции уже применены (run_migrations). Один user и один business. Патчим pg_db_utils.get_db_connection и main.verify_session.
    """
    from tests.helpers.db_init_client_info import (
        create_schema,
        create_client_info_tables,
        insert_test_data,
        get_connection_with_search_path,
        _safe_schema,
    )
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # URL без драйвера SQLAlchemy (postgresql:// для psycopg2)
    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1) if "postgresql+psycopg2" in raw_url else raw_url
    schema_name = _schema_name()
    user_id = str(uuid.uuid4())
    business_id = str(uuid.uuid4())

    # Создаём схему и таблицы в default (public) подключении
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    create_schema(conn, schema_name)
    create_client_info_tables(conn, schema_name)
    insert_test_data(conn, schema_name, user_id=user_id, business_id=business_id, map_links=[])
    conn.close()

    # Патч: соединения из приложения должны использовать нашу схему
    original_get_db = None

    def patched_get_db_connection():
        return get_connection_with_search_path(dsn, schema_name)

    # Патчим в pg_db_utils (оттуда дергает database_manager)
    import pg_db_utils as pg_mod
    original_get_db = pg_mod.get_db_connection
    pg_mod.get_db_connection = patched_get_db_connection

    # Патч verify_session чтобы endpoint считал пользователя авторизованным
    import main as main_mod
    def fake_verify_session(_token):
        return {"user_id": user_id, "id": user_id, "is_superadmin": False}
    original_verify = main_mod.verify_session
    main_mod.verify_session = fake_verify_session

    yield {
        "dsn": dsn,
        "schema_name": schema_name,
        "user_id": user_id,
        "business_id": business_id,
        "client": main_mod.app.test_client(),
    }

    # Восстанавливаем
    pg_mod.get_db_connection = original_get_db
    main_mod.verify_session = original_verify


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


def _get_map_links(response):
    data = response.get_json()
    return data.get("mapLinks", []) if data else []


# --- A: GET ?business_id=... -> 200, ссылки из businessmaplinks
def test_get_client_info_with_business_id_returns_200_and_links(test_db_client_info):
    info = test_db_client_info
    # Добавляем одну ссылку напрямую в БД
    from tests.helpers.db_init_client_info import get_connection_with_search_path, _safe_schema
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO businessmaplinks (id, user_id, business_id, url, map_type) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), info["user_id"], info["business_id"], "https://yandex.ru/maps/org/123", "yandex"),
        )
    conn.commit()
    conn.close()

    r = info["client"].get(
        f"/api/client-info?business_id={info['business_id']}",
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    links = _get_map_links(r)
    assert len(links) == 1
    assert links[0]["url"] == "https://yandex.ru/maps/org/123"
    assert links[0].get("mapType") == "yandex"


# --- B: POST -> 200, затем GET возвращает сохранённые ссылки
def test_post_then_get_returns_saved_links(test_db_client_info):
    info = test_db_client_info
    payload = {
        "business_id": info["business_id"],
        "mapLinks": [
            {"url": "https://yandex.ru/maps/org/456", "mapType": "yandex"},
            {"url": "https://google.com/maps/place/789", "mapType": "google"},
        ],
    }
    r1 = info["client"].post("/api/client-info", json=payload, headers=_auth_headers())
    assert r1.status_code == 200

    r2 = info["client"].get(f"/api/client-info?business_id={info['business_id']}", headers=_auth_headers())
    assert r2.status_code == 200
    links = _get_map_links(r2)
    assert len(links) == 2
    urls = {l["url"] for l in links}
    assert "https://yandex.ru/maps/org/456" in urls
    assert "https://google.com/maps/place/789" in urls


# --- C: Идемпотентность — два POST с теми же ссылками -> ровно N строк
def test_post_idempotent_no_duplicates(test_db_client_info):
    info = test_db_client_info
    payload = {
        "business_id": info["business_id"],
        "mapLinks": [{"url": "https://yandex.ru/maps/org/same", "mapType": "yandex"}],
    }
    info["client"].post("/api/client-info", json=payload, headers=_auth_headers())
    info["client"].post("/api/client-info", json=payload, headers=_auth_headers())

    from tests.helpers.db_init_client_info import get_connection_with_search_path
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM businessmaplinks WHERE business_id = %s", (info["business_id"],))
        row = cur.fetchone()
    count = row["c"] if isinstance(row, dict) else row[0]
    conn.close()
    assert count == 1


# --- D: POST с пустыми ссылками -> 0 строк, GET возвращает пусто
def test_post_empty_links_clears_then_get_empty(test_db_client_info):
    info = test_db_client_info
    # Сначала одна ссылка
    info["client"].post(
        "/api/client-info",
        json={"business_id": info["business_id"], "mapLinks": [{"url": "https://yandex.ru/old", "mapType": "yandex"}]},
        headers=_auth_headers(),
    )
    # Затем пустой список
    r = info["client"].post(
        "/api/client-info",
        json={"business_id": info["business_id"], "mapLinks": []},
        headers=_auth_headers(),
    )
    assert r.status_code == 200

    r2 = info["client"].get(f"/api/client-info?business_id={info['business_id']}", headers=_auth_headers())
    assert r2.status_code == 200
    assert _get_map_links(r2) == []


# --- E: GET без business_id -> данные первого бизнеса пользователя
def test_get_without_business_id_returns_first_business(test_db_client_info):
    info = test_db_client_info
    r = info["client"].get("/api/client-info", headers=_auth_headers())
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("success") is True
    assert data.get("businessName") == "Test Business"
    assert "mapLinks" in data


# --- F: GET с несуществующим business_id -> 404
def test_get_nonexistent_business_id_returns_404(test_db_client_info):
    info = test_db_client_info
    fake_id = str(uuid.uuid4())
    r = info["client"].get(f"/api/client-info?business_id={fake_id}", headers=_auth_headers())
    assert r.status_code == 404


# --- G: Статический тест. В runtime (src/, без scripts и migrate_*.py) нет PRAGMA/ClientInfo.
def test_no_pragma_clientinfo_in_runtime():
    """Всегда выполняется. Проверяет отсутствие PRAGMA table_info(ClientInfo), FROM ClientInfo, INTO ClientInfo в src/ (исключая scripts/ и файлы migrate_*.py)."""
    from pathlib import Path
    import re

    src = Path(__file__).resolve().parents[1] / "src"
    exclude_dirs = {"scripts"}
    exclude_files = {"check_clientinfo_structure.py"}  # утилита проверки, не runtime
    bad_pattern = re.compile(
        r"PRAGMA\s+table_info\s*\(\s*ClientInfo\s*\)|FROM\s+ClientInfo\b|INTO\s+ClientInfo\b",
        re.I,
    )

    for py in src.rglob("*.py"):
        if any(d in py.parts for d in exclude_dirs):
            continue
        if py.name in exclude_files or (py.name.startswith("migrate_") and py.name.endswith(".py")):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in bad_pattern.finditer(text):
            raise AssertionError(f"Found forbidden pattern in runtime: {py} -> {m.group()}")


# --- H: После POST данные видны в новой транзакции (новый коннект)
def test_post_visible_in_new_connection(test_db_client_info):
    info = test_db_client_info
    payload = {
        "business_id": info["business_id"],
        "mapLinks": [{"url": "https://yandex.ru/maps/org/newconn", "mapType": "yandex"}],
    }
    r = info["client"].post("/api/client-info", json=payload, headers=_auth_headers())
    assert r.status_code == 200

    from tests.helpers.db_init_client_info import get_connection_with_search_path
    conn = get_connection_with_search_path(info["dsn"], info["schema_name"])
    with conn.cursor() as cur:
        cur.execute("SELECT url FROM businessmaplinks WHERE business_id = %s", (info["business_id"],))
        rows = cur.fetchall()
    conn.close()
    urls = [r["url"] if isinstance(r, dict) else r[0] for r in rows]
    assert "https://yandex.ru/maps/org/newconn" in urls
