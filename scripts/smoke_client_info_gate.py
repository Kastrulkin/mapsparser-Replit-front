#!/usr/bin/env python3
"""
Smoke gate-тест для /api/client-info (Postgres-only).
Проверяет GET/POST через Flask test client на локальной БД (DATABASE_URL).
"""
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from pg_db_utils import get_db_connection, log_connection_info


def run_smoke():
    print("=" * 60)
    print("🚀 Smoke gate: /api/client-info (Postgres-only)")
    print("=" * 60)

    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL не установлен")
        return 1

    log_connection_info("SMOKE")

    results = []

    # 1) Подключение
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT current_database() AS db, current_user AS user")
        row = cur.fetchone()
        print(f"✅ Подключение: db={row.get('db')}, user={row.get('user')}")
        cur.close()
        conn.close()
        results.append(("Подключение", True))
    except Exception as e:
        print(f"❌ Подключение: {e}")
        results.append(("Подключение", False))
        _print_results(results)
        return 1

    # 2) Найти первого владельца и бизнес
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, owner_id FROM businesses WHERE is_active = TRUE LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            print("⚠️ Нет ни одного бизнеса в БД — пропускаем GET/POST")
            results.append(("GET/POST (нет данных)", True))
            _print_results(results)
            return 0
        business_id = row["id"] if isinstance(row, dict) else row[0]
        user_id = row["owner_id"] if isinstance(row, dict) else row[1]
        print(f"   Тестовый business_id={business_id}, owner_id={user_id}")
    except Exception as e:
        print(f"❌ Поиск бизнеса: {e}")
        results.append(("Поиск business", False))
        _print_results(results)
        return 1

    # 3) GET/POST через Flask test client (без поднятия сервера)
    try:
        import main as main_mod
        main_mod.verify_session = lambda _: {"user_id": user_id, "id": user_id, "is_superadmin": False}
        client = main_mod.app.test_client()
        headers = {"Authorization": "Bearer smoke-token"}

        # GET
        r_get = client.get(f"/api/client-info?business_id={business_id}", headers=headers)
        if r_get.status_code != 200:
            print(f"❌ GET /api/client-info: {r_get.status_code}")
            results.append(("GET client-info", False))
        else:
            data = r_get.get_json()
            links_before = (data or {}).get("mapLinks", [])
            print(f"✅ GET 200, mapLinks: {len(links_before)}")
            results.append(("GET client-info", True))

        # POST — сохраняем одну ссылку
        test_url = "https://yandex.ru/maps/org/smoke-" + uuid.uuid4().hex[:8]
        r_post = client.post(
            "/api/client-info",
            json={"business_id": business_id, "mapLinks": [{"url": test_url, "mapType": "yandex"}]},
            headers=headers,
        )
        if r_post.status_code != 200:
            print(f"❌ POST /api/client-info: {r_post.status_code}")
            results.append(("POST client-info", False))
        else:
            print("✅ POST 200")
            results.append(("POST client-info", True))

        # GET снова — должна появиться ссылка
        r_get2 = client.get(f"/api/client-info?business_id={business_id}", headers=headers)
        if r_get2.status_code != 200:
            print(f"❌ GET после POST: {r_get2.status_code}")
            results.append(("GET после POST", False))
        else:
            data2 = r_get2.get_json()
            links_after = (data2 or {}).get("mapLinks", [])
            found = any(l.get("url") == test_url for l in links_after)
            if found:
                print(f"✅ GET после POST: ссылка сохранена, всего {len(links_after)}")
                results.append(("GET после POST", True))
            else:
                print(f"❌ GET после POST: ожидалась ссылка {test_url}, получено {len(links_after)}")
                results.append(("GET после POST", False))

        # Проверка в БД в новой транзакции
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute(
            "SELECT COUNT(*) AS c FROM businessmaplinks WHERE business_id = %s",
            (business_id,),
        )
        row2 = cur2.fetchone()
        count = row2["c"] if isinstance(row2, dict) else row2[0]
        cur2.close()
        conn2.close()
        if count >= 1:
            print(f"✅ В businessmaplinks для business_id: {count} строк(и)")
            results.append(("Проверка businessmaplinks", True))
        else:
            print(f"❌ В businessmaplinks для business_id: 0 строк")
            results.append(("Проверка businessmaplinks", False))

    except Exception as e:
        print(f"❌ Ошибка GET/POST: {e}")
        import traceback
        traceback.print_exc()
        results.append(("GET/POST", False))

    _print_results(results)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    return 0 if passed == total else 1


def _print_results(results):
    print("\n" + "=" * 60)
    print("📊 Итоги smoke gate client-info")
    print("=" * 60)
    for name, ok in results:
        print(f"   {'✅ PASS' if ok else '❌ FAIL'}: {name}")
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"\n   Всего: {passed}/{total} тестов прошли")


if __name__ == "__main__":
    sys.exit(run_smoke())
