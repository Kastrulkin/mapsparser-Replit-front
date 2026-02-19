#!/usr/bin/env python3
"""
Диагностика результата парсинга по BUSINESS_ID.
Печатает: последнюю запись из cards, кол-во услуг в userservices, слепок businesses.
Не падает при TEXT-полях вместо JSONB (печатает "(not jsonb)" и пропускает jsonb_*).
Запуск: python scripts/diagnose_parsing_result.py <BUSINESS_ID>
       или из корня: PYTHONPATH=src python scripts/diagnose_parsing_result.py <BUSINESS_ID>
"""
import sys
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)


def _row_to_dict(cursor, row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    cols = [d[0] for d in cursor.description] if cursor.description else []
    return dict(zip(cols, row)) if cols else None


def _safe_json_len(val, name):
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return len(val)
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return len(parsed) if isinstance(parsed, (list, dict)) else "(not array/object)"
        except Exception:
            return "(not jsonb)"
    return "(unknown type)"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_parsing_result.py <BUSINESS_ID>", file=sys.stderr)
        return 1
    business_id = sys.argv[1].strip()

    try:
        from pg_db_utils import get_db_connection
    except Exception as e:
        print("❌ pg_db_utils (DATABASE_URL):", e, file=sys.stderr)
        return 1

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1) Последняя запись из cards
        cur.execute("""
            SELECT id, created_at, title, address, rating, reviews_count,
                   overview, products, news, photos, hours_full, competitors
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        row = cur.fetchone()
        card = _row_to_dict(cur, row)

        print("=== 1) Last card (cards) ===")
        if not card:
            print("  (no row)")
        else:
            print(f"  id: {card.get('id')}")
            print(f"  created_at: {card.get('created_at')}")
            print(f"  title: {card.get('title')}")
            print(f"  address: {card.get('address')}")
            print(f"  rating: {card.get('rating')}  reviews_count: {card.get('reviews_count')}")
            for col in ("products", "news", "photos", "hours_full", "competitors"):
                val = card.get(col)
                if val is None:
                    print(f"  {col}: NULL")
                else:
                    ln = _safe_json_len(val, col)
                    typ = type(val).__name__
                    print(f"  {col}: type={typ} len={ln}")

        # 2) Количество услуг
        cur.execute("SELECT count(*) FROM userservices WHERE business_id = %s", (business_id,))
        r = cur.fetchone()
        cnt = r[0] if r and (isinstance(r, (list, tuple)) or not hasattr(r, "keys")) else (r.get("count") if hasattr(r, "get") else 0)
        print("\n=== 2) userservices count ===")
        print(f"  count(*): {cnt}")

        # 2b) Последние задачи parsequeue по этому бизнесу
        cur.execute("""
            SELECT id, status, error_message, warnings, created_at, updated_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (business_id,))
        pq_rows = cur.fetchall()
        print("\n=== 2b) parsequeue (last 5) ===")
        if not pq_rows:
            print("  (no rows)")
        else:
            for r in pq_rows:
                rd = _row_to_dict(cur, r)
                print(f"  id={rd.get('id')} status={rd.get('status')} created_at={rd.get('created_at')}")
                if rd.get("error_message"):
                    print(f"    error_message: {rd.get('error_message')[:120]}...")
                if rd.get("warnings"):
                    print(f"    warnings: {rd.get('warnings')}")

        # 3) Слепок businesses
        cur.execute("""
            SELECT id, site, rating, reviews_count, categories, last_parsed_at
            FROM businesses
            WHERE id = %s
        """, (business_id,))
        row = cur.fetchone()
        biz = _row_to_dict(cur, row)
        print("\n=== 3) businesses (snapshot) ===")
        if not biz:
            print("  (no row)")
        else:
            print(f"  id: {biz.get('id')}")
            print(f"  site: {biz.get('site')}")
            print(f"  rating: {biz.get('rating')}  reviews_count: {biz.get('reviews_count')}")
            print(f"  categories: {biz.get('categories')}")
            print(f"  last_parsed_at: {biz.get('last_parsed_at')}")

    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        cur.close()
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
