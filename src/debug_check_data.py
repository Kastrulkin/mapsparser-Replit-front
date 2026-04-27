#!/usr/bin/env python3
import os
import sqlite3
import sys


POSSIBLE_PATHS = [
    "src/reports.db",
    "reports.db",
]


def resolve_db_path() -> str:
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Legacy SQLite reports.db not found. Current production runtime uses PostgreSQL in Docker; "
        "use this script only for legacy local debug snapshots."
    )


def check_services(db_name: str, business_id: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id = ?", (business_id,))
    count = cursor.fetchone()[0]
    print(f"Services found in legacy DB for {business_id}: {count}")

    if count > 0:
        cursor.execute(
            "SELECT name, price FROM UserServices WHERE business_id = ? LIMIT 5",
            (business_id,),
        )
        rows = cursor.fetchall()
        print("Sample services:")
        for name, price in rows:
            print(f"  - {name}: {price}")

    cursor.execute("SELECT COUNT(*) FROM ExternalBusinessStats WHERE business_id = ?", (business_id,))
    stats_count = cursor.fetchone()[0]
    print(f"Stats entries in legacy DB: {stats_count}")

    conn.close()


if __name__ == "__main__":
    target_business_id = sys.argv[1] if len(sys.argv) > 1 else "533c1300-8a54-43a8-aa1f-69a8ed9c24ba"
    db_path = resolve_db_path()
    print(f"Checking legacy SQLite DB: {db_path}")
    check_services(db_path, target_business_id)
