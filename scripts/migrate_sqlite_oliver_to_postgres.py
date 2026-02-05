#!/usr/bin/env python3
"""
Одноразовая миграция из старой SQLite-базы `src/reports.db` в PostgreSQL:
- Пользователь с email demyanovap@yandex.ru (суперадмин)
- Бизнес "Оливер" + его владелец (чтобы не ломать FK)

ВНИМАНИЕ: запускать ТОЛЬКО один раз.
"""
import os
import sqlite3
from datetime import datetime

import sys

# Добавляем src в sys.path, чтобы можно было импортировать safe_db_utils
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from safe_db_utils import safe_migrate


SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "reports.db")


def load_from_sqlite():
    """Считать нужные записи из старой SQLite БД, ничего в ней не изменяя."""
    if not os.path.exists(SQLITE_PATH):
        raise FileNotFoundError(f"SQLite база не найдена: {SQLITE_PATH}")

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # Пользователь-суперадмин
        cur.execute(
            "SELECT * FROM Users WHERE email = ?", ("demyanovap@yandex.ru",)
        )
        superadmin_row = cur.fetchone()
        if not superadmin_row:
            raise RuntimeError(
                "В SQLite не найден пользователь demyanovap@yandex.ru"
            )

        # Бизнес "Оливер"
        cur.execute(
            "SELECT * FROM Businesses WHERE name LIKE ?", ("%Оливер%",)
        )
        business_row = cur.fetchone()
        if not business_row:
            raise RuntimeError("В SQLite не найден бизнес с названием, содержащим 'Оливер'")

        # Владелец бизнеса (по owner_id)
        owner_id = business_row["owner_id"]
        cur.execute("SELECT * FROM Users WHERE id = ?", (owner_id,))
        owner_row = cur.fetchone()

        return superadmin_row, owner_row, business_row
    finally:
        conn.close()


def migrate_to_postgres(cursor):
    """
    Реальная миграция в PostgreSQL.
    Вызывается внутри safe_migrate(), cursor — это PostgreSQL cursor.
    """
    superadmin_row, owner_row, business_row = load_from_sqlite()

    now = datetime.now()

    # --- 1. Миграция пользователя demyanovap@yandex.ru ---
    cursor.execute("SELECT id, is_superadmin FROM users WHERE email = %s", ("demyanovap@yandex.ru",))
    existing = cursor.fetchone()

    if existing:
        # Пользователь уже есть в PostgreSQL — просто убеждаемся, что он суперадмин
        existing_id = existing[0]
        cursor.execute(
            """
            UPDATE users
            SET is_superadmin = TRUE,
                is_active = TRUE,
                updated_at = %s
            WHERE id = %s
            """,
            (now, existing_id),
        )
        superadmin_id = existing_id
    else:
        # Вставляем нового пользователя с тем же id и хэшем пароля
        superadmin_id = superadmin_row["id"]
        cursor.execute(
            """
            INSERT INTO users (
                id, email, password_hash, name, phone,
                telegram_id,
                created_at, updated_at,
                is_active, is_verified, is_superadmin,
                verification_token, reset_token, reset_token_expires
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            """,
            (
                superadmin_row["id"],
                superadmin_row["email"],
                superadmin_row["password_hash"],
                superadmin_row["name"],
                superadmin_row["phone"],
                superadmin_row["telegram_id"],
                superadmin_row["created_at"] or now,
                superadmin_row["updated_at"] or now,
                bool(superadmin_row["is_active"]),
                bool(superadmin_row["is_verified"]),
                True,  # принудительно делаем суперадмином
                None,
                superadmin_row["reset_token"],
                superadmin_row["reset_token_expires"],
            ),
        )

    # --- 2. Миграция владельца бизнеса (если есть и это не тот же суперадмин) ---
    owner_id = business_row["owner_id"]
    owner_pg_id = None

    # Важно: в старой БД у владельца может не быть пароля (password_hash = NULL),
    # а в PostgreSQL поле NOT NULL. В таком случае не создаём отдельного владельца,
    # а просто назначаем владельцем суперадмина.
    if owner_row and owner_id != superadmin_id and owner_row["password_hash"]:
        cursor.execute("SELECT id FROM users WHERE id = %s", (owner_id,))
        existing_owner = cursor.fetchone()
        if existing_owner:
            owner_pg_id = existing_owner[0]
        else:
            cursor.execute(
                """
                INSERT INTO users (
                    id, email, password_hash, name, phone,
                    telegram_id,
                    created_at, updated_at,
                    is_active, is_verified, is_superadmin,
                    verification_token, reset_token, reset_token_expires
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    owner_row["id"],
                    owner_row["email"],
                    owner_row["password_hash"],
                    owner_row["name"],
                    owner_row["phone"],
                    owner_row["telegram_id"],
                    owner_row["created_at"] or now,
                    owner_row["updated_at"] or now,
                    bool(owner_row["is_active"]),
                    bool(owner_row["is_verified"]),
                    bool(owner_row["is_superadmin"]),
                    None,
                    owner_row["reset_token"],
                    owner_row["reset_token_expires"],
                ),
            )
            owner_pg_id = owner_row["id"]
    else:
        # Если владельца нет, он совпадает с суперадмином или у него нет пароля —
        # считаем владельцем суперадмина
        owner_pg_id = superadmin_id

    # --- 3. Миграция бизнеса "Оливер" ---
    business_id = business_row["id"]

    cursor.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
    existing_business = cursor.fetchone()
    if existing_business:
        # Уже существует — ничего не делаем, только убеждаемся, что owner_id совпадает
        cursor.execute(
            "UPDATE businesses SET owner_id = %s, updated_at = %s WHERE id = %s",
            (owner_pg_id, now, business_id),
        )
        return

    # Вставляем новый бизнес, маппим доступные колонки
    cursor.execute(
        """
        INSERT INTO businesses (
            id, name, description, industry, business_type,
            address, working_hours, phone, email, website,
            owner_id,
            is_active,
            created_at, updated_at,
            city, country, timezone,
            yandex_org_id, yandex_url, yandex_rating,
            yandex_reviews_total, yandex_reviews_30d, yandex_last_sync
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s,
            %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        """,
        (
            business_row["id"],
            business_row["name"],
            business_row["description"],
            business_row["industry"],
            business_row["business_type"],
            business_row["address"],
            business_row["working_hours"],
            business_row["phone"],
            business_row["email"],
            business_row["website"],
            owner_pg_id,
            bool(business_row["is_active"]),
            business_row["created_at"] or now,
            business_row["updated_at"] or now,
            business_row["city"],
            business_row["country"],
            business_row["timezone"],
            business_row["yandex_org_id"],
            business_row["yandex_url"],
            business_row["yandex_rating"],
            business_row["yandex_reviews_total"],
            business_row["yandex_reviews_30d"],
            business_row["yandex_last_sync"],
        ),
    )


def main():
    print("🚀 Запуск миграции пользователя demyanovap@yandex.ru и бизнеса 'Оливер' из SQLite в PostgreSQL")
    success = safe_migrate(
        migrate_to_postgres,
        description="Миграция пользователя demyanovap@yandex.ru и бизнеса 'Оливер' из src/reports.db",
    )
    if success:
        print("✅ Миграция завершена успешно")
    else:
        print("❌ Миграция завершилась с ошибкой (см. логи выше)")


if __name__ == "__main__":
    main()

