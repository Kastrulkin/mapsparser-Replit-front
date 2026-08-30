#!/usr/bin/env python3
"""Narrow fixture controls for the isolated LocalOS staging database."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import urlencode

from database_manager import get_db_connection


FIXTURE_NAMESPACE = uuid.UUID("e48b07f6-e923-4d6d-9a70-b1de982d2f11")
FLOWS = {"maps", "influencer", "partnership", "content", "automation"}
OWNER_EMAIL = "owner@localos-e2e.invalid"
OWNER_TELEGRAM_ID = "900000001"
OWNER_BUSINESS_NAME = "[E2E] Салон Север"
FINANCE_FIXTURE_FILE = "localos-e2e-finance.csv"
OWNER_NETWORK_NAME = "[E2E] Сеть салонов"
FOREIGN_BUSINESS_NAME = "[E2E] Чужая точка"
FOREIGN_NETWORK_NAME = "[E2E] Чужая сеть"


def fixture_id(label: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, label))


def require_isolated_staging() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if os.getenv("APP_ENV") != "staging" or "localos_staging" not in database_url:
        raise RuntimeError("Fixture controls are available only in isolated staging")


def verification_token(email: str) -> None:
    if not email.endswith("@localos-e2e.invalid"):
        raise RuntimeError("Only synthetic .invalid accounts are supported")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT verification_token FROM users WHERE lower(email) = lower(%s) LIMIT 1",
        (email,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        raise RuntimeError("Verification token was not found")
    print(row[0])


def owner_business_id() -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id
        FROM businesses b
        JOIN users u ON u.id = b.owner_id
        WHERE lower(u.email) = lower(%s) AND b.name = %s
        LIMIT 1
        """,
        (OWNER_EMAIL, OWNER_BUSINESS_NAME),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("Synthetic owner business was not found")
    return str(row[0])


def owner_user_id() -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE lower(email) = lower(%s) LIMIT 1", (OWNER_EMAIL,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("Synthetic owner was not found")
    return str(row[0])


def reset_finance() -> None:
    business_id = owner_business_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM finance_import_batches WHERE business_id = %s AND file_name = %s",
        (business_id, FINANCE_FIXTURE_FILE),
    )
    batch_ids = [str(row[0]) for row in cursor.fetchall()]
    if batch_ids:
        for table_name in (
            "finance_entries",
            "finance_service_metrics",
            "finance_staff_metrics",
            "finance_workplace_metrics",
        ):
            cursor.execute(
                f"DELETE FROM {table_name} WHERE business_id = %s AND import_batch_id = ANY(%s)",
                (business_id, batch_ids),
            )
        cursor.execute(
            "DELETE FROM finance_import_batches WHERE business_id = %s AND id = ANY(%s)",
            (business_id, batch_ids),
        )
    conn.commit()
    conn.close()
    print(business_id)


def network_fixture() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT n.id, n.name,
               ARRAY_AGG(b.id ORDER BY b.name) AS business_ids,
               ARRAY_AGG(b.name ORDER BY b.name) AS business_names
        FROM networks n
        JOIN businesses b ON b.network_id = n.id
        WHERE n.name = %s
        GROUP BY n.id, n.name
        """,
        (OWNER_NETWORK_NAME,),
    )
    owner_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT n.id AS network_id, b.id AS business_id
        FROM networks n
        JOIN businesses b ON b.network_id = n.id
        WHERE n.name = %s AND b.name = %s
        LIMIT 1
        """,
        (FOREIGN_NETWORK_NAME, FOREIGN_BUSINESS_NAME),
    )
    foreign_row = cursor.fetchone()
    conn.close()
    if not owner_row or not foreign_row:
        raise RuntimeError("Synthetic network fixtures were not found")
    print(json.dumps({
        "network_id": str(owner_row[0]),
        "network_name": str(owner_row[1]),
        "business_ids": [str(item) for item in owner_row[2]],
        "business_names": [str(item) for item in owner_row[3]],
        "foreign_network_id": str(foreign_row[0]),
        "foreign_business_id": str(foreign_row[1]),
        "foreign_business_name": FOREIGN_BUSINESS_NAME,
    }, ensure_ascii=False))


def reset_journey(flow: str) -> None:
    if flow not in FLOWS:
        raise RuntimeError("Unknown synthetic journey flow")
    journey_id = fixture_id(f"journey:{flow}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM journey_actions WHERE journey_id = %s", (journey_id,))
    cursor.execute(
        """
        UPDATE lead_journeys
        SET status = 'preview', claimed_user_id = NULL, claimed_business_id = NULL,
            claimed_at = NULL, revoked_at = NULL, updated_at = NOW()
        WHERE id = %s AND source = 'e2e_fixture'
        """,
        (journey_id,),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        conn.close()
        raise RuntimeError("Synthetic journey was not found")
    conn.commit()
    conn.close()
    print(journey_id)


def cleanup_admin_journeys() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM lead_journeys journey
        USING prospectingleads lead
        WHERE journey.prospect_lead_id = lead.id
          AND journey.source = 'admin_journey_builder'
          AND lead.source = 'e2e_fixture'
        """
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(deleted)


def telegram_init_data() -> None:
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("Synthetic Telegram bot token is not configured")
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "localos-staging-e2e-query",
        "user": json.dumps({
            "id": int(OWNER_TELEGRAM_ID),
            "first_name": "E2E",
            "last_name": "Владелец",
            "username": "localos_e2e_owner",
        }, ensure_ascii=False, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    print(urlencode(values))


def main() -> None:
    require_isolated_staging()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    token_parser = subparsers.add_parser("verification-token")
    token_parser.add_argument("email")
    reset_parser = subparsers.add_parser("reset-journey")
    reset_parser.add_argument("flow", choices=sorted(FLOWS))
    subparsers.add_parser("owner-business-id")
    subparsers.add_parser("owner-user-id")
    subparsers.add_parser("reset-finance")
    subparsers.add_parser("network-fixture")
    subparsers.add_parser("telegram-init-data")
    subparsers.add_parser("cleanup-admin-journeys")
    args = parser.parse_args()

    if args.command == "verification-token":
        verification_token(args.email)
        return
    if args.command == "owner-business-id":
        print(owner_business_id())
        return
    if args.command == "owner-user-id":
        print(owner_user_id())
        return
    if args.command == "reset-finance":
        reset_finance()
        return
    if args.command == "network-fixture":
        network_fixture()
        return
    if args.command == "telegram-init-data":
        telegram_init_data()
        return
    if args.command == "cleanup-admin-journeys":
        cleanup_admin_journeys()
        return
    reset_journey(args.flow)


if __name__ == "__main__":
    main()
